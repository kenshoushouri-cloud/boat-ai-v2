# -*- coding: utf-8 -*-
"""Compact opponent-pressure Shadow collector v2.

Stores one row per race using fixed lane-order typed arrays instead of JSONB.
Production prediction / BUY-WATCH-SKIP / LINE are not touched.

PR dry-run is strictly read-only and compares recomputed values with the
existing v1 pilot rows for 2026-08-22. Live write mode is Forward-only:
complete race cards are required, writes must occur before 08:15 JST and
strictly before every target race deadline, and existing rows are immutable
(first-write-wins).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
VERSION_TEXT = "2026-09-11 opponent-pressure-shadow-v2-timing-safe-v3"
VERSION_CODE = 2
FORWARD_CUTOFF = time(8, 15)
TRAIN_START = date.fromisoformat(os.getenv("OPPONENT_PRESSURE_TRAIN_START", "2025-07-01"))
SHRINK_K = float(os.getenv("OPPONENT_PRESSURE_SHRINK_K", "100"))
TRAIN_COND_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_COND_MIN", "40"))
TRAIN_BASE_MIN = int(os.getenv("OPPONENT_PRESSURE_TRAIN_BASE_MIN", "500"))
ENABLED = os.getenv("OPPONENT_PRESSURE_V2_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = os.getenv("OPPONENT_PRESSURE_V2_DRY_RUN", os.getenv("DRY_RUN", "0")).strip().lower() in {"1", "true", "yes", "on"}
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))


def _target_race_ids() -> set[str]:
    raw = (os.getenv("TARGET_RACE_IDS") or "").strip()
    return {x for x in re.split(r"[,\s]+", raw) if x} if raw else set()


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("""
          create table if not exists v2_opponent_pressure_shadow_v2 (
            race_id text primary key,
            race_date date not null,
            venue_id text,
            race_no smallint,
            model_version smallint not null,
            train_end date not null,
            racer_classes smallint[] not null,
            matched_opponents smallint[] not null,
            base_win real[] not null,
            base_top3 real[] not null,
            score_win real[] not null,
            score_top3 real[] not null,
            adj_win real[] not null,
            adj_top3 real[] not null,
            created_at timestamptz default now(),
            updated_at timestamptz default now(),
            check (cardinality(racer_classes)=6),
            check (cardinality(matched_opponents)=6),
            check (cardinality(base_win)=6),
            check (cardinality(base_top3)=6),
            check (cardinality(score_win)=6),
            check (cardinality(score_top3)=6),
            check (cardinality(adj_win)=6),
            check (cardinality(adj_top3)=6)
          )
        """)
        cur.execute("create index if not exists ix_v2_opponent_pressure_shadow_v2_date on v2_opponent_pressure_shadow_v2(race_date)")


def _preflight_complete_cards(conn: psycopg.Connection[Any]) -> int:
    ids = _target_race_ids()
    params: list[Any] = [TARGET_DATE]
    clause = ""
    if ids:
        clause = " and r.race_id = any(%s)"
        params.append(sorted(ids))
    q = f"""
      with cards as (
        select r.race_id,
               count(e.*) filter(where e.lane between 1 and 6 and e.racer_class between 1 and 4) valid_entries,
               count(distinct e.lane) filter(where e.lane between 1 and 6 and e.racer_class between 1 and 4) valid_lanes,
               r.deadline_at
        from v2_races r
        left join v2_race_entries e on e.race_id=r.race_id
        where r.race_date=%s {clause}
        group by r.race_id,r.deadline_at
      )
      select count(*) total_races,
             count(*) filter(where valid_entries=6 and valid_lanes=6) complete_races,
             coalesce(sum(valid_entries),0) valid_entries,
             count(*) filter(where deadline_at is not null) deadline_races
      from cards
    """
    with conn.cursor() as cur:
        cur.execute(q, tuple(params))
        r = cur.fetchone()
    total = int(r["total_races"] or 0)
    complete = int(r["complete_races"] or 0)
    entries = int(r["valid_entries"] or 0)
    deadlines = int(r["deadline_races"] or 0)
    print(
        f"OPP_PRESSURE_V2_CARD_PREFLIGHT=total:{total} complete:{complete} entries:{entries} deadlines:{deadlines}",
        flush=True,
    )
    if total <= 0 or complete != total or entries != total * 6 or deadlines != total:
        raise RuntimeError("target race cards/deadlines are not complete; no Shadow write allowed")
    if ids and total != len(ids):
        raise RuntimeError(f"requested target race ids incomplete expected={len(ids)} actual={total}")
    return total


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
        for row in cur.fetchall():
            d = dict(row)
            key = (int(d["own_class"]), int(d["own_lane"]), int(d["opp_lane"]), int(d["opp_class"]))
            out[key] = {
                "pwin": float(d["pwin"]), "ptop3": float(d["ptop3"]),
                "ewin": float(d["ewin"]), "etop3": float(d["etop3"]),
            }
    return out


def _load_targets(conn: psycopg.Connection[Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, int]]]]:
    ids = _target_race_ids()
    params: list[Any] = [TARGET_DATE]
    clause = ""
    if ids:
        clause = " and r.race_id = any(%s)"
        params.append(sorted(ids))
    q = f"""
      select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no,r.deadline_at,
             e.lane,e.racer_class
      from v2_races r join v2_race_entries e on e.race_id=r.race_id
      where r.race_date=%s {clause}
        and e.lane between 1 and 6 and e.racer_class between 1 and 4
      order by r.race_id,e.lane
    """
    meta: dict[str, dict[str, Any]] = {}
    entries: dict[str, list[dict[str, int]]] = {}
    with conn.cursor() as cur:
        cur.execute(q, tuple(params))
        for row in cur.fetchall():
            d = dict(row); rid = str(d["race_id"])
            meta[rid] = {
                "race_date": d["race_date"],
                "venue_id": str(d["venue_id"] or "").zfill(2),
                "race_no": int(d["race_no"]),
                "deadline_at": d["deadline_at"],
            }
            entries.setdefault(rid, []).append({"lane": int(d["lane"]), "class": int(d["racer_class"])})
    return meta, entries


def _assert_forward_write_window(meta: dict[str, dict[str, Any]], now: datetime | None = None) -> datetime:
    now_jst = now or datetime.now(JST)
    if now_jst.tzinfo is None or now_jst.utcoffset() is None:
        raise RuntimeError("write observation time must be timezone-aware")
    now_jst = now_jst.astimezone(JST)
    if now_jst.date() != TARGET_DATE:
        raise RuntimeError(f"Forward write target date mismatch now={now_jst.date()} target={TARGET_DATE}")
    cutoff = datetime.combine(TARGET_DATE, FORWARD_CUTOFF, tzinfo=JST)
    if now_jst >= cutoff:
        raise RuntimeError(f"Forward write cutoff reached now={now_jst.isoformat()} cutoff={cutoff.isoformat()}")
    if not meta:
        raise RuntimeError("no target race metadata")
    for rid, m in meta.items():
        deadline = m.get("deadline_at")
        if not isinstance(deadline, datetime) or deadline.tzinfo is None or deadline.utcoffset() is None:
            raise RuntimeError(f"missing/naive race deadline race_id={rid}")
        deadline_jst = deadline.astimezone(JST)
        if now_jst >= deadline_jst:
            raise RuntimeError(
                f"race deadline reached race_id={rid} now={now_jst.isoformat()} deadline={deadline_jst.isoformat()}"
            )
    print(
        f"OPP_PRESSURE_V2_TIMING_GUARD=PASS now:{now_jst.isoformat()} cutoff:{cutoff.isoformat()} races:{len(meta)}",
        flush=True,
    )
    return now_jst


def _score(rows: list[dict[str, int]], effects: dict[tuple[int, int, int, int], dict[str, float]]) -> dict[str, list[Any]]:
    rows = sorted(rows, key=lambda x: x["lane"])
    out: dict[str, list[Any]] = {k: [] for k in (
        "racer_classes", "matched_opponents", "base_win", "base_top3",
        "score_win", "score_top3", "adj_win", "adj_top3"
    )}
    for own in rows:
        vals: list[dict[str, float]] = []
        bw = bt = None
        for opp in rows:
            if opp["lane"] == own["lane"]:
                continue
            e = effects.get((own["class"], own["lane"], opp["lane"], opp["class"]))
            if e:
                vals.append(e); bw = e["pwin"]; bt = e["ptop3"]
        n = len(vals)
        sw = sum(x["ewin"] for x in vals) / n if n else 0.0
        st = sum(x["etop3"] for x in vals) / n if n else 0.0
        if bw is None or bt is None:
            raise RuntimeError(f"missing baseline lane={own['lane']}")
        out["racer_classes"].append(own["class"])
        out["matched_opponents"].append(n)
        out["base_win"].append(round(bw, 6))
        out["base_top3"].append(round(bt, 6))
        out["score_win"].append(round(sw, 6))
        out["score_top3"].append(round(st, 6))
        out["adj_win"].append(round(max(.001, min(.999, bw + sw)), 6))
        out["adj_top3"].append(round(max(.001, min(.999, bt + st)), 6))
    return out


def _compare_v1(conn: psycopg.Connection[Any], payloads: dict[str, dict[str, list[Any]]]) -> tuple[int, int, float]:
    if not payloads:
        return 0, 0, 0.0
    with conn.cursor() as cur:
        cur.execute("select race_id,lane_scores from v2_opponent_pressure_shadow where race_id=any(%s)", (sorted(payloads),))
        refs = {str(r["race_id"]): r["lane_scores"] for r in cur.fetchall()}
    compared = 0; mismatches = 0; max_abs = 0.0
    fmap = {"base_win":"base_win", "base_top3":"base_top3", "score_win":"score_win", "score_top3":"score_top3", "adj_win":"adj_win", "adj_top3":"adj_top3"}
    for rid, p in payloads.items():
        ref = refs.get(rid)
        if not isinstance(ref, list) or len(ref) != 6:
            mismatches += 1; continue
        compared += 1
        for i in range(6):
            if int(ref[i]["class"]) != int(p["racer_classes"][i]) or int(ref[i]["matched_opponents"]) != int(p["matched_opponents"][i]):
                mismatches += 1; break
            bad = False
            for pk, rk in fmap.items():
                delta = abs(float(ref[i][rk]) - float(p[pk][i]))
                max_abs = max(max_abs, delta)
                if delta > 0.0000011:
                    bad = True; break
            if bad:
                mismatches += 1; break
    return compared, mismatches, max_abs


def _verify_forward_rows(conn: psycopg.Connection[Any], expected: int) -> dict[str, int]:
    cutoff = datetime.combine(TARGET_DATE, FORWARD_CUTOFF, tzinfo=JST)
    with conn.cursor() as cur:
        cur.execute("""
          select count(*) rows,
                 count(*) filter(where s.model_version=%s and s.train_end=%s) version_rows,
                 count(*) filter(where cardinality(s.racer_classes)=6 and cardinality(s.matched_opponents)=6
                   and cardinality(s.base_win)=6 and cardinality(s.base_top3)=6
                   and cardinality(s.score_win)=6 and cardinality(s.score_top3)=6
                   and cardinality(s.adj_win)=6 and cardinality(s.adj_top3)=6) arrays_ok,
                 count(*) filter(where 4 <= all(s.matched_opponents)) matched_ok,
                 count(*) filter(where s.created_at < %s and s.updated_at < %s
                   and s.created_at < r.deadline_at and s.updated_at < r.deadline_at) timing_ok
          from v2_opponent_pressure_shadow_v2 s
          join v2_races r on r.race_id=s.race_id
          where s.race_date=%s
        """, (VERSION_CODE, TARGET_DATE-timedelta(days=1), cutoff, cutoff, TARGET_DATE))
        r = cur.fetchone()
    out = {k: int(r[k] or 0) for k in ("rows", "version_rows", "arrays_ok", "matched_ok", "timing_ok")}
    print(
        "OPP_PRESSURE_V2_POST="
        + " ".join(f"{k}:{v}" for k, v in out.items())
        + f" expected:{expected}",
        flush=True,
    )
    if any(out[k] != expected for k in out):
        raise RuntimeError(f"Forward postcondition failed expected={expected} actual={out}")
    return out


def main() -> None:
    print(f"OPP_PRESSURE_V2_VERSION={VERSION_TEXT}", flush=True)
    print(f"OPP_PRESSURE_V2_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)} TARGET_DATE={TARGET_DATE}", flush=True)
    if not ENABLED:
        print("OPP_PRESSURE_V2_RESULT=SKIP_DISABLED", flush=True); return
    url = os.getenv("DATABASE_URL", "").strip()
    if not url: raise RuntimeError("DATABASE_URL required")
    if TARGET_DATE <= TRAIN_START: raise RuntimeError("TARGET_DATE must be after train start")
    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='180s'")
        expected = _preflight_complete_cards(conn)
        meta, entries = _load_targets(conn)
        if len(meta) != expected or len(entries) != expected:
            raise RuntimeError(f"target load incomplete meta={len(meta)} entries={len(entries)} expected={expected}")
        if not DRY_RUN:
            _assert_forward_write_window(meta)
        effects = _load_effects(conn)
        payloads: dict[str, dict[str, list[Any]]] = {}
        complete = 0
        for rid, rows in entries.items():
            lanes = {int(x["lane"]) for x in rows}
            if len(rows) != 6 or lanes != {1,2,3,4,5,6}:
                continue
            p = _score(rows, effects)
            payloads[rid] = p
            if all(int(x) >= 4 for x in p["matched_opponents"]):
                complete += 1
        compared, mismatches, max_abs = _compare_v1(conn, payloads)
        print(f"OPP_PRESSURE_V2_EFFECT_CELLS={len(effects)} TARGET_RACES={len(entries)} PAYLOADS={len(payloads)} COMPLETE={complete}", flush=True)
        print(f"OPP_PRESSURE_V2_V1_COMPARE=compared:{compared} mismatches:{mismatches} max_abs:{max_abs:.8f}", flush=True)
        if TARGET_DATE == date(2026,8,22) and (compared != 156 or mismatches != 0):
            raise RuntimeError("v1 equivalence check failed")
        if DRY_RUN:
            conn.rollback()
            print("OPP_PRESSURE_V2_WRITE_ROWS=0", flush=True)
            print("OPP_PRESSURE_V2_RESULT=PASS_DRY_RUN", flush=True); return
        if len(payloads) != expected or complete != expected:
            raise RuntimeError(
                f"incomplete Forward payloads target={expected} payloads={len(payloads)} complete={complete}"
            )
        _assert_forward_write_window(meta)
        _ensure_schema(conn)
        inserted = 0
        with conn.cursor() as cur:
            for rid, p in payloads.items():
                m = meta[rid]
                cur.execute("""
                  insert into v2_opponent_pressure_shadow_v2
                    (race_id,race_date,venue_id,race_no,model_version,train_end,
                     racer_classes,matched_opponents,base_win,base_top3,score_win,score_top3,adj_win,adj_top3,updated_at)
                  values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                  on conflict (race_id) do nothing
                """, (rid,m["race_date"],m["venue_id"],m["race_no"],VERSION_CODE,TARGET_DATE-timedelta(days=1),
                      p["racer_classes"],p["matched_opponents"],p["base_win"],p["base_top3"],p["score_win"],p["score_top3"],p["adj_win"],p["adj_top3"]))
                inserted += int(cur.rowcount or 0)
        _verify_forward_rows(conn, expected)
        conn.commit()
        print(f"OPP_PRESSURE_V2_WRITE_ROWS={inserted}", flush=True)
        print(f"OPP_PRESSURE_V2_TOTAL_FORWARD_ROWS={expected}", flush=True)
        print("OPP_PRESSURE_V2_RESULT=PASS_WRITE", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"OPP_PRESSURE_V2_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
