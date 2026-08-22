# -*- coding: utf-8 -*-
"""Opponent-pressure Shadow collector.

Computes train-only global opponent interactions for
own_class x own_lane x opponent_lane x opponent_class and stores one compact
row per race with six lane scores. This module never changes prediction,
BUY/WATCH/SKIP, or LINE behavior.

Default is disabled. In dry-run mode it is strictly read-only and creates no
schema objects.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-22 opponent-pressure-shadow-v1"
TRAIN_START = date.fromisoformat(os.getenv("OPPONENT_PRESSURE_TRAIN_START", "2025-07-01"))
SHRINK_K = float(os.getenv("OPPONENT_PRESSURE_SHRINK_K", "100"))
TRAIN_COND_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_COND_MIN", "40"))
TRAIN_BASE_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_BASE_MIN", "500"))
ENABLED = os.getenv("OPPONENT_PRESSURE_SHADOW_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = os.getenv("OPPONENT_PRESSURE_SHADOW_DRY_RUN", os.getenv("DRY_RUN", "0")).strip().lower() in {"1", "true", "yes", "on"}
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
WINDOW_NAME = (os.getenv("WINDOW_NAME") or os.getenv("PRE_SESSION") or "unknown").strip().lower()


def _target_race_ids() -> set[str]:
    raw = (os.getenv("TARGET_RACE_IDS") or "").strip()
    return {x for x in re.split(r"[,\s]+", raw) if x} if raw else set()


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            create table if not exists v2_opponent_pressure_shadow (
                race_id text primary key,
                race_date date not null,
                venue_id text,
                race_no integer,
                window_name text,
                model_version text not null,
                train_start date not null,
                train_end date not null,
                shrink_k numeric,
                train_cond_min integer,
                train_base_min integer,
                lane_scores jsonb not null,
                created_at timestamptz default now(),
                updated_at timestamptz default now()
            )
        """)
        cur.execute("create index if not exists ix_v2_opponent_pressure_shadow_date on v2_opponent_pressure_shadow(race_date)")
    conn.commit()


def _load_effects(conn: psycopg.Connection[Any]) -> dict[tuple[int, int, int, int], dict[str, float]]:
    q = """
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
           ((avg(b.win)-bl.pwin) * (count(*)::float8/(count(*)+%s)))::float8 ewin,
           ((avg(b.top3)-bl.ptop3) * (count(*)::float8/(count(*)+%s)))::float8 etop3
    from base b join bline bl using(own_class,own_lane)
    where bl.n >= %s
    group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,bl.pwin,bl.ptop3
    having count(*) >= %s
    """
    out: dict[tuple[int, int, int, int], dict[str, float]] = {}
    with conn.cursor() as cur:
        cur.execute(q, (TRAIN_START, TARGET_DATE, SHRINK_K, SHRINK_K, TRAIN_BASE_MIN, TRAIN_COND_MIN))
        for r in cur.fetchall():
            d = dict(r)
            key = (int(d["own_class"]), int(d["own_lane"]), int(d["opp_lane"]), int(d["opp_class"]))
            out[key] = {"pwin": float(d["pwin"]), "ptop3": float(d["ptop3"]), "ewin": float(d["ewin"]), "etop3": float(d["etop3"]), "n": int(d["n"])}
    return out


def _load_target_entries(conn: psycopg.Connection[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    ids = _target_race_ids()
    params: list[Any] = [TARGET_DATE]
    id_clause = ""
    if ids:
        id_clause = " and r.race_id = any(%s)"
        params.append(sorted(ids))
    q = f"""
      select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no,
             e.lane,e.racer_class
      from v2_races r join v2_race_entries e on e.race_id=r.race_id
      where r.race_date=%s {id_clause}
        and e.lane between 1 and 6 and e.racer_class between 1 and 4
      order by r.race_id,e.lane
    """
    meta: dict[str, dict[str, Any]] = {}
    entries: dict[str, list[dict[str, Any]]] = {}
    with conn.cursor() as cur:
        cur.execute(q, tuple(params))
        for row in cur.fetchall():
            d = dict(row); rid = str(d["race_id"])
            meta[rid] = {"race_date": d["race_date"], "venue_id": str(d["venue_id"] or "").zfill(2), "race_no": int(d["race_no"])}
            entries.setdefault(rid, []).append({"lane": int(d["lane"]), "racer_class": int(d["racer_class"])})
    return meta, entries


def _score_race(rows: list[dict[str, Any]], effects: dict[tuple[int, int, int, int], dict[str, float]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for own in rows:
        vals = []
        base_win = base_top3 = None
        for opp in rows:
            if opp["lane"] == own["lane"]:
                continue
            e = effects.get((own["racer_class"], own["lane"], opp["lane"], opp["racer_class"]))
            if e:
                vals.append(e)
                base_win = e["pwin"]; base_top3 = e["ptop3"]
        matched = len(vals)
        score_win = sum(x["ewin"] for x in vals) / matched if matched else 0.0
        score_top3 = sum(x["etop3"] for x in vals) / matched if matched else 0.0
        result.append({
            "lane": own["lane"], "class": own["racer_class"], "matched_opponents": matched,
            "base_win": None if base_win is None else round(base_win, 6),
            "base_top3": None if base_top3 is None else round(base_top3, 6),
            "score_win": round(score_win, 6), "score_top3": round(score_top3, 6),
            "adj_win": None if base_win is None else round(max(.001, min(.999, base_win + score_win)), 6),
            "adj_top3": None if base_top3 is None else round(max(.001, min(.999, base_top3 + score_top3)), 6),
        })
    return result


def main() -> None:
    print(f"OPP_PRESSURE_SHADOW_VERSION={VERSION}", flush=True)
    print(f"OPP_PRESSURE_SHADOW_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)} TARGET_DATE={TARGET_DATE} WINDOW={WINDOW_NAME}", flush=True)
    if not ENABLED:
        print("OPP_PRESSURE_SHADOW_RESULT=SKIP_DISABLED", flush=True); return
    url = os.getenv("DATABASE_URL", "").strip()
    if not url: raise RuntimeError("DATABASE_URL required")
    if TARGET_DATE <= TRAIN_START: raise RuntimeError("TARGET_DATE must be after train start")
    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0"); cur.execute("set work_mem='8MB'"); cur.execute("set statement_timeout='180s'")
        effects = _load_effects(conn)
        meta, entries = _load_target_entries(conn)
        payloads = []
        complete = 0
        for rid, rows in entries.items():
            scores = _score_race(rows, effects)
            if len(rows) == 6 and all(x["matched_opponents"] >= 4 for x in scores): complete += 1
            payloads.append((rid, scores))
        print(f"OPP_PRESSURE_SHADOW_EFFECT_CELLS={len(effects)} TARGET_RACES={len(entries)} COMPLETE_RACES={complete}", flush=True)
        if DRY_RUN:
            conn.rollback()
            print("OPP_PRESSURE_SHADOW_WRITE_ROWS=0", flush=True)
            print("OPP_PRESSURE_SHADOW_RESULT=PASS_DRY_RUN", flush=True); return
        _ensure_schema(conn)
        with conn.cursor() as cur:
            for rid, scores in payloads:
                m = meta[rid]
                cur.execute("""
                  insert into v2_opponent_pressure_shadow
                    (race_id,race_date,venue_id,race_no,window_name,model_version,train_start,train_end,
                     shrink_k,train_cond_min,train_base_min,lane_scores,updated_at)
                  values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,now())
                  on conflict (race_id) do update set
                    window_name=excluded.window_name,model_version=excluded.model_version,
                    train_start=excluded.train_start,train_end=excluded.train_end,shrink_k=excluded.shrink_k,
                    train_cond_min=excluded.train_cond_min,train_base_min=excluded.train_base_min,
                    lane_scores=excluded.lane_scores,updated_at=now()
                """, (rid,m["race_date"],m["venue_id"],m["race_no"],WINDOW_NAME,VERSION,TRAIN_START,TARGET_DATE-timedelta(days=1),SHRINK_K,TRAIN_COND_MIN,TRAIN_BASE_MIN,json.dumps(scores,separators=(",",":"))))
        conn.commit()
        print(f"OPP_PRESSURE_SHADOW_WRITE_ROWS={len(payloads)}", flush=True)
        print("OPP_PRESSURE_SHADOW_RESULT=PASS_WRITE", flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print(f"OPP_PRESSURE_SHADOW_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True); raise
