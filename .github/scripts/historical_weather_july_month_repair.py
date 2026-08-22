# -*- coding: utf-8 -*-
"""Guarded July 2025 historical weather partial-month repair.

Modes:
- audit: read-only projection
- diagnose: execute the same set-based UPDATE path inside one transaction,
  verify all postconditions, then ALWAYS roll back
- write: execute and commit only after every guard passes

Only temperature_c and water_temperature_c NULL cells are eligible. Values are
parsed exclusively from each row's already-stored official historical raw.text.
The 51 source-gap races confirmed by the full-month audit and official-page
recheck remain NULL; no values are guessed or synthesized.

The transaction path stages repair values in a temporary table via PostgreSQL
COPY, then performs one UPDATE ... FROM join. This avoids thousands of
round-trips over the public database connection while preserving the same
transaction and postcondition guarantees.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row

from historical_weather_one_day_pilot import norm, parse_raw_weather
from historical_weather_month_audit import has_numeric_near_label

MONTH_START = date(2025, 7, 1)
MONTH_END = date(2025, 8, 1)
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("HISTORICAL_MONTH_MODE", "audit").strip().lower()
CONFIRM = os.getenv("CONFIRM_HISTORICAL_MONTH_WRITE", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

EXPECTED_RACES = 5196
EXPECTED_SOURCE_GAPS = 51
EXPECTED_ALREADY_FILLED_MIN = 144
EXPECTED_FINAL_FILLED = EXPECTED_RACES - EXPECTED_SOURCE_GAPS
CONFIRM_VALUE = "WRITE_2025_07_HISTORICAL_WEATHER_NULLS_ONLY"


def fetch_one(conn, sql: str, params=()) -> Dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row or {})


def fetch_all(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def counts(conn, label: str | None) -> Dict[str, int]:
    where_label = (
        "snapshot_label is distinct from %s"
        if label is None
        else "snapshot_label = %s"
    )
    row = fetch_one(
        conn,
        f"""
        select
          count(*)::int as rows,
          count(distinct race_id)::int as distinct_races,
          count(*) filter(where nullif(raw->>'text','') is not null)::int as raw_rows,
          count(*) filter(where temperature_c is not null)::int as temp_filled,
          count(*) filter(where water_temperature_c is not null)::int as water_filled,
          count(*) filter(where temperature_c is null)::int as temp_missing,
          count(*) filter(where water_temperature_c is null)::int as water_missing
        from v2_realtime_weather_snapshots
        where race_date >= %s and race_date < %s and {where_label}
        """,
        (MONTH_START, MONTH_END, SNAPSHOT_LABEL),
    )
    return {k: int(v or 0) for k, v in row.items()}


def base_races(conn) -> int:
    return int(
        fetch_one(
            conn,
            """
            select count(*)::int as n
            from v2_races
            where race_date >= %s and race_date < %s
            """,
            (MONTH_START, MONTH_END),
        ).get("n")
        or 0
    )


def is_confirmed_source_gap(raw_text: str, parsed: Dict[str, float | None]) -> bool:
    if parsed.get("temperature_c") is not None or parsed.get("water_temperature_c") is not None:
        return False
    text = norm(raw_text)
    has_temp = "気温" in text
    has_water = "水温" in text
    has_degree = "°C" in text or "℃" in text
    temp_numeric = has_temp and has_numeric_near_label(text, "気温")
    water_numeric = has_water and has_numeric_near_label(text, "水温")
    return (
        has_temp
        and has_water
        and not has_degree
        and not temp_numeric
        and not water_numeric
    )


def print_counts(prefix: str, row: Dict[str, int]) -> None:
    print(
        f"{prefix}_WEATHER="
        f"rows:{row['rows']} distinct:{row['distinct_races']} raw:{row['raw_rows']} "
        f"temp:{row['temp_filled']} water:{row['water_filled']} "
        f"temp_missing:{row['temp_missing']} water_missing:{row['water_missing']}",
        flush=True,
    )


def sqlstate(exc: Exception) -> str:
    value = getattr(exc, "sqlstate", None)
    return str(value or "-")[:32]


def run_transaction(
    repair_rows: list[tuple[float, float, str]],
    source_gap_ids: list[str],
    pre: Dict[str, int],
    pre_nonhist: Dict[str, int],
    *,
    commit: bool,
) -> None:
    phase = "connect"
    updated = 0
    staged = 0
    conn = None
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)

        phase = "pre_tx_counts"
        pre_tx = counts(conn, SNAPSHOT_LABEL)
        pre_nonhist_tx = counts(conn, None)
        if pre_tx != pre or pre_nonhist_tx != pre_nonhist:
            raise RuntimeError("database state changed between audit and transaction")

        phase = "create_temp_table"
        with conn.cursor() as cur:
            cur.execute(
                """
                create temporary table tmp_july_weather_repair(
                    race_id text primary key,
                    temperature_c double precision not null,
                    water_temperature_c double precision not null
                ) on commit drop
                """
            )

        phase = "copy_repair_rows"
        with conn.cursor() as cur:
            with cur.copy(
                "copy tmp_july_weather_repair "
                "(race_id,temperature_c,water_temperature_c) from stdin"
            ) as copy:
                for temp, water, race_id in repair_rows:
                    copy.write_row((race_id, temp, water))
                    staged += 1

        phase = "validate_staging"
        stage_count = int(
            fetch_one(
                conn,
                "select count(*)::int as n from tmp_july_weather_repair",
            ).get("n")
            or 0
        )
        if staged != len(repair_rows) or stage_count != len(repair_rows):
            raise RuntimeError("temporary repair staging count mismatch")
        print(f"STAGED_REPAIR_ROWS={stage_count}", flush=True)

        phase = "set_based_update"
        with conn.cursor() as cur:
            cur.execute(
                """
                update v2_realtime_weather_snapshots as w
                set temperature_c = coalesce(w.temperature_c, t.temperature_c),
                    water_temperature_c = coalesce(w.water_temperature_c, t.water_temperature_c)
                from tmp_july_weather_repair as t
                where w.race_id = t.race_id
                  and w.snapshot_label = %s
                  and w.race_date >= %s
                  and w.race_date < %s
                  and (w.temperature_c is null or w.water_temperature_c is null)
                """,
                (SNAPSHOT_LABEL, MONTH_START, MONTH_END),
            )
            updated = int(cur.rowcount or 0)
        print(f"SET_BASED_UPDATED_ROWS={updated}", flush=True)

        phase = "post_counts"
        post = counts(conn, SNAPSHOT_LABEL)
        post_nonhist = counts(conn, None)

        phase = "source_gap_postcheck"
        gap_post = fetch_one(
            conn,
            """
            select
              count(*)::int as rows,
              count(*) filter(where temperature_c is null)::int as temp_null,
              count(*) filter(where water_temperature_c is null)::int as water_null
            from v2_realtime_weather_snapshots
            where race_id = any(%s) and snapshot_label=%s
            """,
            (source_gap_ids, SNAPSHOT_LABEL),
        )
        gap_post = {k: int(v or 0) for k, v in gap_post.items()}

        phase = "postconditions"
        if updated != len(repair_rows):
            raise RuntimeError("updated row count did not match repair candidates")
        if post["rows"] != pre["rows"] or post["distinct_races"] != pre["distinct_races"]:
            raise RuntimeError("historical weather row/race count changed")
        if post["raw_rows"] != pre["raw_rows"]:
            raise RuntimeError("historical raw-text coverage changed")
        if post_nonhist != pre_nonhist:
            raise RuntimeError("nonhistorical weather counts changed")
        if post["temp_filled"] != EXPECTED_FINAL_FILLED:
            raise RuntimeError("temperature completeness postcondition failed")
        if post["water_filled"] != EXPECTED_FINAL_FILLED:
            raise RuntimeError("water-temperature completeness postcondition failed")
        if post["temp_missing"] != EXPECTED_SOURCE_GAPS:
            raise RuntimeError("temperature source-gap count changed unexpectedly")
        if post["water_missing"] != EXPECTED_SOURCE_GAPS:
            raise RuntimeError("water-temperature source-gap count changed unexpectedly")
        if gap_post != {
            "rows": EXPECTED_SOURCE_GAPS,
            "temp_null": EXPECTED_SOURCE_GAPS,
            "water_null": EXPECTED_SOURCE_GAPS,
        }:
            raise RuntimeError("confirmed source-gap rows were unexpectedly modified")

        print(f"WRITE_WEATHER_ROWS={updated}", flush=True)
        print_counts("POST", post)
        print_counts("POST_NONHIST", post_nonhist)

        if commit:
            phase = "commit"
            conn.commit()
            print("WRITE_TRANSACTION=COMMITTED", flush=True)
        else:
            phase = "diagnostic_rollback"
            conn.rollback()
            print("DIAG_TRANSACTION=ROLLED_BACK", flush=True)
            print("RESULT=PASS_MONTH_REPAIR_DIAGNOSTIC", flush=True)
    except Exception as exc:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        prefix = "DIAG" if MODE == "diagnose" else "WRITE"
        print(f"{prefix}_ERROR_PHASE={phase}", flush=True)
        print(f"{prefix}_ERROR_TYPE={type(exc).__name__}", flush=True)
        print(f"{prefix}_ERROR_SQLSTATE={sqlstate(exc)}", flush=True)
        print(f"{prefix}_STAGED_BEFORE_ERROR={staged}", flush=True)
        print(f"{prefix}_UPDATED_BEFORE_ERROR={updated}", flush=True)
        print(f"{prefix}_TRANSACTION=ROLLED_BACK", flush=True)
        print(
            f"RESULT=FAIL_MONTH_REPAIR_{'DIAGNOSTIC' if MODE == 'diagnose' else 'WRITE'}",
            flush=True,
        )
        raise
    finally:
        if conn is not None:
            conn.close()


def main() -> None:
    if MODE not in {"audit", "diagnose", "write"}:
        raise RuntimeError("HISTORICAL_MONTH_MODE must be audit, diagnose or write")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if MODE == "write" and CONFIRM != CONFIRM_VALUE:
        raise RuntimeError("explicit historical month write confirmation is required")

    print("MONTH_REPAIR_MONTH=2025-07", flush=True)
    print(f"MONTH_REPAIR_MODE={MODE}", flush=True)
    print(f"MONTH_REPAIR_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("MONTH_REPAIR_SOURCE=stored_raw_text", flush=True)
    print("MONTH_REPAIR_FIELDS=temperature_c,water_temperature_c", flush=True)
    print("MONTH_REPAIR_POLICY=null_only_source_gaps_remain_null", flush=True)
    print("MONTH_REPAIR_WRITE_STRATEGY=temp_table_copy_set_based_update", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        expected = base_races(conn)
        pre = counts(conn, SNAPSHOT_LABEL)
        pre_nonhist = counts(conn, None)
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

    source_by_id = {str(row["race_id"]): row for row in source_rows}
    repair_rows: list[tuple[float, float, str]] = []
    source_gap_ids: list[str] = []
    ambiguous_ids: list[str] = []
    sanity_failed = 0
    parse_usable = 0
    existing_preserved = 0

    for row in source_rows:
        race_id = str(row["race_id"])
        parsed: Dict[str, float | None] = parse_raw_weather(row.get("raw_text") or "")
        temp = parsed.get("temperature_c")
        water = parsed.get("water_temperature_c")

        if temp is None or water is None:
            if is_confirmed_source_gap(row.get("raw_text") or "", parsed):
                source_gap_ids.append(race_id)
            else:
                ambiguous_ids.append(race_id)
            continue

        if not (-20.0 <= float(temp) <= 45.0 and 0.0 <= float(water) <= 40.0):
            sanity_failed += 1
            continue

        parse_usable += 1
        if row.get("temperature_c") is None or row.get("water_temperature_c") is None:
            repair_rows.append((float(temp), float(water), race_id))
        else:
            existing_preserved += 1

    print(f"EXPECTED_RACES={expected}", flush=True)
    print_counts("PRE", pre)
    print_counts("PRE_NONHIST", pre_nonhist)
    print(f"PARSE_USABLE={parse_usable}", flush=True)
    print(f"SOURCE_GAPS={len(source_gap_ids)}", flush=True)
    print(f"AMBIGUOUS_PARSE_FAILURES={len(ambiguous_ids)}", flush=True)
    print(f"SANITY_FAILED={sanity_failed}", flush=True)
    print(f"REPAIR_CANDIDATES={len(repair_rows)}", flush=True)
    print(f"EXISTING_COMPLETE_PRESERVED={existing_preserved}", flush=True)

    gate_ok = (
        expected == EXPECTED_RACES
        and pre["rows"] == EXPECTED_RACES
        and pre["distinct_races"] == EXPECTED_RACES
        and pre["raw_rows"] == EXPECTED_RACES
        and len(source_rows) == EXPECTED_RACES
        and len(source_by_id) == EXPECTED_RACES
        and pre["temp_filled"] >= EXPECTED_ALREADY_FILLED_MIN
        and pre["water_filled"] >= EXPECTED_ALREADY_FILLED_MIN
        and len(source_gap_ids) == EXPECTED_SOURCE_GAPS
        and len(ambiguous_ids) == 0
        and sanity_failed == 0
        and parse_usable + len(source_gap_ids) == EXPECTED_RACES
        and len(repair_rows) + existing_preserved + len(source_gap_ids) == EXPECTED_RACES
    )
    if not gate_ok:
        print("RESULT=FAIL_PREWRITE_GATE", flush=True)
        raise SystemExit(2)

    if MODE == "audit":
        projected_temp = pre["temp_filled"] + sum(
            1
            for _, _, rid in repair_rows
            if source_by_id[rid].get("temperature_c") is None
        )
        projected_water = pre["water_filled"] + sum(
            1
            for _, _, rid in repair_rows
            if source_by_id[rid].get("water_temperature_c") is None
        )
        print(f"PROJECTED_TEMP_FILLED={projected_temp}", flush=True)
        print(f"PROJECTED_WATER_FILLED={projected_water}", flush=True)
        if projected_temp != EXPECTED_FINAL_FILLED or projected_water != EXPECTED_FINAL_FILLED:
            print("RESULT=FAIL_PROJECTED_POSTCONDITION", flush=True)
            raise SystemExit(3)
        print("RESULT=PASS_MONTH_REPAIR_AUDIT", flush=True)
        return

    run_transaction(
        repair_rows,
        source_gap_ids,
        pre,
        pre_nonhist,
        commit=(MODE == "write"),
    )
    if MODE == "write":
        print("RESULT=PASS_MONTH_REPAIR_WRITE", flush=True)


if __name__ == "__main__":
    main()
