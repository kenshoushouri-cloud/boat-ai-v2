# -*- coding: utf-8 -*-
"""Read-only audit of required racer x course coverage for one race date.

Unlike the legacy readiness audit, this script evaluates only the exact
(racer_number, snapshot_date, course=lane) row required by each entry. It does
not read results, derive coefficients, write to PostgreSQL, change Production,
or trigger LINE/purchase behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, time
import math
import os
from typing import Any, Iterable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
CUTOFF_TIME = time(8, 15)
DB = os.getenv("DATABASE_URL", "").strip()


def _finite_top3(value: Any) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and 0.0 <= x <= 100.0


def _lane_reason(row: dict[str, Any], cutoff: datetime) -> str:
    if row.get("snapshot_racer_number") is None:
        return "missing_required_row"
    if not _finite_top3(row.get("course_top3_rate")):
        return "missing_or_invalid_top3"
    created_at = row.get("snapshot_created_at")
    deadline_at = row.get("deadline_at")
    if created_at is None:
        return "missing_created_at"
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        return "naive_created_at"
    if created_at.astimezone(JST) > cutoff:
        return "created_after_0815"
    if deadline_at is None:
        return "missing_deadline"
    if deadline_at.tzinfo is None or deadline_at.utcoffset() is None:
        return "naive_deadline"
    if created_at >= deadline_at:
        return "created_at_or_after_deadline"
    return ""


def classify_required_coverage(rows: Iterable[dict[str, Any]], race_date: date) -> dict[str, Any]:
    """Classify exact required-row coverage without outcomes or imputation.

    Race readiness is fail-closed. Lane readiness is counted independently for
    all six lanes so a blocked race does not undercount later valid lanes.
    """
    cutoff = datetime.combine(race_date, CUTOFF_TIME, tzinfo=JST)
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_race[str(row["race_id"])].append(row)

    reasons: Counter[str] = Counter()
    lane_reasons: Counter[str] = Counter()
    blocked: list[tuple[str, str]] = []
    missing_required: list[tuple[str, int, int | None]] = []
    ready_races = 0
    total_lanes = 0
    ready_lanes = 0

    for race_id, race_rows in sorted(by_race.items()):
        total_lanes += len(race_rows)
        lanes = sorted(int(r.get("lane") or 0) for r in race_rows)
        race_reason = ""
        if len(race_rows) != 6 or lanes != [1, 2, 3, 4, 5, 6]:
            race_reason = "entries_not_exactly_6"
        else:
            for row in race_rows:
                lane_reason = _lane_reason(row, cutoff)
                if lane_reason:
                    lane_reasons[lane_reason] += 1
                    if not race_reason:
                        race_reason = lane_reason
                    if lane_reason == "missing_required_row":
                        racer_number = row.get("racer_number")
                        missing_required.append(
                            (
                                race_id,
                                int(row.get("lane") or 0),
                                int(racer_number) if racer_number is not None else None,
                            )
                        )
                else:
                    ready_lanes += 1
        if race_reason:
            reasons[race_reason] += 1
            blocked.append((race_id, race_reason))
        else:
            ready_races += 1

    return {
        "total_races": len(by_race),
        "ready_races": ready_races,
        "blocked_races": len(by_race) - ready_races,
        "total_lanes": total_lanes,
        "ready_lanes": ready_lanes,
        "reasons": reasons,
        "lane_reasons": lane_reasons,
        "blocked": blocked,
        "missing_required": missing_required,
    }


def _load_rows(race_date: date) -> list[dict[str, Any]]:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(DB, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute(
                """
                SELECT r.race_id,
                       r.deadline_at,
                       e.lane,
                       e.racer_number,
                       s.racer_number AS snapshot_racer_number,
                       s.course,
                       s.top3_rate AS course_top3_rate,
                       s.created_at AS snapshot_created_at
                  FROM v2_races r
                  JOIN v2_race_entries e ON e.race_id = r.race_id
                  LEFT JOIN v2_racer_course_stats_snapshots s
                    ON s.racer_number = e.racer_number
                   AND s.snapshot_date = r.race_date
                   AND s.course = e.lane
                 WHERE r.race_date = %s
                 ORDER BY r.race_id, e.lane
                """,
                (race_date,),
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows


def _print_result(prefix: str, race_date: date, result: dict[str, Any]) -> None:
    total = result["total_races"]
    ready = result["ready_races"]
    pct = (100.0 * ready / total) if total else 0.0
    print(f"{prefix}_DATE={race_date.isoformat()}", flush=True)
    print(
        f"{prefix}_RACES=target:{total} ready:{ready} blocked:{result['blocked_races']} ready_pct:{pct:.2f}",
        flush=True,
    )
    print(
        f"{prefix}_LANES=target:{result['total_lanes']} ready:{result['ready_lanes']} blocked:{result['total_lanes'] - result['ready_lanes']}",
        flush=True,
    )
    for reason, count in sorted(result["reasons"].items()):
        print(f"{prefix}_REASON={reason}:{count}", flush=True)
    for reason, count in sorted(result["lane_reasons"].items()):
        print(f"{prefix}_LANE_REASON={reason}:{count}", flush=True)
    missing = result["missing_required"]
    distinct_racers = {racer for _, _, racer in missing if racer is not None}
    print(
        f"{prefix}_MISSING_REQUIRED=lanes:{len(missing)} distinct_racers:{len(distinct_racers)}",
        flush=True,
    )
    for race_id, reason in result["blocked"]:
        print(f"{prefix}_BLOCKED=race_id:{race_id} reason:{reason}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--race-date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    race_date = date.fromisoformat(args.race_date)

    result = classify_required_coverage(_load_rows(race_date), race_date)
    print("RACER_COURSE_REQUIRED_MODE=read_only_exact_racer_course_no_results", flush=True)
    _print_result("RACER_COURSE_REQUIRED", race_date, result)
    print("RACER_COURSE_REQUIRED_RESULT=PASS_READ_ONLY", flush=True)

    # One-shot 2026-09-12 natural-run probe. The existing workflow still
    # reproduces 2026-09-11 and its fixed assertions; this adds a second
    # SELECT-only/rollback observation without changing the workflow or DB.
    if race_date == date(2026, 9, 11):
        probe_date = date(2026, 9, 12)
        probe = classify_required_coverage(_load_rows(probe_date), probe_date)
        print("RACER_COURSE_REQUIRED_PROBE_MODE=read_only_exact_racer_course_no_results", flush=True)
        _print_result("RACER_COURSE_REQUIRED_PROBE", probe_date, probe)
        print("RACER_COURSE_REQUIRED_PROBE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
