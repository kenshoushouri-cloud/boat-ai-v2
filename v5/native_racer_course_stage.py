"""V5 standalone OFFICIAL racer course-stats snapshot -> physical stage ONLY.

Uses boat_data_stage.races/entries for today's racers, the official racer
course page, and the existing parser FUNCTION only; never imports legacy
save/fetch functions and never writes public.v2_*. The official page is a
point-in-time aggregate, so only TODAY can be collected (no back-fill).
Default is PLAN: read-only, no HTTP. One transaction per racer (6 course rows).
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import os
import re
import time
from urllib.parse import urlsplit, parse_qs

from v5.native_stage_race_entries_pg import JST, blocked_by_stage_delta

SOURCE="official_v5_native_racer_course"
TABLE="boat_data_stage.racer_course_stats_snapshots"
FIELDS=("id","racer_number","snapshot_date","course","entry_rate","top3_rate",
        "avg_st","source","raw","created_at","updated_at")
METRICS=("entry_rate","top3_rate","avg_st")
GATES=("V5_NATIVE_COURSE_STATS_STAGE_APPROVED",
       "CONFIRM_V5_SHARED_PRIMARY_CANARY",
       "CONFIRM_LEGACY_WRITES_SEPARATELY")
RACER=re.compile(r"[1-9]\d{3}\Z")
LOCK_ID=2026102503
MAX_CONSECUTIVE_FAIL=5
NO_DATA_CANARY=20

class NoCourseData(RuntimeError):
    """Page fetched fine but has no course stats (e.g. rookie): not a failure."""

def authorize():
    if os.environ.get("DATABASE_URL")!="postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_DB_ONLY")
    if os.environ.get("V5_SHARED_PRIMARY_MODE")!="CANARY":
        raise RuntimeError("HOLD_CANARY_REQUIRED")
    for gate in GATES:
        if os.environ.get(gate)!="YES":
            raise RuntimeError("HOLD_MISSING_GATE_"+gate)
    if any(os.environ.get(k,"").upper() in ("1","YES","ON","TRUE")
           for k in ("BUY_ENABLED","AUTO_BUY","ENABLE_PURCHASE")):
        raise RuntimeError("HOLD_BUY_ENABLED")
    blocked_by_stage_delta()

def today():
    return datetime.now(JST).date()

def pending(day):
    """Racers entered today in stage that have no snapshot row for `day` yet."""
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=5,
                         autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("""SELECT DISTINCT e.racer_number
                   FROM boat_data_stage.races r
                   JOIN boat_data_stage.entries e ON e.race_id=r.race_id
                   WHERE r.race_date=%s AND e.racer_number IS NOT NULL
                     AND NOT EXISTS (
                       SELECT 1 FROM boat_data_stage.racer_course_stats_snapshots s
                       WHERE s.racer_number=e.racer_number AND s.snapshot_date=%s)
                   ORDER BY e.racer_number""",(day,day))
                return [r[0] for r in cur.fetchall()
                        if isinstance(r[0],int) and RACER.fullmatch(str(r[0]))]

def snapshot_id(racer,day,course):
    """Deterministic negative bigint in the V5 stage namespace."""
    key="\x1f".join(("racer_course_stats_snapshots",str(racer),str(day),str(course)))
    n=int.from_bytes(sha256(key.encode()).digest()[:8],"big") & ((1<<63)-1)
    return -max(n,1)

def valid_rows(parsed_rows,racer):
    """Six course rows, in range, at least one real metric overall."""
    if len(parsed_rows)!=6:
        return False
    for want,row in enumerate(parsed_rows,1):
        if row.get("racer_number")!=racer or row.get("course")!=want:
            return False
        e,t,s=(row.get(k) for k in METRICS)
        if e is not None and not 0<=e<=100: return False
        if t is not None and not 0<=t<=100: return False
        if s is not None and not 0<=s<2: return False
    return any(row.get(k) is not None for row in parsed_rows for k in METRICS)

def fetch_rows(racer,day):
    import requests
    from collect_racer_course_stats_pg import parse_course_stats  # parser only
    url=f"https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={racer}"
    with requests.Session() as client:
        response=client.get(url,timeout=(8,20),headers={
            "User-Agent":"Mozilla/5.0 (compatible; V5-stage-racer-course/1.0)"})
        response.raise_for_status()
        actual=urlsplit(response.url)
        if (actual.scheme!="https" or actual.netloc!="www.boatrace.jp"
                or actual.path!="/owpc/pc/data/racersearch/course"
                or actual.fragment or parse_qs(actual.query)!={"toban":[str(racer)]}
                or not response.content or len(response.content)>2_000_000):
            raise RuntimeError("HOLD_OFFICIAL_COURSE_URL_OR_SIZE")
        captured=datetime.now(JST)
        response.encoding=response.apparent_encoding or "utf-8"
        parsed,_debug=parse_course_stats(response.text,racer)
    if not parsed or all(row.get(k) is None for row in parsed for k in METRICS):
        raise NoCourseData("HOLD_OFFICIAL_COURSE_NO_DATA")
    if not valid_rows(parsed,racer):
        raise RuntimeError("HOLD_OFFICIAL_COURSE_UNRESOLVED")
    stamp=captured.isoformat()
    out=[]
    for row in parsed:
        values={k:row.get(k) for k in METRICS}
        out.append({"id":snapshot_id(racer,day,row["course"]),
                    "racer_number":racer,"snapshot_date":day,
                    "course":row["course"],**values,"source":SOURCE,
                    "raw":values,"created_at":stamp,"updated_at":stamp})
    return out

def save_racer(rows):
    authorize()
    from psycopg import connect,sql
    from psycopg.types.json import Jsonb
    racer=rows[0]["racer_number"]
    if not RACER.fullmatch(str(racer)) or len(rows)!=6:
        raise ValueError("HOLD_INVALID_ROWS")
    if {r["snapshot_date"] for r in rows}!={today()}:
        raise RuntimeError("HOLD_ONLY_TODAY_SNAPSHOT")
    with connect(os.environ["DATABASE_URL"],connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SELECT pg_try_advisory_xact_lock(%s)",(LOCK_ID,))
                if not cur.fetchone()[0]:
                    raise RuntimeError("HOLD_STAGE_DELTA_BUSY")
                cur.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",(TABLE,))
                found=cur.fetchone()
                if not found or found[0] not in ("r","p"):
                    raise RuntimeError("HOLD_COURSE_TABLE_NOT_PHYSICAL")
                cur.execute("""SELECT attname,attnotnull,atthasdef,attidentity,attgenerated
                        FROM pg_attribute WHERE attrelid=to_regclass(%s)
                          AND attnum>0 AND NOT attisdropped""",(TABLE,))
                catalog=cur.fetchall()
                if not set(FIELDS)<={rec[0] for rec in catalog}:
                    raise RuntimeError("HOLD_COURSE_MISSING_COLUMNS")
                unmapped=[rec[0] for rec in catalog
                          if rec[1] and not rec[2] and not rec[3] and not rec[4]
                          and rec[0] not in FIELDS]
                if unmapped:
                    raise RuntimeError("HOLD_COURSE_UNMAPPED_REQUIRED_"+",".join(unmapped[:5]))
                cur.execute("""SELECT count(*) FROM boat_data_stage.entries e
                               JOIN boat_data_stage.races r ON r.race_id=e.race_id
                               WHERE r.race_date=%s AND e.racer_number=%s""",
                            (today(),racer))
                if cur.fetchone()[0]<1:
                    raise RuntimeError("HOLD_RACER_NOT_IN_TODAY_ENTRIES")
                # A missing metric must never erase a value already stored today.
                query=sql.SQL("""INSERT INTO boat_data_stage.racer_course_stats_snapshots AS t ({})
                   VALUES ({}) ON CONFLICT (racer_number,snapshot_date,course) DO UPDATE SET
                   entry_rate=COALESCE(EXCLUDED.entry_rate,t.entry_rate),
                   top3_rate=COALESCE(EXCLUDED.top3_rate,t.top3_rate),
                   avg_st=COALESCE(EXCLUDED.avg_st,t.avg_st),
                   source=EXCLUDED.source,raw=EXCLUDED.raw,updated_at=EXCLUDED.updated_at""").format(
                      sql.SQL(",").join(map(sql.Identifier,FIELDS)),
                      sql.SQL(",").join(sql.Placeholder() for _ in FIELDS))
                for row in rows:
                    cur.execute(query,[Jsonb(row[f]) if f=="raw" else row[f]
                                       for f in FIELDS])
                cur.execute("""SELECT count(*) FROM boat_data_stage.racer_course_stats_snapshots
                               WHERE racer_number=%s AND snapshot_date=%s""",(racer,today()))
                if cur.fetchone()[0]!=6:
                    raise RuntimeError("HOLD_COURSE_NOT_SIX_AFTER_WRITE")
                return len(rows)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--max-racers",type=int,default=700)
    args=p.parse_args(argv)
    if not 1<=args.max_racers<=700:
        raise ValueError("HOLD_MAX_RACERS")
    if os.environ.get("DATABASE_URL")!="postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_DB_ONLY")
    if args.apply:
        authorize()
    day=today()
    ids=pending(day)
    print(f"V5_COURSE_STATS_STAGE day={day} pending={len(ids)} "
          f"mode={'APPLY' if args.apply else 'PLAN'}",flush=True)
    if not args.apply:
        print("V5_COURSE_PLAN_READ_ONLY_NO_HTTP_NO_WRITES_NO_BUY",flush=True)
        return 0
    batch=ids[:args.max_racers]
    failed=streak=ok=0
    no_data=[]
    for i,racer in enumerate(batch):
        try:
            n=save_racer(fetch_rows(racer,day))
            streak=0
            ok+=1
            print(f"V5_COURSE_STATS_OK {racer} rows={n}",flush=True)
        except NoCourseData as exc:
            # Neither counts toward nor resets the consecutive-failure streak.
            no_data.append(racer)
            print(f"V5_COURSE_STATS_NO_DATA {racer} {exc}",flush=True)
            if ok==0 and len(no_data)>=NO_DATA_CANARY:
                raise RuntimeError("HOLD_NO_DATA_ON_EVERY_RACER_POSSIBLE_LAYOUT_CHANGE")
        except Exception as exc:
            failed+=1
            streak+=1
            print(f"V5_COURSE_STATS_HOLD {racer} {type(exc).__name__}:"
                  f"{str(exc).splitlines()[0][:100]}",flush=True)
            if streak>=MAX_CONSECUTIVE_FAIL:
                raise RuntimeError("HOLD_CONSECUTIVE_FAILURES")
        if i+1<len(batch):
            time.sleep(.3)
    skip=set(no_data)
    remaining=[r for r in pending(day) if r not in skip]
    print(f"V5_COURSE_STATS_NO_DATA_COUNT={len(no_data)}",flush=True)
    print(f"V5_COURSE_STATS_REMAINING={len(remaining)}",flush=True)
    if failed or remaining or len(ids)>args.max_racers:
        return 3
    print("V5_COURSE_STATS_STAGE_COMPLETE_BUY_OFF",flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_COURSE_STATS_STOP "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
