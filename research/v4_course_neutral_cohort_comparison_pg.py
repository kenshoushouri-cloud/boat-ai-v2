# -*- coding: utf-8 -*-
"""Course-complete vs neutral-missing V4 diagnostic.

Selection is frozen before any outcome/payout query. This is a descriptive
historical diagnostic only; it does not tune thresholds, promote V5, or change
Production.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.forward_economics import forward_report, normalize_formal_settlement_rows
from research.historical_matched_contract_readiness_pg import opponent_provenance

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / ".github" / "scripts" / "candidate_discovery_v1_pg.py"
V4_PATH = ROOT / "research" / "candidate_discovery_v4_contract.py"

v1s = importlib.util.spec_from_file_location("candidate_v1_course_diag", V1_PATH)
v1 = importlib.util.module_from_spec(v1s)
assert v1s and v1s.loader
v1s.loader.exec_module(v1)

v4s = importlib.util.spec_from_file_location("candidate_v4_course_diag", V4_PATH)
v4 = importlib.util.module_from_spec(v4s)
assert v4s and v4s.loader
v4s.loader.exec_module(v4)

COURSE_SOURCE = "boatrace_official_k_applied_term_proxy"
ALL_LANES = {1, 2, 3, 4, 5, 6}
SNAPSHOT_BY_TERM = (
    (date(2025, 7, 1), date(2025, 12, 31), date(2025, 4, 30)),
    (date(2026, 1, 1), date(2026, 6, 30), date(2025, 10, 31)),
    (date(2026, 7, 1), date(2026, 9, 30), date(2026, 4, 30)),
)


def expected_snapshot(d: date) -> date | None:
    for a, b, snap in SNAPSHOT_BY_TERM:
        if a <= d <= b:
            return snap
    return None


def load_overlay(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    x = json.loads(Path(path).read_text(encoding="utf-8"))
    if x.get("contract") != "HISTORICAL_OPPONENT_EPHEMERAL_RECONSTRUCT_V1":
        raise ValueError("unexpected Opponent overlay contract")
    if x.get("target_outcome_read") is not False or x.get("database_write") is not False:
        raise ValueError("unsafe Opponent overlay")
    return {str(r["race_id"]): dict(r) for r in x.get("rows") or []}


def opponent_delta(row: dict[str, Any] | None) -> dict[int, float] | None:
    if not row:
        return None
    base = row.get("base_win")
    adj = row.get("adj_win")
    matched = row.get("matched_opponents")
    if not all(isinstance(x, list) and len(x) == 6 for x in (base, adj, matched)):
        return None
    if any(int(x) < 4 for x in matched):
        return None
    return {i + 1: float(adj[i]) - float(base[i]) for i in range(6)}


def base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
    by = {v1.si(r.get("lane"), 0): r for r in entries}
    if set(by) != ALL_LANES:
        raise ValueError("complete six-lane entries required")
    return {
        lane: v1.lane_raw_strength(by[lane], lane, venue, 0.0)
        for lane in range(1, 7)
    }


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out = {}
    for r in entries:
        lane = v1.si(r.get("lane"), 0)
        val = v1.valid_motor2(r.get("motor_place2_rate"))
        if lane not in ALL_LANES or val is None:
            return {}
        out[lane] = float(val)
    return out if set(out) == ALL_LANES else {}


def course_map(
    entries: list[dict[str, Any]],
    race_date: date,
    course_rows: dict[tuple[int, date, int], float],
) -> dict[int, float]:
    snap = expected_snapshot(race_date)
    if snap is None:
        return {}
    out = {}
    for r in entries:
        lane = v1.si(r.get("lane"), 0)
        racer = v1.si(r.get("racer_number"), 0)
        value = course_rows.get((racer, snap, lane))
        if lane in ALL_LANES and racer > 0 and value is not None:
            out[lane] = float(value)
    return out


def load_pre_result(
    conn: psycopg.Connection[Any],
    start_date: str,
    end_date: str,
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[tuple[int, date, int], float],
    dict[str, dict[str, Any]],
]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (start_date, end_date),
        )
        races = [dict(x) for x in cur.fetchall()]

        cur.execute(
            """
            select e.race_id,e.lane,e.racer_number,e.racer_class,
                   e.national_win_rate,e.national_place2_rate,
                   e.local_place2_rate,e.avg_st,e.motor_place2_rate
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date between %s and %s
             order by e.race_id,e.lane
            """,
            (start_date, end_date),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))

        cur.execute(
            """
            select racer_number,snapshot_date,course,top3_rate
              from v2_racer_course_stats_snapshots
             where source=%s
               and snapshot_date in (
                 date '2025-04-30',date '2025-10-31',date '2026-04-30'
               )
               and course between 1 and 6
               and top3_rate between 0 and 100
            """,
            (COURSE_SOURCE,),
        )
        course_rows = {
            (int(r["racer_number"]), r["snapshot_date"], int(r["course"])): float(r["top3_rate"])
            for r in cur.fetchall()
        }

        cur.execute(
            """
            select s.race_id,s.race_date,s.model_version,s.train_end,
                   s.matched_opponents,s.base_win,s.adj_win,
                   s.created_at,s.updated_at,r.deadline_at
              from v2_opponent_pressure_shadow_v2 s
              join v2_races r on r.race_id=s.race_id
             where s.race_date between %s and %s
             order by s.race_date,s.race_id
            """,
            (start_date, end_date),
        )
        opp = {str(r["race_id"]): dict(r) for r in cur.fetchall()}
    return races, entries_by, course_rows, opp


def freeze_selection(
    races: list[dict[str, Any]],
    entries_by: dict[str, list[dict[str, Any]]],
    course_rows: dict[tuple[int, date, int], float],
    opp_rows: dict[str, dict[str, Any]],
    overlay: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    meta: dict[str, dict[str, Any]] = {}

    for race in races:
        rid = str(race["race_id"])
        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v1.si(x.get("lane"), 0) for x in entries} != ALL_LANES:
            continue
        rd = race["race_date"]
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        course = course_map(entries, rd, course_rows)
        db_opp = opp_rows.get(rid)
        delta = opponent_delta(db_opp) if db_opp and opponent_provenance(db_opp) else None
        if delta is None and rid in overlay:
            delta = opponent_delta(overlay[rid])
        motor = motor_map(entries)
        probs = v4.build_v4_distribution(
            base_raw=base_raw(entries, venue),
            course_top3=course,
            motor_place2=motor,
            opponent_delta=delta,
        )
        day = rd.isoformat()
        by_day[day][rid] = probs
        meta[rid] = {
            "race_id": rid,
            "race_date": day,
            "venue_id": venue,
            "race_no": int(race.get("race_no") or 0),
            "course_usable_lanes": len(course),
            "course_cohort": "complete" if len(course) == 6 else "neutral_missing",
        }

    frozen: list[dict[str, Any]] = []
    for day in sorted(by_day):
        selected = v4.select_daily(
            by_day[day], race_cap=v4.CORE_RACES, ticket_count=v4.CORE_TICKETS
        )
        for row in selected:
            rid = str(row["race_id"])
            tickets = [str(x) for x in row["tickets"]]
            if len(tickets) != 2:
                raise RuntimeError("exact TOP2 required")
            frozen.append(
                {
                    **meta[rid],
                    "daily_rank": int(row["daily_race_rank"]),
                    "ticket1": tickets[0],
                    "ticket2": tickets[1],
                }
            )
    return frozen


# OUTCOME_QUERY_BOUNDARY
def settle(
    conn: psycopg.Connection[Any],
    frozen: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = [x["race_id"] for x in frozen]
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,result_status,race_status,
                   trifecta_ticket,trifecta_payout_yen
              from v2_results
             where race_id=any(%s)
            """,
            (ids,),
        )
        results = {str(r["race_id"]): dict(r) for r in cur.fetchall()}

    raw = []
    for row in frozen:
        res = results.get(row["race_id"])
        actual = v1.norm_ticket(res.get("trifecta_ticket")) if res else ""
        payout = int((res or {}).get("trifecta_payout_yen") or 0)
        official = bool(
            res
            and str(res.get("result_status") or "").lower() == "official"
            and str(res.get("race_status") or "").lower() == "official"
            and actual
            and payout > 0
        )
        hit = official and actual in {row["ticket1"], row["ticket2"]}
        raw.append(
            {
                **row,
                "official": official,
                "hit": hit,
                "return_yen": payout if hit else 0,
                "payout_yen": payout if hit else 0,
            }
        )
    return normalize_formal_settlement_rows(
        raw, investment_yen_per_bet=100, ticket_count=2
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default="2025-07-01")
    ap.add_argument("--end-date", default="2026-09-30")
    ap.add_argument("--opponent-artifact")
    ap.add_argument("--output", default="course-neutral-cohort-comparison.json")
    args = ap.parse_args()

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    overlay = load_overlay(args.opponent_artifact)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

        races, entries_by, course_rows, opp_rows = load_pre_result(
            conn, args.start_date, args.end_date
        )
        frozen = freeze_selection(races, entries_by, course_rows, opp_rows, overlay)
        canonical = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
        freeze_sha = hashlib.sha256(canonical).hexdigest()
        print(f"COURSE_COHORT_FROZEN_RACES={len(frozen)}", flush=True)
        print(f"COURSE_COHORT_FREEZE_SHA256={freeze_sha}", flush=True)
        print("COURSE_COHORT_SELECTION_OUTCOME_READ=0", flush=True)

        settled = settle(conn, frozen)
        conn.rollback()

    cohorts = {}
    for name in ("complete", "neutral_missing"):
        rows = [x for x in settled if x["course_cohort"] == name]
        cohorts[name] = forward_report(
            rows,
            unit_yen=100,
            bootstrap_samples=5000,
            bootstrap_seed=20261004,
        )

    result = {
        "contract": "V4_COURSE_COMPLETE_VS_NEUTRAL_MISSING_DIAGNOSTIC_V1",
        "period": [args.start_date, args.end_date],
        "selection": {
            "v4_daily_race_cap": 6,
            "top2_tickets": 2,
            "unit_yen": 100,
            "frozen_before_outcome_query": True,
            "freeze_sha256": freeze_sha,
        },
        "cohorts": cohorts,
        "safety": {
            "diagnostic_only": True,
            "threshold_tuning": False,
            "promotion_allowed": False,
            "database_write": False,
            "production_change": False,
            "odds_read": False,
        },
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for name in ("complete", "neutral_missing"):
        report = cohorts[name]
        print(
            "COURSE_COHORT_OVERALL="
            + json.dumps({"cohort": name, **report["overall"]}, sort_keys=True),
            flush=True,
        )
        print(
            "COURSE_COHORT_RISK="
            + json.dumps({"cohort": name, **report["risk"]}, sort_keys=True),
            flush=True,
        )
        print(
            "COURSE_COHORT_BOOTSTRAP="
            + json.dumps({"cohort": name, **report["day_bootstrap"]}, sort_keys=True),
            flush=True,
        )
    print("COURSE_COHORT_RESULT=PASS_DIAGNOSTIC_ONLY", flush=True)


if __name__ == "__main__":
    main()
