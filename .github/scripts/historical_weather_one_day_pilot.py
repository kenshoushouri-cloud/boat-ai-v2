# -*- coding: utf-8 -*-
"""Fixed-date historical weather repair pilot.

This is intentionally narrower than the earlier weather/tilt pilot. The live
read-only audit proved that temperature and water temperature can be recovered
for every race on 2025-07-01, while tilt is not yet reliable enough.

Write scope:
- v2_realtime_weather_snapshots.temperature_c
- v2_realtime_weather_snapshots.water_temperature_c

Safety:
- Date is hardcoded to 2025-07-01.
- snapshot_label is hardcoded to historical.
- Existing rows only: UPDATE, never INSERT/UPSERT.
- Existing non-null values are preserved with COALESCE.
- No exhibition/course/ST/tilt fields are changed.
- No Production labels, predictions, decisions, Railway settings or LINE.
- Write mode requires CONFIRM_HISTORICAL_PILOT=YES.
"""
from __future__ import annotations

import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.rows import dict_row

PILOT_DATE = "2025-07-01"
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("HISTORICAL_PILOT_MODE", "audit").strip().lower()
CONFIRM = os.getenv("CONFIRM_HISTORICAL_PILOT", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WORKERS = 4
TIMEOUT = 35
EXPECTED_RACES = 144
OFFICIAL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo"


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


def parse_weather(html: str) -> Dict[str, Any]:
    text = norm(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

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


def official_url(venue: str, race_no: int) -> str:
    hd = PILOT_DATE.replace("-", "")
    return f"{OFFICIAL}?rno={race_no}&jcd={venue.zfill(2)}&hd={hd}"


def fetch_parse_one(race: Dict[str, Any]) -> Dict[str, Any]:
    rid = str(race["race_id"])
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = int(race.get("race_no") or 0)
    try:
        response = requests.get(
            official_url(venue, race_no),
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2-historical-weather-pilot/1.0)"
            },
        )
        if response.status_code != 200:
            return {"race_id": rid, "status": f"HTTP_{response.status_code}"}
        response.encoding = response.apparent_encoding or "utf-8"
        weather = parse_weather(response.text)
        usable = (
            weather.get("temperature_c") is not None
            and weather.get("water_temperature_c") is not None
        )
        return {
            "race_id": rid,
            "status": "OK",
            "usable": usable,
            "temperature_c": weather.get("temperature_c"),
            "water_temperature_c": weather.get("water_temperature_c"),
        }
    except Exception as exc:
        return {
            "race_id": rid,
            "status": "ERROR",
            "error_type": type(exc).__name__,
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
          count(*) filter(where temperature_c is not null)::int temp,
          count(*) filter(where water_temperature_c is not null)::int water_temp
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
    return {
        "weather_rows": int(weather["rows"]),
        "temp": int(weather["temp"]),
        "water_temp": int(weather["water_temp"]),
        "nonhist_weather": int(nonhist),
    }


def print_db(prefix: str, row: Dict[str, int]) -> None:
    print(
        f"{prefix}_WEATHER=rows:{row['weather_rows']} temp:{row['temp']} "
        f"water:{row['water_temp']}",
        flush=True,
    )
    print(
        f"{prefix}_NONHIST_WEATHER={row['nonhist_weather']}",
        flush=True,
    )


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
    print("PILOT_FIELDS=temperature_c,water_temperature_c", flush=True)

    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=True,
    ) as conn:
        races = fetch_all(
            conn,
            """
            select race_id,race_date,venue_id,venue_code,race_no
            from v2_races
            where race_date=%s
            order by venue_id,race_no
            """,
            (PILOT_DATE,),
        )
        pre = audit_db(conn)

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_parse_one, race): str(race["race_id"]) for race in races}
        for future in as_completed(futures):
            results.append(future.result())

    total = len(races)
    http_ok = sum(result.get("status") == "OK" for result in results)
    errors = sum(result.get("status") == "ERROR" for result in results)
    usable_rows = [
        {
            "race_id": result["race_id"],
            "temperature_c": result["temperature_c"],
            "water_temperature_c": result["water_temperature_c"],
        }
        for result in results
        if result.get("status") == "OK" and result.get("usable")
    ]

    quality_ok = (
        total == EXPECTED_RACES
        and http_ok == EXPECTED_RACES
        and len(usable_rows) == EXPECTED_RACES
        and pre["weather_rows"] == EXPECTED_RACES
    )

    print(f"PARSE_RACES={total}/{EXPECTED_RACES}", flush=True)
    print(f"PARSE_HTTP_OK={http_ok}/{EXPECTED_RACES}", flush=True)
    print(f"PARSE_WEATHER_USABLE={len(usable_rows)}/{EXPECTED_RACES}", flush=True)
    print(f"PARSE_ERRORS={errors}", flush=True)
    print_db("PRE", pre)

    if not quality_ok:
        print("RESULT=FAIL_QUALITY_GATE", flush=True)
        raise SystemExit(2)

    if MODE == "audit":
        print("RESULT=PASS_AUDIT", flush=True)
        return

    weather_updates = 0
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
                for row in usable_rows:
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
                    weather_updates += max(cur.rowcount, 0)

            post_in_tx = audit_db(conn)
            if post_in_tx["weather_rows"] != pre["weather_rows"]:
                raise RuntimeError("historical weather row count changed unexpectedly")
            if post_in_tx["temp"] != EXPECTED_RACES:
                raise RuntimeError("post-write temperature completeness failed")
            if post_in_tx["water_temp"] != EXPECTED_RACES:
                raise RuntimeError("post-write water-temperature completeness failed")
            if post_in_tx["nonhist_weather"] != pre["nonhist_weather"]:
                raise RuntimeError("non-historical weather row count changed")

        post = audit_db(conn)

    print(f"WRITE_WEATHER_ROWS={weather_updates}", flush=True)
    print_db("POST", post)
    print("RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    main()
