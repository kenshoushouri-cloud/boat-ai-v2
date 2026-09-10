# -*- coding: utf-8 -*-
"""Read-only Production-input readiness audit for Racer Course Top3.

Checks whether the frozen Forward feature can be computed from today's PRE-time
inputs without outcome or market data. No writes, notifications, selection, or
Production behavior changes are performed.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row

import collect_racer_course_top3_forward_shadow_pg as fwd


def _unsafe_reasons(entries: List[Dict[str, Any]], deadline: Any) -> set[str]:
    reasons: set[str] = set()
    for row in entries:
        created = fwd._aware_jst(row.get("course_snapshot_created_at"))
        if created is None:
            reasons.add("missing_snapshot")
            continue
        if created.date() != fwd.TARGET_DATE:
            reasons.add("wrong_snapshot_date")
        if created.time().replace(tzinfo=None) > fwd.SOURCE_CUTOFF:
            reasons.add("after_0815")
        if created >= deadline:
            reasons.add("not_before_deadline")
        if str(row.get("course_source") or "") != "boatrace_official_racer_course":
            reasons.add("wrong_source")
        x = fwd._sf(row.get("course_top3_rate"))
        if x is None or not (0.0 <= x <= 100.0):
            reasons.add("invalid_top3")
    return reasons


def main() -> None:
    print("RACER_COURSE_PROD_READY_MODE=read_only_inputs_only_no_odds_no_results_no_updates_no_line", flush=True)
    url = (fwd.os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = fwd._load(conn)

    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)

    entry_racers: set[int] = set()
    safe_snapshot_racers: set[int] = set()
    for row in rows:
        racer_number = fwd._si(row.get("racer_number"), 0)
        if racer_number > 0:
            entry_racers.add(racer_number)
        created = fwd._aware_jst(row.get("course_snapshot_created_at"))
        top3 = fwd._sf(row.get("course_top3_rate"))
        if (
            racer_number > 0
            and created is not None
            and created.date() == fwd.TARGET_DATE
            and created.time().replace(tzinfo=None) <= fwd.SOURCE_CUTOFF
            and str(row.get("course_source") or "") == "boatrace_official_racer_course"
            and top3 is not None and 0.0 <= top3 <= 100.0
        ):
            safe_snapshot_racers.add(racer_number)
    missing_racers = entry_racers - safe_snapshot_racers

    total_races = len(by_race)
    full6_cards = 0
    source_full6 = 0
    distribution_ok = 0
    invalid_card = 0
    deadline_missing = 0
    source_not_safe = 0
    degenerate_or_distribution_error = 0
    lead_ge3_at_source = 0
    deltas: List[float] = []
    source_leads: List[float] = []
    reason_counts: Dict[str, int] = defaultdict(int)
    venue_total: Dict[str, int] = defaultdict(int)
    venue_safe: Dict[str, int] = defaultdict(int)

    for rid, raw_rows in sorted(by_race.items()):
        entries = sorted(raw_rows, key=lambda x: fwd._si(x.get("lane")))
        venue = str(entries[0].get("venue") or "").zfill(2) if entries else "UNKNOWN"
        venue_total[venue] += 1
        if not fwd._valid_entries(entries):
            invalid_card += 1
            continue
        full6_cards += 1

        deadline = fwd._aware_jst(entries[0].get("deadline_at"))
        if deadline is None:
            deadline_missing += 1
            continue

        reasons = _unsafe_reasons(entries, deadline)
        if reasons:
            source_not_safe += 1
            for reason in reasons:
                reason_counts[reason] += 1
            continue
        source_full6 += 1
        venue_safe[venue] += 1

        latest_source = max(fwd._aware_jst(e.get("course_snapshot_created_at")) for e in entries)
        if latest_source is not None:
            lead = (deadline - latest_source).total_seconds() / 60.0
            source_leads.append(lead)
            if lead >= fwd.MIN_LEAD_MINUTES:
                lead_ge3_at_source += 1

        try:
            base = fwd._distribution(entries, venue, 0.0)
            course = fwd._distribution(entries, venue, fwd.FIXED_COEF)
            if (
                len(base) != 120
                or len(course) != 120
                or abs(sum(base.values()) - 1.0) > 1e-10
                or abs(sum(course.values()) - 1.0) > 1e-10
            ):
                raise RuntimeError("invalid distribution")
            deltas.append(max(abs(base[t] - course[t]) for t in fwd.TICKETS))
            distribution_ok += 1
        except Exception:
            degenerate_or_distribution_error += 1

    max_delta = max(deltas) if deltas else 0.0
    median_delta = median(deltas) if deltas else 0.0
    min_source_lead = min(source_leads) if source_leads else 0.0
    median_source_lead = median(source_leads) if source_leads else 0.0
    coverage_pct = (100.0 * source_full6 / total_races) if total_races else 0.0
    racer_coverage_pct = (100.0 * len(safe_snapshot_racers) / len(entry_racers)) if entry_racers else 0.0

    venue_rates = []
    for venue in sorted(venue_total):
        total = venue_total[venue]
        safe = venue_safe.get(venue, 0)
        pct = (100.0 * safe / total) if total else 0.0
        venue_rates.append((pct, venue, safe, total))
        print(
            f"RACER_COURSE_PROD_READY_VENUE=venue:{venue} safe:{safe} total:{total} pct:{pct:.2f}",
            flush=True,
        )

    print(f"RACER_COURSE_PROD_READY_DATE={fwd.TARGET_DATE}", flush=True)
    print(
        f"RACER_COURSE_PROD_READY_RACERS=entry_unique:{len(entry_racers)} safe_snapshot_unique:{len(safe_snapshot_racers)} "
        f"missing_snapshot_unique:{len(missing_racers)} safe_pct:{racer_coverage_pct:.2f}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PROD_READY_COVERAGE=races:{total_races} full6_cards:{full6_cards} "
        f"source_safe_full6:{source_full6} source_safe_pct:{coverage_pct:.2f} distribution_ok:{distribution_ok} "
        f"lead_ge3_at_source:{lead_ge3_at_source}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PROD_READY_SKIPS=invalid_card:{invalid_card} deadline_missing:{deadline_missing} "
        f"source_not_safe:{source_not_safe} distribution_error:{degenerate_or_distribution_error}",
        flush=True,
    )
    print(
        "RACER_COURSE_PROD_READY_UNSAFE_REASONS="
        + " ".join(f"{k}:{reason_counts.get(k,0)}" for k in (
            "missing_snapshot", "wrong_snapshot_date", "after_0815", "not_before_deadline", "wrong_source", "invalid_top3"
        )),
        flush=True,
    )
    if venue_rates:
        lowest = min(venue_rates)
        highest = max(venue_rates)
        print(
            f"RACER_COURSE_PROD_READY_VENUE_RANGE=min:{lowest[1]}:{lowest[0]:.2f}%({lowest[2]}/{lowest[3]}) "
            f"max:{highest[1]}:{highest[0]:.2f}%({highest[2]}/{highest[3]})",
            flush=True,
        )
    print(
        f"RACER_COURSE_PROD_READY_SOURCE_LEAD_MINUTES=min:{min_source_lead:.2f} median:{median_source_lead:.2f}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PROD_READY_PROB_CHANGE=max_abs_median:{median_delta:.10f} max_abs_max:{max_delta:.10f}",
        flush=True,
    )
    print("RACER_COURSE_PROD_READY_POLICY=FALLBACK_TO_CURRENT_V24_IF_FEATURE_INPUT_NOT_SAFE", flush=True)
    print("RACER_COURSE_PROD_READY_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_PROD_READY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RACER_COURSE_PROD_READY_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",
            flush=True,
        )
        raise
