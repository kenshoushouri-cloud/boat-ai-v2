# -*- coding: utf-8 -*-
"""Read-only venue/date stability audit for Racer Course Top3 Forward Shadow.

Research-only helper. It imports the frozen health-report primitives, reads the
same shadow/result rows, and emits aggregate sign counts plus venue-level
metric deltas. It performs no database writes and makes no promotion decision.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row

import report_racer_course_top3_forward_health_pg as rpt


def _valid(row: Dict[str, Any]) -> bool:
    base = row.get("base_probs")
    course = row.get("course_probs")
    rates = row.get("course_top3_rates")
    snapshot_at = rpt._aware_jst(row.get("snapshot_at"))
    deadline = rpt._aware_jst(row.get("deadline_at"))
    return (
        int(row.get("model_version") or 0) == 1
        and abs(float(row.get("course_coef") or 0.0) - 0.50) < 1e-9
        and str(row.get("source_cutoff_jst") or "") == "08:15"
        and str(row.get("ticket_order_version") or "") == "lexicographic_lane_loop_120_fixed_v1"
        and isinstance(rates, list) and len(rates) == 6
        and all(0.0 <= float(x) <= 100.0 for x in rates)
        and isinstance(base, list) and len(base) == 120
        and isinstance(course, list) and len(course) == 120
        and snapshot_at is not None and deadline is not None and snapshot_at < deadline
        and float(row.get("minutes_before") or 0.0) >= 3.0
        and rpt._valid_source_times(row)
        and abs(sum(float(x) for x in base) - 1.0) <= 5e-5
        and abs(sum(float(x) for x in course) - 1.0) <= 5e-5
    )


def _deltas(stats: Dict[str, Dict[str, float]]) -> tuple[int, float, float, float]:
    base = stats["BASE"]
    course = stats["COURSE"]
    n = int(course["n"])
    return (
        n,
        rpt._mean(course, "ll") - rpt._mean(base, "ll"),
        rpt._mean(course, "br") - rpt._mean(base, "br"),
        rpt._mean(course, "rk") - rpt._mean(base, "rk"),
    )


def main() -> None:
    print(
        "RACER_COURSE_VENUE_HEALTH_MODE=read_only_research_stability_no_updates_no_production_no_line",
        flush=True,
    )
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = rpt._load(conn)
    if rows is None:
        print("RACER_COURSE_VENUE_HEALTH_RESULT=PASS_NO_TABLE", flush=True)
        return

    by_venue = defaultdict(lambda: {m: rpt._new() for m in ("BASE", "COURSE")})
    by_date = defaultdict(lambda: {m: rpt._new() for m in ("BASE", "COURSE")})
    invalid = pending = evaluated = 0

    for row in rows:
        if not _valid(row):
            invalid += 1
            continue
        official = (
            str(row.get("result_status") or "").lower() == "official"
            and str(row.get("race_status") or "").lower() == "official"
        )
        actual = str(row.get("trifecta_ticket") or "").strip()
        if not official or actual not in rpt.TICKET_INDEX:
            pending += 1
            continue

        venue = str(row.get("venue_id") or "UNKNOWN")
        d = str(row.get("race_date"))
        base = row["base_probs"]
        course = row["course_probs"]
        rpt._add(by_venue[venue]["BASE"], base, actual)
        rpt._add(by_venue[venue]["COURSE"], course, actual)
        rpt._add(by_date[d]["BASE"], base, actual)
        rpt._add(by_date[d]["COURSE"], course, actual)
        evaluated += 1

    venue_ll = venue_br = venue_rk = venue_all3 = 0
    for venue in sorted(by_venue):
        n, dll, dbr, drk = _deltas(by_venue[venue])
        ll_better = dll < 0.0
        br_better = dbr < 0.0
        rk_better = drk < 0.0
        venue_ll += int(ll_better)
        venue_br += int(br_better)
        venue_rk += int(rk_better)
        venue_all3 += int(ll_better and br_better and rk_better)
        print(
            f"RACER_COURSE_VENUE_HEALTH_SCOPE=VENUE:{venue} n:{n} "
            f"delta_ll:{dll:+.8f} delta_brier:{dbr:+.8f} delta_rank:{drk:+.4f} "
            f"all3_better:{int(ll_better and br_better and rk_better)}",
            flush=True,
        )

    date_ll = date_br = date_rk = date_all3 = 0
    for d in sorted(by_date):
        _, dll, dbr, drk = _deltas(by_date[d])
        ll_better = dll < 0.0
        br_better = dbr < 0.0
        rk_better = drk < 0.0
        date_ll += int(ll_better)
        date_br += int(br_better)
        date_rk += int(rk_better)
        date_all3 += int(ll_better and br_better and rk_better)

    print(
        f"RACER_COURSE_VENUE_HEALTH_COVERAGE=rows:{len(rows)} evaluated:{evaluated} pending:{pending} invalid:{invalid}",
        flush=True,
    )
    print(
        f"RACER_COURSE_VENUE_HEALTH_VENUE_SIGN_COUNT=venues:{len(by_venue)} "
        f"ll_better:{venue_ll} brier_better:{venue_br} rank_better:{venue_rk} all3_better:{venue_all3}",
        flush=True,
    )
    print(
        f"RACER_COURSE_VENUE_HEALTH_DATE_SIGN_COUNT=dates:{len(by_date)} "
        f"ll_better:{date_ll} brier_better:{date_br} rank_better:{date_rk} all3_better:{date_all3}",
        flush=True,
    )
    print("RACER_COURSE_VENUE_HEALTH_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_VENUE_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RACER_COURSE_VENUE_HEALTH_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",
            flush=True,
        )
        raise
