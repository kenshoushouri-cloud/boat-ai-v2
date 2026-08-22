# -*- coding: utf-8 -*-
"""Read-only official-page recheck for July 2025 stored-raw weather gaps.

The full-month stored-raw audit identifies races whose stored historical raw
text cannot yield both air and water temperatures. This diagnostic re-fetches
only those failed public BOAT RACE historical beforeinfo pages and reports
aggregate recoverability. It never writes to PostgreSQL and never publishes raw
HTML/text or connection values.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any, Dict, Tuple

import os
import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.rows import dict_row

from historical_weather_one_day_pilot import norm, parse_raw_weather

MONTH_START = date(2025, 7, 1)
MONTH_END = date(2025, 8, 1)
SNAPSHOT_LABEL = "historical"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
OFFICIAL = "https://www.boatrace.jp/owpc/pc/race"
HTTP_TIMEOUT = 25
HTTP_RETRIES = 2
MAX_WORKERS = 3


def fetch_all(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def live_url(race_id: str) -> str:
    ds, venue, race_no = race_id.split("_")[:3]
    return f"{OFFICIAL}/beforeinfo?rno={int(race_no)}&jcd={venue}&hd={ds}"


def fetch_one(race_id: str) -> Tuple[str, str, Dict[str, float | None] | None]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; boat-ai-historical-gap-audit/1.0)",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
    last_error = ""
    for attempt in range(HTTP_RETRIES + 1):
        try:
            response = requests.get(live_url(race_id), headers=headers, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            text = norm(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True))
            return race_id, "ok", parse_raw_weather(text)
        except Exception as exc:
            last_error = type(exc).__name__
            if attempt < HTTP_RETRIES:
                time.sleep(0.8 * (attempt + 1))
    return race_id, f"error:{last_error}", None


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        source_rows = fetch_all(
            conn,
            """
            select race_id, raw->>'text' as raw_text
            from v2_realtime_weather_snapshots
            where race_date >= %s and race_date < %s and snapshot_label=%s
            order by race_id
            """,
            (MONTH_START, MONTH_END, SNAPSHOT_LABEL),
        )

    failed_ids: list[str] = []
    for row in source_rows:
        parsed = parse_raw_weather(row.get("raw_text") or "")
        if parsed.get("temperature_c") is None or parsed.get("water_temperature_c") is None:
            failed_ids.append(str(row["race_id"]))

    if not failed_ids:
        print("GAP_STORED_RAW_FAILED=0", flush=True)
        print("GAP_PROBE_RESULT=NO_GAPS", flush=True)
        return
    if len(failed_ids) > 500:
        raise RuntimeError("unexpectedly large stored-raw gap set")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        result_counts = fetch_all(
            conn,
            """
            select race_id, count(*)::int as n
            from v2_result_entries
            where race_id = any(%s)
            group by race_id
            """,
            (failed_ids,),
        )
    result6 = {str(row["race_id"]): int(row["n"] or 0) == 6 for row in result_counts}

    http_ok = 0
    http_failed = 0
    live_usable = 0
    live_parse_failed = 0
    live_sanity_failed = 0
    usable_with_result6 = 0
    usable_without_result6 = 0
    unusable_with_result6 = 0
    unusable_without_result6 = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_one, race_id): race_id for race_id in failed_ids}
        for future in as_completed(futures):
            race_id, status, parsed = future.result()
            has_result6 = result6.get(race_id, False)
            if status != "ok" or parsed is None:
                http_failed += 1
                continue
            http_ok += 1
            temp = parsed.get("temperature_c")
            water = parsed.get("water_temperature_c")
            if temp is None or water is None:
                live_parse_failed += 1
                if has_result6:
                    unusable_with_result6 += 1
                else:
                    unusable_without_result6 += 1
                continue
            if not (-20.0 <= float(temp) <= 45.0 and 0.0 <= float(water) <= 40.0):
                live_sanity_failed += 1
                if has_result6:
                    unusable_with_result6 += 1
                else:
                    unusable_without_result6 += 1
                continue
            live_usable += 1
            if has_result6:
                usable_with_result6 += 1
            else:
                usable_without_result6 += 1

    print(f"GAP_STORED_RAW_FAILED={len(failed_ids)}", flush=True)
    print(f"GAP_HTTP_OK={http_ok}", flush=True)
    print(f"GAP_HTTP_FAILED={http_failed}", flush=True)
    print(f"GAP_LIVE_USABLE={live_usable}", flush=True)
    print(f"GAP_LIVE_PARSE_FAILED={live_parse_failed}", flush=True)
    print(f"GAP_LIVE_SANITY_FAILED={live_sanity_failed}", flush=True)
    print(f"GAP_LIVE_USABLE_WITH_RESULT6={usable_with_result6}", flush=True)
    print(f"GAP_LIVE_USABLE_WITHOUT_RESULT6={usable_without_result6}", flush=True)
    print(f"GAP_LIVE_UNUSABLE_WITH_RESULT6={unusable_with_result6}", flush=True)
    print(f"GAP_LIVE_UNUSABLE_WITHOUT_RESULT6={unusable_without_result6}", flush=True)

    if http_failed:
        print("GAP_PROBE_RESULT=FAIL_HTTP", flush=True)
        raise SystemExit(2)
    print("GAP_PROBE_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
