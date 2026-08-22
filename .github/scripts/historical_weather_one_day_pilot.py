# -*- coding: utf-8 -*-
"""Fixed-date historical weather repair pilot using already-stored raw text.

The historical weather rows already contain the official beforeinfo text in
`raw.text`. The original parser normalized Unicode with NFKC, which converts
`℃` to `°C`, but then searched only for `℃`; this left temperature columns
NULL even though the source text was stored.

This pilot therefore does not re-fetch BOAT RACE pages. It reparses the stored
historical raw text and fills only:
- v2_realtime_weather_snapshots.temperature_c
- v2_realtime_weather_snapshots.water_temperature_c

Safety:
- Date is hardcoded to 2025-07-01.
- snapshot_label is hardcoded to historical.
- Existing rows only: UPDATE, never INSERT/UPSERT.
- Existing non-null values are preserved with COALESCE.
- No exhibition/course/ST/tilt fields are read for writing or changed.
- No Production labels, predictions, decisions, Railway settings or LINE.
- Write mode requires CONFIRM_HISTORICAL_PILOT=YES.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict

import psycopg
from psycopg.rows import dict_row

PILOT_DATE = "2025-07-01"
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("HISTORICAL_PILOT_MODE", "audit").strip().lower()
CONFIRM = os.getenv("CONFIRM_HISTORICAL_PILOT", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
EXPECTED_RACES = 144


def norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip()


def safe_float(value: Any):
    try:
        if value in (None, ""):
            return None
        return float(norm(value).replace(",", ""))
    except Exception:
        return None


def parse_raw_weather(raw_text: str) -> Dict[str, float | None]:
    text = norm(raw_text)

    def labeled_number(label: str):
        match = re.search(
            rf"{label}[^0-9+\-]{{0,20}}([+\-]?\d+(?:\.\d+)?)\s*(?:℃|°\s*C)",
            text,
            flags=re.I,
        )
        return safe_float(match.group(1)) if match else None

    return {
        "temperature_c": labeled_number("気温"),
        "water_temperature_c": labeled_number("水温"),
    }


def fetch_all(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def audit_db(conn) -> Dict[str, int]:
    weather = fetch_all(
        conn,
        """
        select
          count(*)::int rows,
          count(distinct race_id)::int distinct_races,
          count(*) filter(where temperature_c is not null)::int temp,
          count(*) filter(where water_temperature_c is not null)::int water_temp,
          count(*) filter(where nullif(raw->>'text','') is not null)::int raw_text
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label=%s
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]
    nonhist = fetch_all(
        conn,
        """
        select count(*)::int n
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label<>%s
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]["n"]
    races = fetch_all(
        conn,
        "select count(*)::int n from v2_races where race_date=%s",
        (PILOT_DATE,),
    )[0]["n"]
    return {
        "races": int(races),
        "weather_rows": int(weather["rows"]),
        "distinct_races": int(weather["distinct_races"]),
        "temp": int(weather["temp"]),
        "water_temp": int(weather["water_temp"]),
        "raw_text": int(weather["raw_text"]),
        "nonhist_weather": int(nonhist),
    }


def print_db(prefix: str, row: Dict[str, int]) -> None:
    print(
        f"{prefix}_WEATHER=races:{row['races']} rows:{row['weather_rows']} "
        f"distinct:{row['distinct_races']} raw:{row['raw_text']} "
        f"temp:{row['temp']} water:{row['water_temp']}",
        flush=True,
    )
    print(f"{prefix}_NONHIST_WEATHER={row['nonhist_weather']}", flush=True)


def main() -> None:
    if MODE not in {"audit", "write"}:
        raise RuntimeError("HISTORICAL_PILOT_MODE must be audit or write")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if MODE == "write" and CONFIRM != "YES":
        raise RuntimeError("write mode requires CONFIRM_HISTORICAL_PILOT=YES")

    print(f"PILOT_DATE={PILOT_DATE}", flush=True)
    print(f"PILOT_MODE={MODE}", flush=True)
    print(f"PILOT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("PILOT_SOURCE=stored_raw_text", flush=True)
    print("PILOT_FIELDS=temperature_c,water_temperature_c", flush=True)

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=True,
    ) as conn:
        pre = audit_db(conn)
        source_rows = fetch_all(
            conn,
            """
            select race_id, raw->>'text' as raw_text
            from v2_realtime_weather_snapshots
            where race_date=%s and snapshot_label=%s
            order by race_id
            """,
            (PILOT_DATE, SNAPSHOT_LABEL),
        )

    parsed_rows = []
    parse_failed = 0
    sanity_failed = 0
    for row in source_rows:
        parsed = parse_raw_weather(row.get("raw_text") or "")
        temp = parsed.get("temperature_c")
        water = parsed.get("water_temperature_c")
        if temp is None or water is None:
            parse_failed += 1
            continue
        if not (-20.0 <= temp <= 45.0 and 0.0 <= water <= 40.0):
            sanity_failed += 1
            continue
        parsed_rows.append(
            {
                "race_id": str(row["race_id"]),
                "temperature_c": float(temp),
                "water_temperature_c": float(water),
            }
        )

    quality_ok = (
        pre["races"] == EXPECTED_RACES
        and pre["weather_rows"] == EXPECTED_RACES
        and pre["distinct_races"] == EXPECTED_RACES
        and pre["raw_text"] == EXPECTED_RACES
        and len(source_rows) == EXPECTED_RACES
        and len(parsed_rows) == EXPECTED_RACES
        and parse_failed == 0
        and sanity_failed == 0
    )

    print(f"PARSE_RAW_ROWS={len(source_rows)}/{EXPECTED_RACES}", flush=True)
    print(f"PARSE_WEATHER_USABLE={len(parsed_rows)}/{EXPECTED_RACES}", flush=True)
    print(f"PARSE_FAILED={parse_failed}", flush=True)
    print(f"PARSE_SANITY_FAILED={sanity_failed}", flush=True)
    print_db("PRE", pre)

    if not quality_ok:
        print("RESULT=FAIL_QUALITY_GATE", flush=True)
        raise SystemExit(2)

    if MODE == "audit":
        print("RESULT=PASS_AUDIT", flush=True)
        return

    updates = 0
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=True,
    ) as conn:
        before = audit_db(conn)
        if before != pre:
            raise RuntimeError("target-date weather snapshot changed between audit and write")

        with conn.transaction():
            with conn.cursor() as cur:
                for row in parsed_rows:
                    cur.execute(
                        """
                        update v2_realtime_weather_snapshots
                        set
                          temperature_c=coalesce(temperature_c,%s),
                          water_temperature_c=coalesce(water_temperature_c,%s),
                          updated_at=now()
                        where race_id=%s
                          and race_date=%s
                          and snapshot_label=%s
                          and (temperature_c is null or water_temperature_c is null)
                        """,
                        (
                            row["temperature_c"],
                            row["water_temperature_c"],
                            row["race_id"],
                            PILOT_DATE,
                            SNAPSHOT_LABEL,
                        ),
                    )
                    updates += max(cur.rowcount, 0)

            post_in_tx = audit_db(conn)
            if post_in_tx["weather_rows"] != pre["weather_rows"]:
                raise RuntimeError("historical weather row count changed unexpectedly")
            if post_in_tx["distinct_races"] != pre["distinct_races"]:
                raise RuntimeError("historical weather race set changed unexpectedly")
            if post_in_tx["temp"] != EXPECTED_RACES:
                raise RuntimeError("post-write temperature completeness failed")
            if post_in_tx["water_temp"] != EXPECTED_RACES:
                raise RuntimeError("post-write water-temperature completeness failed")
            if post_in_tx["raw_text"] != pre["raw_text"]:
                raise RuntimeError("historical raw text coverage changed unexpectedly")
            if post_in_tx["nonhist_weather"] != pre["nonhist_weather"]:
                raise RuntimeError("non-historical weather row count changed")

        post = audit_db(conn)

    print(f"WRITE_WEATHER_ROWS={updates}", flush=True)
    print_db("POST", post)
    print("RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    main()
