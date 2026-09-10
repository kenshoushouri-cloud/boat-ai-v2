# -*- coding: utf-8 -*-
"""Read-only structural coverage audit for partial racer-course statistics.

This script estimates how many currently missing race-level Racer Course Top3
features could be supported if the official page parser preserved per-course
availability instead of rejecting a racer unless all six courses are numeric.

The HTTP fetch occurs at audit time and therefore MUST NOT be used as an
eligible frozen source for today's prediction. It is diagnostic only: no DB
writes, no Production/LINE/selection changes, and no promotion decision.
"""
from __future__ import annotations

import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
import psycopg
from psycopg.rows import dict_row

import collect_racer_course_top3_forward_shadow_pg as fwd

URL = "https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban={racer_number}"
TIMEOUT = 25
WORKERS = 4


def _parse_top3_by_course(html: str) -> List[Optional[float]]:
    soup = BeautifulSoup(html, "html.parser")
    tokens = [re.sub(r"\s+", " ", s).strip() for s in soup.stripped_strings]
    try:
        start = next(i for i, token in enumerate(tokens) if token == "コース別3連対率") + 1
        end = next(i for i in range(start, len(tokens)) if tokens[i] == "コース別平均スタートタイミング")
    except StopIteration:
        return []
    section = tokens[start:end]
    values: List[Optional[float]] = []
    pos = 0
    for lane in range(1, 7):
        lane_token = str(lane)
        found = None
        for i in range(pos, len(section)):
            if section[i] == lane_token:
                found = i
                break
        if found is None:
            return []
        value: Optional[float] = None
        next_pos = found + 1
        for j in range(found + 1, min(found + 6, len(section))):
            token = section[j]
            m = re.fullmatch(r"(\d{1,3}(?:\.\d+)?)\s*%", token)
            if m:
                value = float(m.group(1))
                next_pos = j + 1
                break
            if token in {"-", "--", "- -", "－－"}:
                value = None
                next_pos = j + 1
                break
            if token == str(lane + 1):
                break
        values.append(value)
        pos = next_pos
    return values if len(values) == 6 else []


def _fetch_one(racer_number: int) -> tuple[int, List[Optional[float]], str]:
    try:
        response = requests.get(
            URL.format(racer_number=racer_number),
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; boat-ai-readonly-partial-coverage/1.0)"},
        )
        if not response.ok:
            return racer_number, [], f"http_{response.status_code}"
        response.encoding = response.apparent_encoding or "utf-8"
        values = _parse_top3_by_course(response.text)
        return racer_number, values, "ok" if len(values) == 6 else "parse_failed"
    except Exception as exc:
        return racer_number, [], type(exc).__name__


def main() -> None:
    print("RACER_COURSE_PARTIAL_MODE=read_only_current_page_structural_diagnostic_not_frozen_source", flush=True)
    url = (fwd.os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        rows = fwd._load(conn)

    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    missing_needed_lanes: Dict[int, set[int]] = defaultdict(set)
    existing_safe: set[tuple[int, int]] = set()

    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)
        racer = fwd._si(row.get("racer_number"), 0)
        lane = fwd._si(row.get("lane"), 0)
        created = fwd._aware_jst(row.get("course_snapshot_created_at"))
        top3 = fwd._sf(row.get("course_top3_rate"))
        source_safe = (
            racer > 0 and 1 <= lane <= 6
            and created is not None
            and created.date() == fwd.TARGET_DATE
            and created.time().replace(tzinfo=None) <= fwd.SOURCE_CUTOFF
            and str(row.get("course_source") or "") == "boatrace_official_racer_course"
            and top3 is not None and 0.0 <= top3 <= 100.0
        )
        if source_safe:
            existing_safe.add((racer, lane))
        elif racer > 0 and 1 <= lane <= 6:
            missing_needed_lanes[racer].add(lane)

    fetched: Dict[int, List[Optional[float]]] = {}
    status_counts: Dict[str, int] = defaultdict(int)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_fetch_one, racer): racer for racer in sorted(missing_needed_lanes)}
        for future in as_completed(futures):
            racer, values, status = future.result()
            status_counts[status] += 1
            if len(values) == 6:
                fetched[racer] = values

    current_needed_pairs = 0
    current_available_pairs = 0
    racers_any_needed_available = 0
    racers_all_needed_available = 0
    racers_no_top3_any_course = 0
    for racer, lanes in missing_needed_lanes.items():
        values = fetched.get(racer, [])
        available_for_racer = 0
        any_course = bool(values) and any(v is not None for v in values)
        if not any_course:
            racers_no_top3_any_course += 1
        for lane in lanes:
            current_needed_pairs += 1
            if len(values) == 6 and values[lane - 1] is not None:
                current_available_pairs += 1
                available_for_racer += 1
        if available_for_racer > 0:
            racers_any_needed_available += 1
        if lanes and available_for_racer == len(lanes):
            racers_all_needed_available += 1

    unsafe_races = 0
    structurally_recoverable_now = 0
    still_unavailable_now = 0
    for raw_rows in by_race.values():
        missing_pairs: List[tuple[int, int]] = []
        for row in raw_rows:
            racer = fwd._si(row.get("racer_number"), 0)
            lane = fwd._si(row.get("lane"), 0)
            if (racer, lane) not in existing_safe:
                missing_pairs.append((racer, lane))
        if not missing_pairs:
            continue
        unsafe_races += 1
        recoverable = True
        for racer, lane in missing_pairs:
            values = fetched.get(racer, [])
            if len(values) != 6 or not (1 <= lane <= 6) or values[lane - 1] is None:
                recoverable = False
                break
        if recoverable:
            structurally_recoverable_now += 1
        else:
            still_unavailable_now += 1

    print(
        f"RACER_COURSE_PARTIAL_RACERS=missing_snapshot_racers:{len(missing_needed_lanes)} "
        f"page_parsed:{len(fetched)} fetch_ok:{status_counts.get('ok',0)} parse_failed:{status_counts.get('parse_failed',0)}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PARTIAL_NEEDED=missing_racer_lane_pairs:{current_needed_pairs} "
        f"current_page_lane_value_available:{current_available_pairs} "
        f"racers_any_needed_available:{racers_any_needed_available} racers_all_needed_available:{racers_all_needed_available} "
        f"racers_no_top3_any_course:{racers_no_top3_any_course}",
        flush=True,
    )
    print(
        f"RACER_COURSE_PARTIAL_RACE_RECOVERY=unsafe_races:{unsafe_races} "
        f"structurally_recoverable_now:{structurally_recoverable_now} still_unavailable_now:{still_unavailable_now}",
        flush=True,
    )
    print("RACER_COURSE_PARTIAL_CAUTION=current_http_values_are_after_frozen_cutoff_and_not_prediction_eligible", flush=True)
    print("RACER_COURSE_PARTIAL_PROMOTION=BLOCK_MANUAL_REVIEW_ONLY", flush=True)
    print("RACER_COURSE_PARTIAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RACER_COURSE_PARTIAL_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
