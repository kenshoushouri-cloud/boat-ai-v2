# -*- coding: utf-8 -*-
"""Lightweight V4 historical core readiness with a frozen Opponent overlay.

Measures only the matched-backtest core:
BASE + Motor2 + historical Course proxy + Opponent Pressure.

Opponent may come from:
1) valid DB provenance (historical102 or timing-clean forward-v2), or
2) a separately frozen strict-prior-only ephemeral reconstruction artifact.

The artifact is overlay-only: it never mutates or replaces database rows.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from research.historical_matched_contract_readiness_pg import (
    COURSE_PROXY_SOURCE,
    expected_course_snapshot,
    opponent_provenance,
)

OVERLAY_CONTRACT = "HISTORICAL_OPPONENT_EPHEMERAL_RECONSTRUCT_V1"


def load_overlay(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("contract") != OVERLAY_CONTRACT:
        raise ValueError("unexpected Opponent overlay contract")
    if payload.get("target_outcome_read") is not False:
        raise ValueError("Opponent overlay must be target-outcome blind")
    if payload.get("database_write") is not False:
        raise ValueError("Opponent overlay must be DB-write free")
    if payload.get("existing_rows_changed") is not False:
        raise ValueError("Opponent overlay must not change existing rows")
    if payload.get("production_change") is not False:
        raise ValueError("Opponent overlay must not change Production")

    out: dict[str, dict[str, Any]] = {}
    for raw in payload.get("rows") or []:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid Opponent overlay row")
        row = dict(raw)
        rid = str(row.get("race_id") or "")
        if not rid or rid in out:
            raise ValueError("duplicate/empty Opponent overlay race_id")
        if row.get("provenance") != "ephemeral_historical102_strict_prior_only":
            raise ValueError("unexpected Opponent overlay provenance")
        race_date = date.fromisoformat(str(row["race_date"]))
        train_end = date.fromisoformat(str(row["train_end"]))
        if train_end >= race_date:
            raise ValueError("Opponent overlay is not strict-prior-only")
        matched = row.get("matched_opponents")
        base = row.get("base_win")
        adj = row.get("adj_win")
        if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
            raise ValueError("Opponent overlay arrays must contain six lanes")
        if any(int(x) < 4 for x in matched):
            raise ValueError("Opponent overlay matched-opponent threshold failed")
        out[rid] = row
    return out


def audit(start_date: str, end_date: str, overlay_path: str | None) -> dict[str, Any]:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    overlay = load_overlay(overlay_path)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute(
                """
                with races as (
                  select race_id,race_date
                    from v2_races
                   where race_date between %s and %s
                ),
                ent as (
                  select e.race_id,
                         count(*) as entry_rows,
                         count(distinct e.lane) as lane_count,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.racer_number is not null
                             and nullif(trim(e.racer_class::text),'') is not null
                             and e.national_win_rate between 0 and 100
                             and e.national_place2_rate between 0 and 100
                             and e.local_place2_rate between 0 and 100
                             and e.avg_st is not null
                         ) as base_n,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.motor_place2_rate between 0 and 100
                         ) as motor_n
                    from v2_race_entries e
                    join races r using(race_id)
                   group by e.race_id
                ),
                course_proxy as (
                  select e.race_id,
                         count(distinct e.lane) filter(
                           where c.top3_rate between 0 and 100
                         ) as course_n
                    from v2_race_entries e
                    join races r using(race_id)
                    left join v2_racer_course_stats_snapshots c
                      on c.racer_number=e.racer_number
                     and c.course=e.lane
                     and c.source=%s
                     and c.snapshot_date=case
                         when r.race_date between date '2025-07-01' and date '2025-12-31'
                           then date '2025-04-30'
                         when r.race_date between date '2026-01-01' and date '2026-06-30'
                           then date '2025-10-31'
                         when r.race_date between date '2026-07-01' and date '2026-12-31'
                           then date '2026-04-30'
                         else null
                       end
                   where e.lane between 1 and 6
                   group by e.race_id
                )
                select r.race_id,r.race_date,
                       coalesce(ent.entry_rows,0) entry_rows,
                       coalesce(ent.lane_count,0) lane_count,
                       coalesce(ent.base_n,0) base_n,
                       coalesce(ent.motor_n,0) motor_n,
                       coalesce(course_proxy.course_n,0) course_n
                  from races r
                  left join ent using(race_id)
                  left join course_proxy using(race_id)
                 order by r.race_date,r.race_id
                """,
                (start_date, end_date, COURSE_PROXY_SOURCE),
            )
            races = [dict(x) for x in cur.fetchall()]

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
            opp_rows = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    db_opp = {str(x["race_id"]): opponent_provenance(x) for x in opp_rows}
    monthly: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "races": 0,
            "exact6_entries": 0,
            "v4_base6": 0,
            "motor6": 0,
            "course_proxy6": 0,
            "opponent_db_usable": 0,
            "opponent_overlay": 0,
            "opponent_usable": 0,
            "v4_core_ready": 0,
            "missing_base": 0,
            "missing_motor": 0,
            "missing_course": 0,
            "missing_opponent": 0,
        }
    )

    used_overlay: set[str] = set()
    for row in races:
        rid = str(row["race_id"])
        race_date = row["race_date"]
        if isinstance(race_date, str):
            race_date = date.fromisoformat(race_date)
        month = race_date.strftime("%Y-%m")
        m = monthly[month]
        m["races"] += 1

        exact6 = int(row["entry_rows"]) == 6 and int(row["lane_count"]) == 6
        base6 = exact6 and int(row["base_n"]) == 6
        motor6 = exact6 and int(row["motor_n"]) == 6
        course6 = (
            exact6
            and int(row["course_n"]) == 6
            and expected_course_snapshot(race_date) is not None
        )

        db_valid = db_opp.get(rid) is not None
        overlay_valid = (not db_valid) and rid in overlay
        if overlay_valid:
            used_overlay.add(rid)
        opponent_ok = db_valid or overlay_valid
        core_ready = base6 and motor6 and course6 and opponent_ok

        m["exact6_entries"] += int(exact6)
        m["v4_base6"] += int(base6)
        m["motor6"] += int(motor6)
        m["course_proxy6"] += int(course6)
        m["opponent_db_usable"] += int(db_valid)
        m["opponent_overlay"] += int(overlay_valid)
        m["opponent_usable"] += int(opponent_ok)
        m["v4_core_ready"] += int(core_ready)
        m["missing_base"] += int(not base6)
        m["missing_motor"] += int(not motor6)
        m["missing_course"] += int(not course6)
        m["missing_opponent"] += int(not opponent_ok)

    unknown_overlay = sorted(set(overlay) - {str(x["race_id"]) for x in races})
    if unknown_overlay:
        raise ValueError("Opponent overlay contains race_ids outside audit period")

    totals: dict[str, int] = defaultdict(int)
    months: list[dict[str, Any]] = []
    for month in sorted(monthly):
        row = {"month": month, **monthly[month]}
        denom = max(1, int(row["races"]))
        row["v4_core_ready_pct"] = round(100.0 * row["v4_core_ready"] / denom, 2)
        months.append(row)
        for key, value in monthly[month].items():
            totals[key] += int(value)

    denom = max(1, totals["races"])
    summary = dict(totals)
    summary["v4_core_ready_pct"] = round(
        100.0 * totals["v4_core_ready"] / denom, 2
    )
    summary["overlay_rows_loaded"] = len(overlay)
    summary["overlay_rows_used"] = len(used_overlay)

    return {
        "contract": "HISTORICAL_V4_CORE_READINESS_WITH_OPPONENT_OVERLAY_V1",
        "period": [start_date, end_date],
        "opponent_overlay_contract": OVERLAY_CONTRACT if overlay else None,
        "months": months,
        "totals": summary,
        "safety": {
            "transaction_read_only": True,
            "outcome_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "production_change": False,
            "overlay_only": True,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default="2025-07-01")
    ap.add_argument("--end-date", default="2026-09-30")
    ap.add_argument("--opponent-artifact")
    ap.add_argument("--output", default="historical-v4-core-readiness.json")
    args = ap.parse_args()

    payload = audit(args.start_date, args.end_date, args.opponent_artifact)
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for row in payload["months"]:
        print("V4_CORE_MONTH=" + json.dumps(row, sort_keys=True), flush=True)
    print(
        "V4_CORE_TOTALS=" + json.dumps(payload["totals"], sort_keys=True),
        flush=True,
    )
    print("V4_CORE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
