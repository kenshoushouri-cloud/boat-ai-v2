# -*- coding: utf-8 -*-
"""Fixed-date historical weather/tilt repair pilot.

The first broad pilot proved that historical temperature/water-temperature can
be parsed for every race on 2025-07-01, while start-exhibition course recovery
is not yet reliable enough for a write. This narrower pilot therefore changes
only three previously-null historical fields:

- v2_realtime_weather_snapshots.temperature_c
- v2_realtime_weather_snapshots.water_temperature_c
- v2_realtime_exhibition_snapshots.tilt

Safety:
- Date is hardcoded to 2025-07-01.
- snapshot_label is hardcoded to historical.
- Existing rows only: UPDATE, never INSERT/UPSERT.
- Existing non-null values are preserved with COALESCE.
- No course/ST/rank/raw/source fields are changed.
- No Production labels, predictions, decisions, Railway settings or LINE.
- Write mode requires CONFIRM_HISTORICAL_PILOT=YES.
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import historical_beforeinfo_parser_v3 as parser_v3  # noqa: E402

PILOT_DATE = "2025-07-01"
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("HISTORICAL_PILOT_MODE", "audit").strip().lower()
CONFIRM = os.getenv("CONFIRM_HISTORICAL_PILOT", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WORKERS = 4
TIMEOUT = 35
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
    """Parse temperature fields after NFKC safely.

    NFKC changes the compatibility character `℃` to `°C`, so both forms are
    accepted. This is the historical 0%-coverage defect isolated by the audit.
    """
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
                "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2-historical-pilot/1.1)"
            },
        )
        if response.status_code != 200:
            return {"race_id": rid, "status": f"HTTP_{response.status_code}"}
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text
        weather = parse_weather(html)
        exhibition = parser_v3.parse_exhibition(html)

        lanes = {int(row.get("lane") or 0) for row in exhibition}
        tilt_rows = [
            {
                "race_id": rid,
                "lane": int(row["lane"]),
                "tilt": safe_float(row.get("tilt")),
            }
            for row in exhibition
            if int(row.get("lane") or 0) in range(1, 7)
        ]
        tilt_complete = (
            len(tilt_rows) == 6
            and lanes == set(range(1, 7))
            and all(row["tilt"] is not None for row in tilt_rows)
        )

        courses = {int(row.get("exhibition_course") or 0) for row in exhibition}
        start_complete = (
            len(exhibition) == 6
            and sum(row.get("start_timing") is not None for row in exhibition) == 6
            and courses == set(range(1, 7))
        )
        course_changed = bool(
            start_complete
            and any(
                int(row.get("exhibition_course") or 0) != int(row.get("lane") or 0)
                for row in exhibition
            )
        )
        return {
            "race_id": rid,
            "status": "OK",
            "weather": weather,
            "tilt_rows": tilt_rows if tilt_complete else [],
            "tilt_complete": tilt_complete,
            "course_parse_complete": start_complete,
            "course_changed": course_changed,
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
    exhibition = fetch_all(
        conn,
        """
        select
          count(*)::int rows,
          count(*) filter(where tilt is not null)::int tilt,
          count(*) filter(where start_timing is not null)::int st,
          count(*) filter(
            where exhibition_course is not null and exhibition_course<>lane
          )::int changed
        from v2_realtime_exhibition_snapshots
        where race_date=%s and snapshot_label=%s
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]
    complete = fetch_all(
        conn,
        """
        select count(*)::int n
        from (
          select race_id
          from v2_realtime_exhibition_snapshots
          where race_date=%s and snapshot_label=%s
          group by race_id
          having count(distinct lane)=6
        ) x
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]["n"]
    nonhist_weather = fetch_all(
        conn,
        """
        select count(*)::int n
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label<>%s
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]["n"]
    nonhist_exhibition = fetch_all(
        conn,
        """
        select count(*)::int n
        from v2_realtime_exhibition_snapshots
        where race_date=%s and snapshot_label<>%s
        """,
        (PILOT_DATE, SNAPSHOT_LABEL),
    )[0]["n"]
    return {
        "weather_rows": int(weather["rows"]),
        "temp": int(weather["temp"]),
        "water_temp": int(weather["water_temp"]),
        "exhibition_rows": int(exhibition["rows"]),
        "tilt": int(exhibition["tilt"]),
        "st": int(exhibition["st"]),
        "changed": int(exhibition["changed"]),
        "exhibition_complete_races": int(complete),
        "nonhist_weather": int(nonhist_weather),
        "nonhist_exhibition": int(nonhist_exhibition),
    }


def print_db(prefix: str, row: Dict[str, int]) -> None:
    print(
        f"{prefix}_WEATHER=rows:{row['weather_rows']} temp:{row['temp']} "
        f"water:{row['water_temp']}",
        flush=True,
    )
    print(
        f"{prefix}_EXHIBITION=rows:{row['exhibition_rows']} "
        f"complete_races:{row['exhibition_complete_races']} tilt:{row['tilt']} "
        f"st:{row['st']} changed:{row['changed']}",
        flush=True,
    )
    print(
        f"{prefix}_NONHIST=weather:{row['nonhist_weather']} "
        f"exhibition:{row['nonhist_exhibition']}",
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
    print(f"PILOT_PARSER={parser_v3.VERSION}", flush=True)
    print("PILOT_FIELDS=temperature_c,water_temperature_c,tilt", flush=True)

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

    if not races:
        raise RuntimeError("pilot date has no races")

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_parse_one, race): str(race["race_id"]) for race in races}
        for future in as_completed(futures):
            results.append(future.result())

    total = len(races)
    http_ok = sum(result.get("status") == "OK" for result in results)
    errors = sum(result.get("status") == "ERROR" for result in results)
    weather_rows = []
    tilt_rows = []
    weather_usable = 0
    tilt_usable = 0
    course_parse_complete = 0
    course_changed = 0

    for result in results:
        if result.get("status") != "OK":
            continue
        weather = result["weather"]
        if (
            weather.get("temperature_c") is not None
            and weather.get("water_temperature_c") is not None
        ):
            weather_usable += 1
            weather_rows.append(
                {
                    "race_id": result["race_id"],
                    "temperature_c": weather["temperature_c"],
                    "water_temperature_c": weather["water_temperature_c"],
                }
            )
        if result.get("tilt_complete"):
            tilt_usable += 1
            tilt_rows.extend(result["tilt_rows"])
        if result.get("course_parse_complete"):
            course_parse_complete += 1
        if result.get("course_changed"):
            course_changed += 1

    expected_weather_rows = total
    expected_exhibition_rows = total * 6
    quality_ok = (
        total >= 12
        and http_ok == total
        and weather_usable == total
        and tilt_usable == total
        and len(weather_rows) == expected_weather_rows
        and len(tilt_rows) == expected_exhibition_rows
        and pre["weather_rows"] == expected_weather_rows
        and pre["exhibition_rows"] == expected_exhibition_rows
        and pre["exhibition_complete_races"] == total
    )

    print(f"PARSE_RACES={total}", flush=True)
    print(f"PARSE_HTTP_OK={http_ok}/{total}", flush=True)
    print(f"PARSE_WEATHER_USABLE={weather_usable}/{total}", flush=True)
    print(f"PARSE_TILT_USABLE={tilt_usable}/{total}", flush=True)
    print(f"PARSE_TILT_ROWS={len(tilt_rows)}/{expected_exhibition_rows}", flush=True)
    print(f"PARSE_COURSE_COMPLETE={course_parse_complete}/{total}", flush=True)
    print(f"PARSE_COURSE_CHANGED_RACES={course_changed}", flush=True)
    print(f"PARSE_ERRORS={errors}", flush=True)
    print_db("PRE", pre)

    if not quality_ok:
        print("RESULT=FAIL_QUALITY_GATE", flush=True)
        raise SystemExit(2)

    if MODE == "audit":
        print("RESULT=PASS_AUDIT", flush=True)
        return

    weather_updates = 0
    tilt_updates = 0
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        autocommit=True,
    ) as conn:
        before = audit_db(conn)
        if before != pre:
            raise RuntimeError("target-date snapshot changed between audit and write")

        with conn.transaction():
            with conn.cursor() as cur:
                for row in weather_rows:
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

                for row in tilt_rows:
                    cur.execute(
                        """
                        update v2_realtime_exhibition_snapshots
                        set tilt=coalesce(tilt,%s), updated_at=now()
                        where race_id=%s
                          and race_date=%s
                          and snapshot_label=%s
                          and lane=%s
                          and tilt is null
                        """,
                        (
                            row["tilt"],
                            row["race_id"],
                            PILOT_DATE,
                            SNAPSHOT_LABEL,
                            row["lane"],
                        ),
                    )
                    tilt_updates += max(cur.rowcount, 0)

            post_in_tx = audit_db(conn)
            if post_in_tx["temp"] != total:
                raise RuntimeError("post-write temperature completeness failed")
            if post_in_tx["water_temp"] != total:
                raise RuntimeError("post-write water-temperature completeness failed")
            if post_in_tx["tilt"] != expected_exhibition_rows:
                raise RuntimeError("post-write tilt completeness failed")
            if post_in_tx["st"] != pre["st"]:
                raise RuntimeError("start_timing changed unexpectedly")
            if post_in_tx["changed"] != pre["changed"]:
                raise RuntimeError("exhibition_course changed unexpectedly")
            if post_in_tx["nonhist_weather"] != pre["nonhist_weather"]:
                raise RuntimeError("non-historical weather row count changed")
            if post_in_tx["nonhist_exhibition"] != pre["nonhist_exhibition"]:
                raise RuntimeError("non-historical exhibition row count changed")

        post = audit_db(conn)

    print(f"WRITE_WEATHER_ROWS={weather_updates}", flush=True)
    print(f"WRITE_TILT_ROWS={tilt_updates}", flush=True)
    print_db("POST", post)
    print("RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    main()
