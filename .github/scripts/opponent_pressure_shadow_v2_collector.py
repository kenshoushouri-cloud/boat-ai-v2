# -*- coding: utf-8 -*-
"""Compact opponent-pressure Shadow collector v2.

Stores one row per race using typed arrays rather than verbose JSONB.
The feature remains Shadow-only and is never read by Production decisions.
PR mode is dry-run/read-only. Controlled writes are performed only via the
Issue #42 pilot workflow after merge.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-22 opponent-pressure-shadow-v2-compact"
TRAIN_START = date.fromisoformat(os.getenv("OPPONENT_PRESSURE_TRAIN_START", "2025-07-01"))
SHRINK_K = float(os.getenv("OPPONENT_PRESSURE_SHRINK_K", "100"))
TRAIN_COND_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_COND_MIN", "40"))
TRAIN_BASE_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_BASE_MIN", "500"))
ENABLED = os.getenv("OPPONENT_PRESSURE_SHADOW_V2_ENABLED", "0").strip().lower() in {"1","true","yes","on"}
DRY_RUN = os.getenv("OPPONENT_PRESSURE_SHADOW_V2_DRY_RUN", "1").strip().lower() in {"1","true","yes","on"}
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
WINDOW_NAME = (os.getenv("WINDOW_NAME") or "unknown").strip().lower()


def _target_race_ids() -> set[str]:
    raw=(os.getenv("TARGET_RACE_IDS") or "").strip()
    return {x for x in re.split(r"[,\s]+",raw) if x} if raw else set()


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("""
          create table if not exists v2_opponent_pressure_shadow_v2 (
            race_id text primary key,
            race_date date not null,
            venue_id text,
            race_no integer,
            window_name text,
            model_version text not null,
            train_start date not null,
            train_end date not null,
            shrink_k real not null,
            train_cond_min integer not null,
            train_base_min integer not null,
            lane_classes smallint[] not null,
            matched_counts smallint[] not null,
            base_win real[] not null,
            base_top3 real[] not null,
            score_win real[] not null,
            score_top3 real[] not null,
            created_at timestamptz default now(),
            updated_at timestamptz default now(),
            constraint ck_opp_pressure_v2_array_lengths check (
              cardinality(lane_classes)=6 and cardinality(matched_counts)=6 and
              cardinality(base_win)=6 and cardinality(base_top3)=6 and
              cardinality(score_win)=6 and cardinality(score_top3)=6
            )
          )
        """)
        cur.execute("create index if not exists ix_v2_opponent_pressure_shadow_v2_date on v2_opponent_pressure_shadow_v2(race_date)")
    conn.commit()


def _load_effects(conn: psycopg.Connection[Any]) -> dict[tuple[int,int,int,int],dict[str,float]]:
    q="""
    with base as (
      select a.racer_class own_class,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date >= %s and r.race_date < %s
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ), bline as (
      select own_class,own_lane,count(*)/5.0 n,avg(win)::float8 pwin,avg(top3)::float8 ptop3
      from base group by 1,2
    )
    select b.own_class,b.own_lane,b.opp_lane,b.opp_class,count(*)::bigint n,
           bl.pwin,bl.ptop3,
           ((avg(b.win)-bl.pwin)*(count(*)::float8/(count(*)+%s)))::float8 ewin,
           ((avg(b.top3)-bl.ptop3)*(count(*)::float8/(count(*)+%s)))::float8 etop3
    from base b join bline bl using(own_class,own_lane)
    where bl.n >= %s
    group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,bl.pwin,bl.ptop3
    having count(*) >= %s
    """
    out={}
    with conn.cursor() as cur:
        cur.execute(q,(TRAIN_START,TARGET_DATE,SHRINK_K,SHRINK_K,TRAIN_BASE_MIN,TRAIN_COND_MIN))
        for row in cur.fetchall():
            d=dict(row)
            out[(int(d['own_class']),int(d['own_lane']),int(d['opp_lane']),int(d['opp_class']))]={
                'pwin':float(d['pwin']),'ptop3':float(d['ptop3']),
                'ewin':float(d['ewin']),'etop3':float(d['etop3'])
            }
    return out


def _load_targets(conn: psycopg.Connection[Any]):
    ids=_target_race_ids(); params:[Any]=[TARGET_DATE]; clause=""
    if ids:
        clause=" and r.race_id=any(%s)"; params.append(sorted(ids))
    q=f"""
      select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no,e.lane,e.racer_class
      from v2_races r join v2_race_entries e on e.race_id=r.race_id
      where r.race_date=%s {clause} and e.lane between 1 and 6 and e.racer_class between 1 and 4
      order by r.race_id,e.lane
    """
    meta={}; entries={}
    with conn.cursor() as cur:
        cur.execute(q,tuple(params))
        for row in cur.fetchall():
            d=dict(row); rid=str(d['race_id'])
            meta[rid]={'race_date':d['race_date'],'venue_id':str(d['venue_id'] or '').zfill(2),'race_no':int(d['race_no'])}
            entries.setdefault(rid,[]).append({'lane':int(d['lane']),'class':int(d['racer_class'])})
    return meta,entries


def _score(rows,effects):
    rows=sorted(rows,key=lambda x:x['lane'])
    classes=[]; matched=[]; bw=[]; bt=[]; sw=[]; st=[]
    for own in rows:
        vals=[]; pwin=None; ptop3=None
        for opp in rows:
            if opp['lane']==own['lane']: continue
            e=effects.get((own['class'],own['lane'],opp['lane'],opp['class']))
            if e:
                vals.append(e); pwin=e['pwin']; ptop3=e['ptop3']
        n=len(vals)
        classes.append(own['class']); matched.append(n)
        bw.append(None if pwin is None else float(pwin)); bt.append(None if ptop3 is None else float(ptop3))
        sw.append(float(sum(v['ewin'] for v in vals)/n) if n else 0.0)
        st.append(float(sum(v['etop3'] for v in vals)/n) if n else 0.0)
    return classes,matched,bw,bt,sw,st


def main():
    print(f"OPP_PRESSURE_V2_VERSION={VERSION}",flush=True)
    print(f"OPP_PRESSURE_V2_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)} TARGET_DATE={TARGET_DATE} WINDOW={WINDOW_NAME}",flush=True)
    if not ENABLED:
        print('OPP_PRESSURE_V2_RESULT=SKIP_DISABLED',flush=True); return
    url=os.getenv('DATABASE_URL','').strip()
    if not url: raise RuntimeError('DATABASE_URL required')
    if TARGET_DATE<=TRAIN_START: raise RuntimeError('TARGET_DATE must be after train start')
    with psycopg.connect(url,row_factory=dict_row,autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute('set max_parallel_workers_per_gather=0'); cur.execute("set work_mem='8MB'"); cur.execute("set statement_timeout='180s'")
        effects=_load_effects(conn); meta,entries=_load_targets(conn)
        payloads=[]; complete=0
        for rid,rows in entries.items():
            arrays=_score(rows,effects)
            if len(rows)==6 and all(n>=4 for n in arrays[1]): complete+=1
            payloads.append((rid,arrays))
        print(f"OPP_PRESSURE_V2_EFFECT_CELLS={len(effects)} TARGET_RACES={len(entries)} COMPLETE_RACES={complete}",flush=True)
        if DRY_RUN:
            conn.rollback(); print('OPP_PRESSURE_V2_WRITE_ROWS=0',flush=True); print('OPP_PRESSURE_V2_RESULT=PASS_DRY_RUN',flush=True); return
        _ensure_schema(conn)
        with conn.cursor() as cur:
            for rid,arr in payloads:
                m=meta[rid]; classes,matched,bw,bt,sw,st=arr
                cur.execute("""
                  insert into v2_opponent_pressure_shadow_v2
                    (race_id,race_date,venue_id,race_no,window_name,model_version,train_start,train_end,
                     shrink_k,train_cond_min,train_base_min,lane_classes,matched_counts,base_win,base_top3,score_win,score_top3,updated_at)
                  values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                  on conflict(race_id) do update set
                    window_name=excluded.window_name,model_version=excluded.model_version,train_start=excluded.train_start,
                    train_end=excluded.train_end,shrink_k=excluded.shrink_k,train_cond_min=excluded.train_cond_min,
                    train_base_min=excluded.train_base_min,lane_classes=excluded.lane_classes,matched_counts=excluded.matched_counts,
                    base_win=excluded.base_win,base_top3=excluded.base_top3,score_win=excluded.score_win,score_top3=excluded.score_top3,updated_at=now()
                """,(rid,m['race_date'],m['venue_id'],m['race_no'],WINDOW_NAME,VERSION,TRAIN_START,TARGET_DATE-timedelta(days=1),SHRINK_K,TRAIN_COND_MIN,TRAIN_BASE_MIN,classes,matched,bw,bt,sw,st))
        conn.commit(); print(f"OPP_PRESSURE_V2_WRITE_ROWS={len(payloads)}",flush=True); print('OPP_PRESSURE_V2_RESULT=PASS_WRITE',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f"OPP_PRESSURE_V2_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
