# -*- coding: utf-8 -*-
"""Freeze the matched-contract V4/V5 selection set before outcome evaluation.

No results, payouts, odds, or database writes are read/performed here.

Shared comparison population:
- exactly six race-entry lanes;
- complete six-lane Motor2 values, because the frozen V5 overlay requires a
  six-lane within-race population z-score.

Course and Opponent follow the frozen V4 contract and are neutral when missing.
A frozen strict-prior Opponent artifact may fill only otherwise unusable DB
Opponent rows for historical selection.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research.historical_matched_contract_readiness_pg import opponent_provenance

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / ".github" / "scripts" / "candidate_discovery_v1_pg.py"
v1_spec = importlib.util.spec_from_file_location("candidate_v1_matched_freeze", V1_PATH)
v1 = importlib.util.module_from_spec(v1_spec)
assert v1_spec and v1_spec.loader
v1_spec.loader.exec_module(v1)

CONTRACT = "MATCHED_CONTRACT_SELECTION_FREEZE_V1"
OPP_OVERLAY_CONTRACT = "HISTORICAL_OPPONENT_EPHEMERAL_RECONSTRUCT_V1"
COURSE_SOURCE = "boatrace_official_k_applied_term_proxy"
ALL_LANES = {1, 2, 3, 4, 5, 6}
SPLITS = (
    ("TRAIN_REFERENCE", date(2025, 7, 1), date(2025, 12, 31)),
    ("VALIDATION", date(2026, 1, 1), date(2026, 6, 30)),
    ("OOS", date(2026, 7, 1), date(2026, 9, 30)),
)
COURSE_SNAPSHOTS = (
    (date(2025, 7, 1), date(2025, 12, 31), date(2025, 4, 30)),
    (date(2026, 1, 1), date(2026, 6, 30), date(2025, 10, 31)),
    (date(2026, 7, 1), date(2026, 9, 30), date(2026, 4, 30)),
)


def split_name(d: date) -> str:
    for name, start, end in SPLITS:
        if start <= d <= end:
            return name
    raise ValueError(f"date outside frozen split: {d}")


def expected_course_snapshot(d: date) -> date:
    for start, end, snap in COURSE_SNAPSHOTS:
        if start <= d <= end:
            return snap
    raise ValueError(f"date outside course terms: {d}")


def load_opponent_overlay(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("contract") != OPP_OVERLAY_CONTRACT:
        raise ValueError("unexpected Opponent overlay contract")
    required_false = (
        "target_outcome_read",
        "database_write",
        "existing_rows_changed",
        "production_change",
        "prospective_evidence",
    )
    for key in required_false:
        if payload.get(key) is not False:
            raise ValueError(f"unsafe Opponent overlay flag: {key}")

    out: dict[str, dict[str, Any]] = {}
    for raw in payload.get("rows") or []:
        row = dict(raw)
        rid = str(row.get("race_id") or "")
        if not rid or rid in out:
            raise ValueError("duplicate/empty Opponent overlay race_id")
        if row.get("provenance") != "ephemeral_historical102_strict_prior_only":
            raise ValueError("unexpected Opponent overlay provenance")
        rd = date.fromisoformat(str(row.get("race_date") or ""))
        te = date.fromisoformat(str(row.get("train_end") or ""))
        if te >= rd:
            raise ValueError("Opponent overlay is not strict-prior")
        out[rid] = row
    return out


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        value = _finite(row.get("motor_place2_rate"))
        if lane not in ALL_LANES or value is None or not 0.0 <= value <= 100.0:
            return {}
        out[lane] = value
    return out if set(out) == ALL_LANES else {}


def base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
    by_lane = {v1.si(row.get("lane"), 0): row for row in entries}
    if set(by_lane) != ALL_LANES:
        raise ValueError("exact six lanes required")
    return {
        lane: v1.lane_raw_strength(by_lane[lane], lane, venue, 0.0)
        for lane in range(1, 7)
    }


def course_map(
    entries: list[dict[str, Any]],
    race_date: date,
    course_rows: dict[tuple[int, date, int], float],
) -> dict[int, float]:
    snap = expected_course_snapshot(race_date)
    out: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        racer = v1.si(row.get("racer_number"), 0)
        value = course_rows.get((racer, snap, lane))
        if racer > 0 and lane in ALL_LANES and value is not None:
            out[lane] = value
    return out


def opponent_delta(row: dict[str, Any] | None) -> dict[int, float] | None:
    if not row:
        return None
    matched = row.get("matched_opponents")
    base = row.get("base_win")
    adj = row.get("adj_win")
    if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
        return None
    if any(int(x) < 4 for x in matched):
        return None
    out: dict[int, float] = {}
    for idx in range(6):
        b = _finite(base[idx])
        a = _finite(adj[idx])
        if b is None or a is None:
            return None
        out[idx + 1] = a - b
    return out


def motor_ticket_score(ticket: str, motor: dict[int, float]) -> float:
    if set(motor) != ALL_LANES:
        raise ValueError("V5 Motor2 overlay requires six lanes")
    xs = [motor[lane] for lane in range(1, 7)]
    mean = sum(xs) / 6.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / 6.0)
    z = {lane: 0.0 for lane in range(1, 7)}
    if sd >= 1e-12:
        z = {lane: (motor[lane] - mean) / sd for lane in range(1, 7)}
    a, b, c = (int(x) for x in ticket.split("-"))
    w = v4.MOTOR_POS_W
    return w[0] * z[a] + w[1] * z[b] + w[2] * z[c]


def load_inputs(
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
                 date '2025-04-30',
                 date '2025-10-31',
                 date '2026-04-30'
               )
               and course between 1 and 6
               and top3_rate between 0 and 100
            """,
            (COURSE_SOURCE,),
        )
        course_rows = {
            (int(x["racer_number"]), x["snapshot_date"], int(x["course"])): float(x["top3_rate"])
            for x in cur.fetchall()
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
        opp_rows = {str(x["race_id"]): dict(x) for x in cur.fetchall()}

    return races, entries_by, course_rows, opp_rows


def freeze_selection(
    races: list[dict[str, Any]],
    entries_by: dict[str, list[dict[str, Any]]],
    course_rows: dict[tuple[int, date, int], float],
    opp_rows: dict[str, dict[str, Any]],
    overlay: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_day: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    motor_by_race: dict[str, dict[int, float]] = {}
    meta: dict[str, dict[str, Any]] = {}

    total_races = 0
    exact6_races = 0
    shared_evaluable = 0
    rejected_motor = 0

    for race in races:
        total_races += 1
        rid = str(race["race_id"])
        entries = entries_by.get(rid, [])
        lanes = {v1.si(x.get("lane"), 0) for x in entries}
        if len(entries) != 6 or lanes != ALL_LANES:
            continue
        exact6_races += 1

        motor = motor_map(entries)
        if not motor:
            rejected_motor += 1
            continue

        rd = race["race_date"]
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        course = course_map(entries, rd, course_rows)

        db_opp = opp_rows.get(rid)
        delta = (
            opponent_delta(db_opp)
            if db_opp is not None and opponent_provenance(db_opp) is not None
            else None
        )
        opp_source = "neutral"
        if delta is not None:
            opp_source = "database"
        elif rid in overlay:
            delta = opponent_delta(overlay[rid])
            if delta is None:
                raise ValueError(f"invalid overlay payload for {rid}")
            opp_source = "ephemeral_overlay"

        probs = v4.build_v4_distribution(
            base_raw=base_raw(entries, venue),
            course_top3=course,
            motor_place2=motor,
            opponent_delta=delta,
        )
        day = rd.isoformat()
        by_day[day][rid] = probs
        motor_by_race[rid] = motor
        meta[rid] = {
            "race_id": rid,
            "race_date": day,
            "split": split_name(rd),
            "venue_id": venue,
            "race_no": int(race.get("race_no") or 0),
            "course_usable_lanes": len(course),
            "opponent_source": opp_source,
            "motor2_complete": True,
        }
        shared_evaluable += 1

    frozen_v4: list[dict[str, Any]] = []
    frozen_v5: list[dict[str, Any]] = []

    for day in sorted(by_day):
        selected = v4.select_daily(
            by_day[day],
            race_cap=v4.CORE_RACES,
            ticket_count=v4.CORE_TICKETS,
        )
        for row in selected:
            rid = str(row["race_id"])
            tickets = [str(x) for x in row["tickets"]]
            if len(tickets) != 2:
                raise RuntimeError("exact V4 TOP2 required")
            scores = [motor_ticket_score(t, motor_by_race[rid]) for t in tickets]
            base = {
                **meta[rid],
                "daily_rank": int(row["daily_race_rank"]),
                "race_score": round(float(row["race_score"]), 12),
                "tickets": tickets,
                "motor2_ticket_scores": [round(x, 12) for x in scores],
            }
            frozen_v4.append(base)
            if all(score > 0.0 for score in scores):
                frozen_v5.append(dict(base))

    by_split: dict[str, dict[str, Any]] = {}
    for name, start, end in SPLITS:
        days = sorted(
            {
                row["race_date"]
                for row in frozen_v4
                if row["split"] == name
            }
        )
        v4_rows = [x for x in frozen_v4 if x["split"] == name]
        v5_rows = [x for x in frozen_v5 if x["split"] == name]
        v5_days = sorted({x["race_date"] for x in v5_rows})
        by_split[name] = {
            "period": [start.isoformat(), end.isoformat()],
            "v4_selected_races": len(v4_rows),
            "v4_active_days": len(days),
            "v4_races_per_active_day": round(len(v4_rows) / len(days), 4) if days else None,
            "v5_selected_races": len(v5_rows),
            "v5_active_days": len(v5_days),
            "v5_races_per_active_day": round(len(v5_rows) / len(v5_days), 4) if v5_days else None,
        }

    return {
        "contract": CONTRACT,
        "period": [SPLITS[0][1].isoformat(), SPLITS[-1][2].isoformat()],
        "shared_population": {
            "total_races": total_races,
            "exact6_entry_races": exact6_races,
            "motor2_incomplete_rejected": rejected_motor,
            "shared_evaluable_races": shared_evaluable,
            "course_missing_policy": "neutral",
            "opponent_missing_policy": "neutral",
            "motor2_policy": "six_lane_required_for_shared_v5_overlay",
        },
        "by_split": by_split,
        "v4": {
            "contract": "V4",
            "daily_cap": v4.CORE_RACES,
            "tickets_per_race": v4.CORE_TICKETS,
            "selected_races": frozen_v4,
        },
        "v5": {
            "candidate_id": "V5_M2_TOP2_BOTH_POSITIVE_V1",
            "source": "frozen_v4_top2_only",
            "race_pass": "both_motor2_ticket_scores_gt_0",
            "selected_races": frozen_v5,
        },
        "selection_outcome_read": False,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
        "prospective_gate_credit": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default="2025-07-01")
    ap.add_argument("--end-date", default="2026-09-30")
    ap.add_argument("--opponent-artifact")
    ap.add_argument("--output", default="matched-contract-selection-freeze.json")
    args = ap.parse_args()

    overlay = load_opponent_overlay(args.opponent_artifact)
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        inputs = load_inputs(conn, args.start_date, args.end_date)
        payload = freeze_selection(*inputs, overlay)
        conn.rollback()

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    payload["freeze_sha256"] = digest

    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "MATCHED_SELECTION_POPULATION="
        + json.dumps(payload["shared_population"], sort_keys=True),
        flush=True,
    )
    for name, row in payload["by_split"].items():
        print(
            "MATCHED_SELECTION_SPLIT="
            + json.dumps({"split": name, **row}, sort_keys=True),
            flush=True,
        )
    print(f"MATCHED_SELECTION_V4_RACES={len(payload['v4']['selected_races'])}", flush=True)
    print(f"MATCHED_SELECTION_V5_RACES={len(payload['v5']['selected_races'])}", flush=True)
    print(f"MATCHED_SELECTION_FREEZE_SHA256={digest}", flush=True)
    print("MATCHED_SELECTION_OUTCOME_READ=0", flush=True)
    print("MATCHED_SELECTION_ODDS_READ=0", flush=True)
    print("MATCHED_SELECTION_DB_WRITE=0", flush=True)
    print("MATCHED_SELECTION_RESULT=PASS_FROZEN_PRE_OUTCOME", flush=True)


if __name__ == "__main__":
    main()
