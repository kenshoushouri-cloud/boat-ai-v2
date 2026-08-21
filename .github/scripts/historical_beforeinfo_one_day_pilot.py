# -*- coding: utf-8 -*-
"""One-day historical beforeinfo repair pilot.

Safety properties:
- Fixed date: 2025-07-01 (not configurable).
- Fixed snapshot label: historical (not configurable).
- Only v2_realtime_weather_snapshots and v2_realtime_exhibition_snapshots.
- HTTP parse + DB reads happen before any write.
- Write mode requires CONFIRM_HISTORICAL_PILOT=YES.
- Production snapshot labels, prediction tables, decisions and LINE are untouched.
- Existing non-null values are preserved with COALESCE except exhibition_course,
  which is intentionally corrected from the validated v3 parser.
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import psycopg
import requests
from bs4 import BeautifulSoup
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import historical_beforeinfo_parser_v3 as parser_v3  # noqa: E402

PILOT_DATE = "2025-07-01"
SNAPSHOT_LABEL = "historical"
MODE = os.getenv("HISTORICAL_PILOT_MODE", "audit").strip().lower()
CONFIRM = os.getenv("CONFIRM_HISTORICAL_PILOT", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
JST = timezone(timedelta(hours=9))
WORKERS = 4
TIMEOUT = 35
MIN_HTTP_RATE = 0.95
MIN_WEATHER_RATE = 0.90
MIN_EXHIBITION_RATE = 0.90
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
    """Historical weather parser tolerant of NFKC Celsius normalization.

    U+2103 `℃` compatibility-normalizes to `°C` under NFKC. The old
    historical parser normalized the page first but then searched only for
    `℃`, which explains the observed 0% historical temperature coverage.
    """
    text = norm(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

    def labeled_number(label: str, unit_pattern: str):
        match = re.search(
            rf"{label}[^0-9+\-]{{0,20}}([+\-]?\d+(?:\.\d+)?)\s*(?:{unit_pattern})",
            text,
            flags=re.I,
        )
        return safe_float(match.group(1)) if match else None

    weather = next(
        (w for w in ("晴", "曇り", "曇", "くもり", "雨", "雪", "霧") if w in text),
        None,
    )
    wind_direction = next(
        (
            d
            for d in (
                "北東", "南東", "南西", "北西",
                "向い風", "追い風", "右横風", "左横風",
                "北", "東", "南", "西",
            )
            if d in text
        ),
        None,
    )
    return {
        "weather": weather,
        "temperature_c": labeled_number("気温", r"℃|°\s*C"),
        "water_temperature_c": labeled_number("水温", r"℃|°\s*C"),
        "wind_speed_m": labeled_number("風速", r"m"),
        "wind_direction": wind_direction,
        "wave_height_cm": labeled_number("波高", r"cm"),
        "raw_text": text[:4000],
    }


def fetch_all(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def official_url(venue: str, race_no: int) -> str:
    return f"{OFFICIAL}?rno={race_no}&jcd={venue.zfill(2)}&hd={PILOT_DATE.replace('-', '')}"


def fetch_parse_one(race: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    rid = str(race["race_id"])
    venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = int(race.get("race_no") or 0)
    try:
        response = requests.get(
            official_url(venue, race_no),
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2-historical-pilot/1.0)"},
        )
        if response.status_code != 200:
            return {"race_id": rid, "status": f"HTTP_{response.status_code}"}
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text
        weather = parse_weather(html)
        exhibition = parser_v3.parse_exhibition(html)

        entries_by_lane = {
            int(e.get("lane") or 0): e
            for e in entries
            if 1 <= int(e.get("lane") or 0) <= 6
        }
        now = datetime.now(JST).isoformat()
        weather_row = {
            "race_id": rid,
            "race_date": race.get("race_date"),
            "venue_id": venue,
            "venue_code": venue,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "snapshot_at": now,
            "source": "official_beforeinfo_historical_v3_pilot",
            "weather": weather.get("weather"),
            "temperature_c": weather.get("temperature_c"),
            "water_temperature_c": weather.get("water_temperature_c"),
            "wind_speed_m": weather.get("wind_speed_m"),
            "wind_direction": weather.get("wind_direction"),
            "wave_height_cm": weather.get("wave_height_cm"),
            "raw": {"text": weather.get("raw_text", "")},
            "updated_at": now,
        }

        exhibition_rows = []
        for row in exhibition:
            lane = int(row.get("lane") or 0)
            if lane not in range(1, 7):
                continue
            original_tilt = safe_float(entries_by_lane.get(lane, {}).get("tilt"))
            tilt = safe_float(row.get("tilt"))
            tilt_change = (
                round(tilt - original_tilt, 3)
                if tilt is not None and original_tilt is not None
                else None
            )
            exhibition_rows.append({
                "race_id": rid,
                "race_date": race.get("race_date"),
                "venue_id": venue,
                "venue_code": venue,
                "race_no": race_no,
                "snapshot_label": SNAPSHOT_LABEL,
                "snapshot_at": now,
                "source": "official_beforeinfo_historical_v3_pilot",
                "lane": lane,
                "exhibition_course": int(row.get("exhibition_course") or lane),
                "exhibition_time": row.get("exhibition_time"),
                "exhibition_time_rank": row.get("exhibition_time_rank"),
                "exhibition_time_diff": row.get("exhibition_time_diff"),
                "start_timing": row.get("start_timing"),
                "start_timing_rank": row.get("start_timing_rank"),
                "start_timing_diff": row.get("start_timing_diff"),
                "tilt": tilt,
                "original_tilt": original_tilt,
                "tilt_change": tilt_change,
                "raw": {"cells": row.get("raw_cells", [])},
                "updated_at": now,
            })
        return {
            "race_id": rid,
            "status": "OK",
            "weather_row": weather_row,
            "exhibition_rows": exhibition_rows,
        }
    except Exception as exc:
        return {
            "race_id": rid,
            "status": "ERROR",
            "error_type": type(exc).__name__,
        }


def audit_db(conn) -> Dict[str, int]:
    weather = fetch_all(
        conn,
        """
        select
          count(*)::int rows,
          count(*) filter(where temperature_c is not null)::int temp,
          count(*) filter(where water_temperature_c is not null)::int water_temp,
          count(*) filter(where wind_speed_m is not null)::int wind,
          count(*) filter(where wind_direction is not null and trim(wind_direction)<>'')::int wind_dir,
          count(*) filter(where wave_height_cm is not null)::int wave
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label='historical'
        """,
        (PILOT_DATE,),
    )[0]
    exhibition = fetch_all(
        conn,
        """
        select
          count(*)::int rows,
          count(*) filter(where tilt is not null)::int tilt,
          count(*) filter(where start_timing is not null)::int st,
          count(*) filter(where exhibition_course is not null and exhibition_course<>lane)::int changed
        from v2_realtime_exhibition_snapshots
        where race_date=%s and snapshot_label='historical'
        """,
        (PILOT_DATE,),
    )[0]
    complete = fetch_all(
        conn,
        """
        select count(*)::int n
        from (
          select race_id
          from v2_realtime_exhibition_snapshots
          where race_date=%s and snapshot_label='historical'
          group by race_id
          having count(distinct lane) filter(where exhibition_time is not null)=6
        ) x
        """,
        (PILOT_DATE,),
    )[0]["n"]
    nonhist_weather = fetch_all(
        conn,
        """
        select count(*)::int n
        from v2_realtime_weather_snapshots
        where race_date=%s and snapshot_label<>'historical'
        """,
        (PILOT_DATE,),
    )[0]["n"]
    nonhist_exhibition = fetch_all(
        conn,
        """
        select count(*)::int n
        from v2_realtime_exhibition_snapshots
        where race_date=%s and snapshot_label<>'historical'
        """,
        (PILOT_DATE,),
    )[0]["n"]
    return {
        "weather_rows": int(weather["rows"]),
        "temp": int(weather["temp"]),
        "water_temp": int(weather["water_temp"]),
        "wind": int(weather["wind"]),
        "wind_dir": int(weather["wind_dir"]),
        "wave": int(weather["wave"]),
        "exhibition_rows": int(exhibition["rows"]),
        "tilt": int(exhibition["tilt"]),
        "st": int(exhibition["st"]),
        "changed": int(exhibition["changed"]),
        "exhibition_complete_races": int(complete),
        "nonhist_weather": int(nonhist_weather),
        "nonhist_exhibition": int(nonhist_exhibition),
    }


def write_rows(conn, weather_rows, exhibition_rows) -> None:
    weather_sql = """
        insert into v2_realtime_weather_snapshots as current(
          race_id,race_date,venue_id,venue_code,race_no,snapshot_label,
          snapshot_at,source,weather,temperature_c,water_temperature_c,
          wind_speed_m,wind_direction,wave_height_cm,raw,updated_at
        ) values (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        on conflict(race_id,snapshot_label) do update set
          snapshot_at=excluded.snapshot_at,
          source=excluded.source,
          weather=coalesce(excluded.weather,current.weather),
          temperature_c=coalesce(excluded.temperature_c,current.temperature_c),
          water_temperature_c=coalesce(excluded.water_temperature_c,current.water_temperature_c),
          wind_speed_m=coalesce(excluded.wind_speed_m,current.wind_speed_m),
          wind_direction=coalesce(excluded.wind_direction,current.wind_direction),
          wave_height_cm=coalesce(excluded.wave_height_cm,current.wave_height_cm),
          raw=excluded.raw,
          updated_at=excluded.updated_at
    """
    exhibition_sql = """
        insert into v2_realtime_exhibition_snapshots as current(
          race_id,race_date,venue_id,venue_code,race_no,snapshot_label,
          snapshot_at,source,lane,exhibition_course,exhibition_time,
          exhibition_time_rank,exhibition_time_diff,start_timing,
          start_timing_rank,start_timing_diff,tilt,original_tilt,tilt_change,
          raw,updated_at
        ) values (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        on conflict(race_id,snapshot_label,lane) do update set
          snapshot_at=excluded.snapshot_at,
          source=excluded.source,
          exhibition_course=excluded.exhibition_course,
          exhibition_time=coalesce(excluded.exhibition_time,current.exhibition_time),
          exhibition_time_rank=coalesce(excluded.exhibition_time_rank,current.exhibition_time_rank),
          exhibition_time_diff=coalesce(excluded.exhibition_time_diff,current.exhibition_time_diff),
          start_timing=coalesce(excluded.start_timing,current.start_timing),
          start_timing_rank=coalesce(excluded.start_timing_rank,current.start_timing_rank),
          start_timing_diff=coalesce(excluded.start_timing_diff,current.start_timing_diff),
          tilt=coalesce(excluded.tilt,current.tilt),
          original_tilt=coalesce(excluded.original_tilt,current.original_tilt),
          tilt_change=coalesce(excluded.tilt_change,current.tilt_change),
          raw=excluded.raw,
          updated_at=excluded.updated_at
    """
    with conn.cursor() as cur:
        for row in weather_rows:
            cur.execute(
                weather_sql,
                (
                    row["race_id"], row["race_date"], row["venue_id"], row["venue_code"],
                    row["race_no"], row["snapshot_label"], row["snapshot_at"], row["source"],
                    row["weather"], row["temperature_c"], row["water_temperature_c"],
                    row["wind_speed_m"], row["wind_direction"], row["wave_height_cm"],
                    Jsonb(row["raw"]), row["updated_at"],
                ),
            )
        for row in exhibition_rows:
            cur.execute(
                exhibition_sql,
                (
                    row["race_id"], row["race_date"], row["venue_id"], row["venue_code"],
                    row["race_no"], row["snapshot_label"], row["snapshot_at"], row["source"],
                    row["lane"], row["exhibition_course"], row["exhibition_time"],
                    row["exhibition_time_rank"], row["exhibition_time_diff"], row["start_timing"],
                    row["start_timing_rank"], row["start_timing_diff"], row["tilt"],
                    row["original_tilt"], row["tilt_change"], Jsonb(row["raw"]), row["updated_at"],
                ),
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

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        races = fetch_all(
            conn,
            """
            select race_id,race_date,venue_id,venue_code,venue_name,race_no,race_name
            from v2_races
            where race_date=%s
            order by venue_id,race_no
            """,
            (PILOT_DATE,),
        )
        if not races:
            raise RuntimeError("pilot date has no races")
        race_ids = [str(r["race_id"]) for r in races]
        entries = fetch_all(
            conn,
            """
            select * from v2_race_entries
            where race_id = any(%s)
            order by race_id,lane
            """,
            (race_ids,),
        )
        entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
        for row in entries:
            entries_by_race.setdefault(str(row["race_id"]), []).append(row)
        pre = audit_db(conn)

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(fetch_parse_one, race, entries_by_race.get(str(race["race_id"]), [])): str(race["race_id"])
            for race in races
        }
        for future in as_completed(futures):
            results.append(future.result())

    total_races = len(races)
    http_ok = sum(r.get("status") == "OK" for r in results)
    weather_rows = []
    exhibition_rows = []
    weather_usable_races = 0
    exhibition_usable_races = 0
    course_changed_races = 0
    parse_errors = sum(r.get("status") == "ERROR" for r in results)

    for result in results:
        if result.get("status") != "OK":
            continue
        weather = result["weather_row"]
        if weather["temperature_c"] is not None and weather["water_temperature_c"] is not None:
            weather_usable_races += 1
            weather_rows.append(weather)

        rows = result["exhibition_rows"]
        lanes = {int(x["lane"]) for x in rows}
        courses = {int(x["exhibition_course"]) for x in rows}
        tilt_ok = len(rows) == 6 and sum(x["tilt"] is not None for x in rows) == 6
        st_ok = len(rows) == 6 and sum(x["start_timing"] is not None for x in rows) == 6
        permutation_ok = lanes == set(range(1, 7)) and courses == set(range(1, 7))
        if tilt_ok and st_ok and permutation_ok:
            exhibition_usable_races += 1
            exhibition_rows.extend(rows)
            if any(int(x["exhibition_course"]) != int(x["lane"]) for x in rows):
                course_changed_races += 1

    http_rate = http_ok / total_races
    weather_rate = weather_usable_races / max(http_ok, 1)
    exhibition_rate = exhibition_usable_races / max(http_ok, 1)
    quality_ok = (
        total_races >= 12
        and http_rate >= MIN_HTTP_RATE
        and weather_rate >= MIN_WEATHER_RATE
        and exhibition_rate >= MIN_EXHIBITION_RATE
        and all(x["snapshot_label"] == SNAPSHOT_LABEL for x in weather_rows)
        and all(x["snapshot_label"] == SNAPSHOT_LABEL for x in exhibition_rows)
        and len(exhibition_rows) == exhibition_usable_races * 6
    )

    print(f"PARSE_RACES={total_races}", flush=True)
    print(f"PARSE_HTTP_OK={http_ok} rate={http_rate:.3f}", flush=True)
    print(f"PARSE_WEATHER_USABLE={weather_usable_races} rate={weather_rate:.3f}", flush=True)
    print(f"PARSE_EXHIBITION_USABLE={exhibition_usable_races} rate={exhibition_rate:.3f}", flush=True)
    print(f"PARSE_COURSE_CHANGED_RACES={course_changed_races}", flush=True)
    print(f"PARSE_ERRORS={parse_errors}", flush=True)
    print(
        "PRE_WEATHER="
        f"rows:{pre['weather_rows']} temp:{pre['temp']} water:{pre['water_temp']} "
        f"wind:{pre['wind']} wind_dir:{pre['wind_dir']} wave:{pre['wave']}",
        flush=True,
    )
    print(
        "PRE_EXHIBITION="
        f"rows:{pre['exhibition_rows']} complete_races:{pre['exhibition_complete_races']} "
        f"tilt:{pre['tilt']} st:{pre['st']} changed:{pre['changed']}",
        flush=True,
    )
    print(
        f"PRE_NONHIST=weather:{pre['nonhist_weather']} exhibition:{pre['nonhist_exhibition']}",
        flush=True,
    )

    if not quality_ok:
        print("RESULT=FAIL_QUALITY_GATE", flush=True)
        raise SystemExit(2)

    if MODE == "audit":
        print("RESULT=PASS_AUDIT", flush=True)
        return

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        before = audit_db(conn)
        if before["nonhist_weather"] != pre["nonhist_weather"] or before["nonhist_exhibition"] != pre["nonhist_exhibition"]:
            raise RuntimeError("non-historical target-date rows changed during pilot preparation")
        with conn.transaction():
            write_rows(conn, weather_rows, exhibition_rows)
            post_in_tx = audit_db(conn)
            if post_in_tx["temp"] < weather_usable_races:
                raise RuntimeError("post-write temperature audit failed")
            if post_in_tx["water_temp"] < weather_usable_races:
                raise RuntimeError("post-write water-temperature audit failed")
            if post_in_tx["tilt"] < exhibition_usable_races * 6:
                raise RuntimeError("post-write tilt audit failed")
            if post_in_tx["nonhist_weather"] != before["nonhist_weather"]:
                raise RuntimeError("non-historical weather row count changed")
            if post_in_tx["nonhist_exhibition"] != before["nonhist_exhibition"]:
                raise RuntimeError("non-historical exhibition row count changed")
        post = audit_db(conn)

    print(f"WRITE_WEATHER_ROWS={len(weather_rows)}", flush=True)
    print(f"WRITE_EXHIBITION_ROWS={len(exhibition_rows)}", flush=True)
    print(
        "POST_WEATHER="
        f"rows:{post['weather_rows']} temp:{post['temp']} water:{post['water_temp']} "
        f"wind:{post['wind']} wind_dir:{post['wind_dir']} wave:{post['wave']}",
        flush=True,
    )
    print(
        "POST_EXHIBITION="
        f"rows:{post['exhibition_rows']} complete_races:{post['exhibition_complete_races']} "
        f"tilt:{post['tilt']} st:{post['st']} changed:{post['changed']}",
        flush=True,
    )
    print(
        f"POST_NONHIST=weather:{post['nonhist_weather']} exhibition:{post['nonhist_exhibition']}",
        flush=True,
    )
    print("RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    main()
