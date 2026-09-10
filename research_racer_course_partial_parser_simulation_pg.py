# -*- coding: utf-8 -*-
"""Read-only structural simulation for the partial racer-course parser.

Uses frozen DB inputs only to determine today's currently eligible racer×lane
pairs, then fetches the current official racer course page only for missing
racers and parses it with collect_racer_course_stats_pg.parse_course_stats.

IMPORTANT: current HTTP values are fetched after the frozen cutoff and are NOT
prediction eligible. They are used only to test parser structure, lane-position
preservation, and whether the Production distribution can be formed if the same
per-lane values had been captured at the approved PRE-time cutoff.

No DB writes, no LINE, no purchase/selection changes, no Production changes.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

import collect_racer_course_stats_pg as collector
import collect_racer_course_top3_forward_shadow_pg as fwd

WORKERS = 4


def _source_safe(row: Dict[str, Any]) -> bool:
    racer = fwd._si(row.get("racer_number"), 0)
    lane = fwd._si(row.get("lane"), 0)
    created = fwd._aware_jst(row.get("course_snapshot_created_at"))
    top3 = fwd._sf(row.get("course_top3_rate"))
    return (
        racer > 0
        and 1 <= lane <= 6
        and created is not None
        and created.date() == fwd.TARGET_DATE
        and created.time().replace(tzinfo=None) <= fwd.SOURCE_CUTOFF
        and str(row.get("course_source") or "") == "boatrace_official_racer_course"
        and top3 is not None
        and 0.0 <= top3 <= 100.0
    )


def _fetch_current_top3(racer_number: int) -> tuple[int, List[Optional[float]], str]:
    html = collector._fetch_html(racer_number)
    if not html:
        return racer_number, [], "no_html"
    rows, _debug = collector.parse_course_stats(html, racer_number)
    if len(rows) != 6:
        return racer_number, [], "parse_failed"
    values = [fwd._sf(row.get("top3_rate")) for row in rows]
    return racer_number, values, "ok"


def main() -> None:
    print("RACER_COURSE_PARTIAL_SIM_MODE=read_only_current_http_structural_simulation_not_prediction_eligible", flush=True)
    url = (fwd.os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = fwd._load(conn)

    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    missing_racers: set[int] = set()
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)
        if not _source_safe(row):
            racer = fwd._si(row.get("racer_number"), 0)
            if racer > 0:
                missing_racers.add(racer)

    current: Dict[int, List[Optional[float]]] = {}
    status_counts: Dict[str, int] = defaultdict(int)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_fetch_current_top3, racer): racer for racer in sorted(missing_racers)}
        for future in as_completed(futures):
            racer, values, status = future.result()
            status_counts[status] += 1
            if status == "ok" and len(values) == 6:
                current[racer] = values

    baseline_safe = 0
    simulated_safe = 0
    simulated_recovered = 0
    simulated_fallback = 0
    distribution_ok = 0
    invalid_cards = 0
    missing_pair_count = 0
    current_value_pair_count = 0
    venue_total: Dict[str, int] = defaultdict(int)
    venue_baseline: Dict[str, int] = defaultdict(int)
    venue_simulated: Dict[str, int] = defaultdict(int)

    for rid, raw_rows in sorted(by_race.items()):
        entries = sorted(raw_rows, key=lambda row: fwd._si(row.get("lane"), 0))
        venue = str(entries[0].get("venue") or "").zfill(2) if entries else "UNKNOWN"
        venue_total[venue] += 1
        if not fwd._valid_entries(entries):
            invalid_cards += 1
            continue

        baseline_ok = all(_source_safe(row) for row in entries)
        if baseline_ok:
            baseline_safe += 1
            simulated_safe += 1
            venue_baseline[venue] += 1
            venue_simulated[venue] += 1
            simulated_entries = entries
        else:
            simulated_entries = []
            recoverable = True
            for row in entries:
                copy = dict(row)
                if not _source_safe(row):
                    racer = fwd._si(row.get("racer_number"), 0)
                    lane = fwd._si(row.get("lane"), 0)
                    missing_pair_count += 1
                    values = current.get(racer, [])
                    value = values[lane - 1] if len(values) == 6 and 1 <= lane <= 6 else None
                    if value is None or not (0.0 <= value <= 100.0):
                        recoverable = False
                        break
                    current_value_pair_count += 1
                    copy["course_top3_rate"] = value
                simulated_entries.append(copy)

            if recoverable and len(simulated_entries) == 6:
                simulated_safe += 1
                simulated_recovered += 1
                venue_simulated[venue] += 1
            else:
                simulated_fallback += 1
                continue

        try:
            base = fwd._distribution(simulated_entries, venue, 0.0)
            course = fwd._distribution(simulated_entries, venue, fwd.FIXED_COEF)
            if (
                len(base) != 120
                or len(course) != 120
                or abs(sum(base.values()) - 1.0) > 1e-10
                or abs(sum(course.values()) - 1.0) > 1e-10
            ):
                raise RuntimeError("invalid distribution")
            distribution_ok += 1
        except Exception:
            pass

    total_races = len(by_race)
    baseline_pct = 100.0 * baseline_safe / total_races if total_races else 0.0
    simulated_pct = 100.0 * simulated_safe / total_races if total_races else 0.0

    print(
        f"RACER_COURSE_PARTIAL_SIM_HTTP=missing_racers:{len(missing_racers)} parsed:{len(current)} "
        f"ok:{status_counts.get('ok',0)} no_html:{status_counts.get('no_html',0)} parse_failed:{status_counts.get('parse_failed',0)}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PARTIAL_SIM_COVERAGE=races:{total_races} baseline_safe:{baseline_safe} baseline_pct:{baseline_pct:.2f} "
        f"simulated_safe:{simulated_safe} simulated_pct:{simulated_pct:.2f} recovered:{simulated_recovered} fallback:{simulated_fallback} "
        f"distribution_ok:{distribution_ok} invalid_cards:{invalid_cards}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PARTIAL_SIM_PAIRS=missing_pairs_seen:{missing_pair_count} current_value_pairs_used:{current_value_pair_count}",
        flush=True,
    )
    for venue in sorted(venue_total):
        total = venue_total[venue]
        base = venue_baseline.get(venue, 0)
        sim = venue_simulated.get(venue, 0)
        print(
            f"RACER_COURSE_PARTIAL_SIM_VENUE=venue:{venue} baseline:{base}/{total} simulated:{sim}/{total}",
            flush=True,
        )
    print("RACER_COURSE_PARTIAL_SIM_POLICY=current_http_values_are_after_cutoff_and_must_not_be_used_for_today_prediction", flush=True)
    print("RACER_COURSE_PARTIAL_SIM_PRODUCTION=NO_CHANGE_BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_PARTIAL_SIM_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RACER_COURSE_PARTIAL_SIM_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:500]}", flush=True)
        raise
