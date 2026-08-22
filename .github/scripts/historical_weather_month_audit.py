# -*- coding: utf-8 -*-
"""Read-only full-month audit for historical weather raw-text repair readiness.

This script intentionally supports one fixed month only: 2025-07.
It never writes to PostgreSQL. It verifies whether every base race has exactly
one historical weather snapshot with stored official raw text, then reparses
that raw text with the same parser used by the proven one-day repair pilot.

When parsing is incomplete, it emits only aggregate/public race diagnostics:
label presence and whether the same failed races have six result-entry rows.
No raw page text is published.

No HTTP requests, UPDATE/INSERT/DELETE, prediction logic, Railway settings, or
LINE operations are performed.
"""
from __future__ import annotations

import os
from collections import Counter
from datetime import date
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row

from historical_weather_one_day_pilot import norm, parse_raw_weather

AUDIT_MONTH = "2025-07"
MONTH_START = date(2025, 7, 1)
MONTH_END = date(2025, 8, 1)
SNAPSHOT_LABEL = "historical"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
MAX_EXPECTED_RACES = 10000


def fetch_all(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def safe_int(value: Any) -> int:
    return int(value or 0)


def compact_counter(counter: Counter[str]) -> str:
    return ",".join(f"{key}:{counter[key]}" for key in sorted(counter)) or "-"


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print(f"MONTH_AUDIT_MONTH={AUDIT_MONTH}", flush=True)
    print(f"MONTH_AUDIT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("MONTH_AUDIT_SOURCE=stored_raw_text", flush=True)
    print("MONTH_AUDIT_FIELDS=temperature_c,water_temperature_c", flush=True)
    print("MONTH_AUDIT_MODE=read_only", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        base = fetch_all(
            conn,
            """
            select count(*)::int as n
            from v2_races
            where race_date >= %s and race_date < %s
            """,
            (MONTH_START, MONTH_END),
        )[0]
        weather = fetch_all(
            conn,
            """
            select
              count(*)::int as rows,
              count(distinct race_id)::int as distinct_races,
              count(*) filter(where nullif(raw->>'text','') is not null)::int as raw_rows,
              count(*) filter(where temperature_c is not null)::int as temp_filled,
              count(*) filter(where water_temperature_c is not null)::int as water_filled,
              count(*) filter(where temperature_c is null)::int as temp_missing,
              count(*) filter(where water_temperature_c is null)::int as water_missing,
              count(*) filter(where temperature_c is null or water_temperature_c is null)::int as rows_needing_fill
            from v2_realtime_weather_snapshots
            where race_date >= %s and race_date < %s and snapshot_label=%s
            """,
            (MONTH_START, MONTH_END, SNAPSHOT_LABEL),
        )[0]
        source_rows = fetch_all(
            conn,
            """
            select race_id, raw->>'text' as raw_text,
                   temperature_c, water_temperature_c
            from v2_realtime_weather_snapshots
            where race_date >= %s and race_date < %s and snapshot_label=%s
            order by race_id
            """,
            (MONTH_START, MONTH_END, SNAPSHOT_LABEL),
        )

    expected = safe_int(base["n"])
    rows = safe_int(weather["rows"])
    distinct_races = safe_int(weather["distinct_races"])
    raw_rows = safe_int(weather["raw_rows"])
    temp_filled = safe_int(weather["temp_filled"])
    water_filled = safe_int(weather["water_filled"])
    temp_missing = safe_int(weather["temp_missing"])
    water_missing = safe_int(weather["water_missing"])
    rows_needing_fill = safe_int(weather["rows_needing_fill"])
    duplicate_rows = max(rows - distinct_races, 0)

    parse_usable = 0
    parse_failed = 0
    sanity_failed = 0
    reparsed_rows_needing_fill = 0
    reparsed_temp_missing = 0
    reparsed_water_missing = 0

    failed_race_ids: list[str] = []
    failed_temp_none = 0
    failed_water_none = 0
    failed_temp_label_present = 0
    failed_water_label_present = 0
    failed_both_labels_present = 0
    failed_degree_c_present = 0
    failed_by_date: Counter[str] = Counter()
    failed_by_venue: Counter[str] = Counter()

    for row in source_rows:
        race_id = str(row["race_id"])
        raw_text = row.get("raw_text") or ""
        parsed: Dict[str, float | None] = parse_raw_weather(raw_text)
        temp = parsed.get("temperature_c")
        water = parsed.get("water_temperature_c")
        if temp is None or water is None:
            parse_failed += 1
            failed_race_ids.append(race_id)
            text = norm(raw_text)
            has_temp = "気温" in text
            has_water = "水温" in text
            if temp is None:
                failed_temp_none += 1
            if water is None:
                failed_water_none += 1
            if has_temp:
                failed_temp_label_present += 1
            if has_water:
                failed_water_label_present += 1
            if has_temp and has_water:
                failed_both_labels_present += 1
            if "°C" in text or "℃" in text:
                failed_degree_c_present += 1
            parts = race_id.split("_")
            if len(parts) >= 3:
                failed_by_date[parts[0]] += 1
                failed_by_venue[parts[1]] += 1
            continue
        if not (-20.0 <= float(temp) <= 45.0 and 0.0 <= float(water) <= 40.0):
            sanity_failed += 1
            continue
        parse_usable += 1
        if row.get("temperature_c") is None or row.get("water_temperature_c") is None:
            reparsed_rows_needing_fill += 1
        if row.get("temperature_c") is None:
            reparsed_temp_missing += 1
        if row.get("water_temperature_c") is None:
            reparsed_water_missing += 1

    result6_by_race: dict[str, int] = {}
    if failed_race_ids:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
            result_counts = fetch_all(
                conn,
                """
                select race_id, count(*)::int as n
                from v2_result_entries
                where race_id = any(%s)
                group by race_id
                """,
                (failed_race_ids,),
            )
        result6_by_race = {
            str(row["race_id"]): safe_int(row["n"])
            for row in result_counts
        }

    failed_with_result6 = sum(
        1 for race_id in failed_race_ids if result6_by_race.get(race_id, 0) == 6
    )
    failed_without_result6 = len(failed_race_ids) - failed_with_result6

    print(f"EXPECTED_RACES={expected}", flush=True)
    print(f"HIST_WEATHER_ROWS={rows}", flush=True)
    print(f"HIST_DISTINCT_RACES={distinct_races}", flush=True)
    print(f"HIST_DUPLICATE_ROWS={duplicate_rows}", flush=True)
    print(f"RAW_ROWS={raw_rows}", flush=True)
    print(f"PARSE_USABLE={parse_usable}", flush=True)
    print(f"PARSE_FAILED={parse_failed}", flush=True)
    print(f"PARSE_SANITY_FAILED={sanity_failed}", flush=True)
    print(f"PRE_TEMP_FILLED={temp_filled}", flush=True)
    print(f"PRE_WATER_FILLED={water_filled}", flush=True)
    print(f"PRE_TEMP_MISSING={temp_missing}", flush=True)
    print(f"PRE_WATER_MISSING={water_missing}", flush=True)
    print(f"PRE_ROWS_NEEDING_FILL={rows_needing_fill}", flush=True)
    print(f"REPARSED_ROWS_NEEDING_FILL={reparsed_rows_needing_fill}", flush=True)
    print(f"REPARSED_TEMP_MISSING={reparsed_temp_missing}", flush=True)
    print(f"REPARSED_WATER_MISSING={reparsed_water_missing}", flush=True)
    print(f"FAILED_TEMP_NONE={failed_temp_none}", flush=True)
    print(f"FAILED_WATER_NONE={failed_water_none}", flush=True)
    print(f"FAILED_TEMP_LABEL_PRESENT={failed_temp_label_present}", flush=True)
    print(f"FAILED_WATER_LABEL_PRESENT={failed_water_label_present}", flush=True)
    print(f"FAILED_BOTH_LABELS_PRESENT={failed_both_labels_present}", flush=True)
    print(f"FAILED_DEGREE_C_PRESENT={failed_degree_c_present}", flush=True)
    print(f"FAILED_WITH_RESULT6={failed_with_result6}", flush=True)
    print(f"FAILED_WITHOUT_RESULT6={failed_without_result6}", flush=True)
    print(f"FAILED_BY_DATE={compact_counter(failed_by_date)}", flush=True)
    print(f"FAILED_BY_VENUE={compact_counter(failed_by_venue)}", flush=True)

    quality_ok = (
        1 <= expected <= MAX_EXPECTED_RACES
        and rows == expected
        and distinct_races == expected
        and duplicate_rows == 0
        and raw_rows == expected
        and len(source_rows) == expected
        and parse_usable == expected
        and parse_failed == 0
        and sanity_failed == 0
        and reparsed_rows_needing_fill == rows_needing_fill
        and reparsed_temp_missing == temp_missing
        and reparsed_water_missing == water_missing
    )

    if not quality_ok:
        print("RESULT=FAIL_QUALITY_GATE", flush=True)
        raise SystemExit(2)

    print("RESULT=PASS_MONTH_AUDIT", flush=True)


if __name__ == "__main__":
    main()
