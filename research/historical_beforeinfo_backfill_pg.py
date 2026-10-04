# -*- coding: utf-8 -*-
"""Historical BOAT RACE official beforeinfo backfill.

User-approved historical truth rule:
- archived target-race pre-race/beforeinfo values are treated as pre-deadline
  historical truth;
- exact original fetch timestamp is unknown, therefore snapshot_at is a
  synthetic pre-deadline boundary and this fact is recorded in raw metadata;
- historical reconstruction is never counted as prospective evidence.

Writes only snapshot_label='historical' rows in:
- v2_realtime_exhibition_snapshots
- v2_realtime_weather_snapshots

Existing non-null values are preserved. Missing fields/lanes may be filled.
No results, odds or payouts are read.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import requests
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import v21_realtime_collector_pg as rt


JST = ZoneInfo("Asia/Tokyo")
SNAPSHOT_LABEL = "historical"
SOURCE = "official_archived_beforeinfo_historical_reconstruction"
SOURCE_CONTRACT = "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
WRITE_CONFIRM = "YES"
DEFAULT_SLEEP_SEC = 0.50
USER_AGENT = "boat-ai-v2-historical-beforeinfo-backfill/1.0"
MODE_GENERIC = "generic"
MODE_EXHIBITION_TIME_ONLY = "exhibition-time-only"
MODES = (MODE_GENERIC, MODE_EXHIBITION_TIME_ONLY)


def _date_range(start_date: str, end_date: str) -> list[str]:
    a = date.fromisoformat(start_date)
    b = date.fromisoformat(end_date)
    if b < a:
        raise ValueError("end before start")
    out: list[str] = []
    cur = a
    while cur <= b:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _deadline(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.astimezone(JST)


def _synthetic_snapshot_at(deadline_at: datetime | None, race_date: str) -> datetime:
    if deadline_at is not None:
        return deadline_at - timedelta(seconds=1)
    d = date.fromisoformat(race_date)
    # Fallback is intentionally conservative and explicitly synthetic.
    return datetime(d.year, d.month, d.day, 0, 0, tzinfo=JST)


def _fetch(session: requests.Session, url: str, sleep_sec: float) -> str | None:
    if sleep_sec > 0:
        time.sleep(sleep_sec)
    try:
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=30,
        )
    except requests.RequestException:
        return None
    if response.status_code == 404:
        return None
    if not response.ok:
        return None
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _target_races(
    conn: psycopg.Connection,
    target_date: str,
    *,
    mode: str = MODE_GENERIC,
) -> list[dict[str, Any]]:
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")

    if mode == MODE_EXHIBITION_TIME_ONLY:
        with conn.cursor() as cur:
            cur.execute(
                """
                with ex as (
                  select race_id,
                         count(*) filter(
                           where snapshot_label='historical'
                         ) as row_count,
                         count(*) filter(
                           where snapshot_label='historical'
                             and exhibition_time is not null
                         ) as time_count
                    from v2_realtime_exhibition_snapshots
                   group by race_id
                )
                select r.race_id,
                       r.race_date,
                       coalesce(r.venue_id,r.venue_code) as venue_id,
                       r.race_no,
                       r.deadline_at,
                       coalesce(ex.row_count,0) as ex_rows,
                       coalesce(ex.time_count,0) as ex_times
                  from v2_races r
                  left join ex using(race_id)
                 where r.race_date=%s
                   and coalesce(ex.time_count,0) < 6
                 order by r.deadline_at nulls last, r.race_id
                """,
                (target_date,),
            )
            return [dict(row) for row in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute(
            """
            with ex as (
              select race_id,
                     count(*) filter(where snapshot_label='historical') as row_count,
                     count(*) filter(
                       where snapshot_label='historical'
                         and exhibition_time is not null
                     ) as time_count,
                     count(*) filter(
                       where snapshot_label='historical'
                         and start_timing is not null
                     ) as st_count
                from v2_realtime_exhibition_snapshots
               group by race_id
            ),
            wx as (
              select race_id,
                     max((weather is not null)::int) as weather_ok,
                     max((temperature_c is not null)::int) as temp_ok,
                     max((water_temperature_c is not null)::int) as water_temp_ok,
                     max((wind_speed_m is not null)::int) as wind_ok,
                     max((wave_height_cm is not null)::int) as wave_ok
                from v2_realtime_weather_snapshots
               where snapshot_label='historical'
               group by race_id
            )
            select r.race_id,
                   r.race_date,
                   coalesce(r.venue_id,r.venue_code) as venue_id,
                   r.race_no,
                   r.deadline_at,
                   coalesce(ex.row_count,0) as ex_rows,
                   coalesce(ex.time_count,0) as ex_times,
                   coalesce(ex.st_count,0) as ex_st,
                   coalesce(wx.weather_ok,0) as wx_weather,
                   coalesce(wx.temp_ok,0) as wx_temp,
                   coalesce(wx.water_temp_ok,0) as wx_water_temp,
                   coalesce(wx.wind_ok,0) as wx_wind,
                   coalesce(wx.wave_ok,0) as wx_wave
              from v2_races r
              left join ex using(race_id)
              left join wx using(race_id)
             where r.race_date=%s
               and (
                    coalesce(ex.row_count,0) < 6
                 or coalesce(ex.time_count,0) < 6
                 or coalesce(ex.st_count,0) < 6
                 or coalesce(wx.weather_ok,0) = 0
                 or coalesce(wx.temp_ok,0) = 0
                 or coalesce(wx.water_temp_ok,0) = 0
                 or coalesce(wx.wind_ok,0) = 0
                 or coalesce(wx.wave_ok,0) = 0
               )
             order by r.deadline_at nulls last, r.race_id
            """,
            (target_date,),
        )
        return [dict(row) for row in cur.fetchall()]


def _historical_raw(
    *,
    target_date: str,
    deadline_at: datetime | None,
    kind: str,
    parsed_raw: Any,
) -> dict[str, Any]:
    return {
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "source_contract": SOURCE_CONTRACT,
        "timing_policy": "archived_target_race_beforeinfo_treated_as_predeadline",
        "snapshot_at_semantics": (
            "synthetic_deadline_minus_1s"
            if deadline_at is not None
            else "synthetic_target_date_midnight_fallback"
        ),
        "target_date": target_date,
        "kind": kind,
        "parsed_raw": parsed_raw,
    }


def _upsert_weather(
    conn: psycopg.Connection,
    race: dict[str, Any],
    weather: dict[str, Any],
) -> int:
    deadline_at = _deadline(race.get("deadline_at"))
    snapshot_at = _synthetic_snapshot_at(deadline_at, str(race["race_date"]))
    raw = _historical_raw(
        target_date=str(race["race_date"]),
        deadline_at=deadline_at,
        kind="weather",
        parsed_raw={"text": weather.get("raw_text", "")},
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into v2_realtime_weather_snapshots(
                race_id,race_date,venue_id,venue_code,race_no,
                snapshot_label,snapshot_at,source,
                weather,temperature_c,water_temperature_c,
                wind_speed_m,wind_direction,wave_height_cm,raw,updated_at
            )
            values(
                %s,%s,%s,%s,%s,
                'historical',%s,%s,
                %s,%s,%s,%s,%s,%s,%s,now()
            )
            on conflict(race_id,snapshot_label) do update set
                weather=coalesce(v2_realtime_weather_snapshots.weather,excluded.weather),
                temperature_c=coalesce(v2_realtime_weather_snapshots.temperature_c,excluded.temperature_c),
                water_temperature_c=coalesce(v2_realtime_weather_snapshots.water_temperature_c,excluded.water_temperature_c),
                wind_speed_m=coalesce(v2_realtime_weather_snapshots.wind_speed_m,excluded.wind_speed_m),
                wind_direction=coalesce(v2_realtime_weather_snapshots.wind_direction,excluded.wind_direction),
                wave_height_cm=coalesce(v2_realtime_weather_snapshots.wave_height_cm,excluded.wave_height_cm),
                source=coalesce(v2_realtime_weather_snapshots.source,excluded.source),
                snapshot_at=coalesce(v2_realtime_weather_snapshots.snapshot_at,excluded.snapshot_at),
                raw=coalesce(v2_realtime_weather_snapshots.raw,excluded.raw),
                updated_at=now()
            where
                   (v2_realtime_weather_snapshots.weather is null and excluded.weather is not null)
                or (v2_realtime_weather_snapshots.temperature_c is null and excluded.temperature_c is not null)
                or (v2_realtime_weather_snapshots.water_temperature_c is null and excluded.water_temperature_c is not null)
                or (v2_realtime_weather_snapshots.wind_speed_m is null and excluded.wind_speed_m is not null)
                or (v2_realtime_weather_snapshots.wind_direction is null and excluded.wind_direction is not null)
                or (v2_realtime_weather_snapshots.wave_height_cm is null and excluded.wave_height_cm is not null)
                or (v2_realtime_weather_snapshots.source is null and excluded.source is not null)
                or (v2_realtime_weather_snapshots.snapshot_at is null and excluded.snapshot_at is not null)
                or (v2_realtime_weather_snapshots.raw is null and excluded.raw is not null)
            returning 1
            """,
            (
                str(race["race_id"]),
                race["race_date"],
                str(race.get("venue_id") or "").zfill(2),
                str(race.get("venue_id") or "").zfill(2),
                int(race.get("race_no") or 0),
                snapshot_at,
                SOURCE,
                weather.get("weather"),
                weather.get("temperature_c"),
                weather.get("water_temperature_c"),
                weather.get("wind_speed_m"),
                weather.get("wind_direction"),
                weather.get("wave_height_cm"),
                Jsonb(raw),
            ),
        )
        return 1 if cur.fetchone() else 0


def _upsert_exhibition(
    conn: psycopg.Connection,
    race: dict[str, Any],
    exhibition: list[dict[str, Any]],
) -> int:
    deadline_at = _deadline(race.get("deadline_at"))
    snapshot_at = _synthetic_snapshot_at(deadline_at, str(race["race_date"]))
    total = 0
    for row in exhibition:
        lane = int(row.get("lane") or 0)
        if lane not in (1, 2, 3, 4, 5, 6):
            continue
        raw = _historical_raw(
            target_date=str(race["race_date"]),
            deadline_at=deadline_at,
            kind="exhibition",
            parsed_raw={"cells": row.get("raw_cells") or []},
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into v2_realtime_exhibition_snapshots(
                    race_id,race_date,venue_id,venue_code,race_no,
                    snapshot_label,snapshot_at,source,lane,
                    exhibition_course,exhibition_time,exhibition_time_rank,
                    exhibition_time_diff,start_timing,start_timing_rank,
                    start_timing_diff,tilt,raw,updated_at
                )
                values(
                    %s,%s,%s,%s,%s,
                    'historical',%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,now()
                )
                on conflict(race_id,snapshot_label,lane) do update set
                    exhibition_course=coalesce(v2_realtime_exhibition_snapshots.exhibition_course,excluded.exhibition_course),
                    exhibition_time=coalesce(v2_realtime_exhibition_snapshots.exhibition_time,excluded.exhibition_time),
                    exhibition_time_rank=coalesce(v2_realtime_exhibition_snapshots.exhibition_time_rank,excluded.exhibition_time_rank),
                    exhibition_time_diff=coalesce(v2_realtime_exhibition_snapshots.exhibition_time_diff,excluded.exhibition_time_diff),
                    start_timing=coalesce(v2_realtime_exhibition_snapshots.start_timing,excluded.start_timing),
                    start_timing_rank=coalesce(v2_realtime_exhibition_snapshots.start_timing_rank,excluded.start_timing_rank),
                    start_timing_diff=coalesce(v2_realtime_exhibition_snapshots.start_timing_diff,excluded.start_timing_diff),
                    tilt=coalesce(v2_realtime_exhibition_snapshots.tilt,excluded.tilt),
                    source=coalesce(v2_realtime_exhibition_snapshots.source,excluded.source),
                    snapshot_at=coalesce(v2_realtime_exhibition_snapshots.snapshot_at,excluded.snapshot_at),
                    raw=coalesce(v2_realtime_exhibition_snapshots.raw,excluded.raw),
                    updated_at=now()
                where
                       (v2_realtime_exhibition_snapshots.exhibition_course is null and excluded.exhibition_course is not null)
                    or (v2_realtime_exhibition_snapshots.exhibition_time is null and excluded.exhibition_time is not null)
                    or (v2_realtime_exhibition_snapshots.exhibition_time_rank is null and excluded.exhibition_time_rank is not null)
                    or (v2_realtime_exhibition_snapshots.exhibition_time_diff is null and excluded.exhibition_time_diff is not null)
                    or (v2_realtime_exhibition_snapshots.start_timing is null and excluded.start_timing is not null)
                    or (v2_realtime_exhibition_snapshots.start_timing_rank is null and excluded.start_timing_rank is not null)
                    or (v2_realtime_exhibition_snapshots.start_timing_diff is null and excluded.start_timing_diff is not null)
                    or (v2_realtime_exhibition_snapshots.tilt is null and excluded.tilt is not null)
                    or (v2_realtime_exhibition_snapshots.source is null and excluded.source is not null)
                    or (v2_realtime_exhibition_snapshots.snapshot_at is null and excluded.snapshot_at is not null)
                    or (v2_realtime_exhibition_snapshots.raw is null and excluded.raw is not null)
                returning 1
                """,
                (
                    str(race["race_id"]),
                    race["race_date"],
                    str(race.get("venue_id") or "").zfill(2),
                    str(race.get("venue_id") or "").zfill(2),
                    int(race.get("race_no") or 0),
                    snapshot_at,
                    SOURCE,
                    lane,
                    row.get("exhibition_course") or lane,
                    row.get("exhibition_time"),
                    row.get("exhibition_time_rank"),
                    row.get("exhibition_time_diff"),
                    row.get("start_timing"),
                    row.get("start_timing_rank"),
                    row.get("start_timing_diff"),
                    row.get("tilt"),
                    Jsonb(raw),
                ),
            )
            if cur.fetchone():
                total += 1
    return total


def _upsert_exhibition_time_only(
    conn: psycopg.Connection,
    race: dict[str, Any],
    exhibition: list[dict[str, Any]],
) -> int:
    """Fill only Exhibition Time / rank / diff; never ST, tilt, course or weather."""
    deadline_at = _deadline(race.get("deadline_at"))
    snapshot_at = _synthetic_snapshot_at(deadline_at, str(race["race_date"]))
    total = 0
    for row in exhibition:
        lane = int(row.get("lane") or 0)
        ex_time = row.get("exhibition_time")
        if lane not in (1, 2, 3, 4, 5, 6) or ex_time is None:
            continue
        raw = _historical_raw(
            target_date=str(race["race_date"]),
            deadline_at=deadline_at,
            kind="exhibition_time_only",
            parsed_raw={"cells": row.get("raw_cells") or []},
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into v2_realtime_exhibition_snapshots(
                    race_id,race_date,venue_id,venue_code,race_no,
                    snapshot_label,snapshot_at,source,lane,
                    exhibition_time,exhibition_time_rank,exhibition_time_diff,
                    raw,updated_at
                )
                values(
                    %s,%s,%s,%s,%s,
                    'historical',%s,%s,%s,
                    %s,%s,%s,%s,now()
                )
                on conflict(race_id,snapshot_label,lane) do update set
                    exhibition_time=coalesce(
                        v2_realtime_exhibition_snapshots.exhibition_time,
                        excluded.exhibition_time
                    ),
                    exhibition_time_rank=coalesce(
                        v2_realtime_exhibition_snapshots.exhibition_time_rank,
                        excluded.exhibition_time_rank
                    ),
                    exhibition_time_diff=coalesce(
                        v2_realtime_exhibition_snapshots.exhibition_time_diff,
                        excluded.exhibition_time_diff
                    ),
                    source=coalesce(
                        v2_realtime_exhibition_snapshots.source,
                        excluded.source
                    ),
                    snapshot_at=coalesce(
                        v2_realtime_exhibition_snapshots.snapshot_at,
                        excluded.snapshot_at
                    ),
                    raw=coalesce(
                        v2_realtime_exhibition_snapshots.raw,
                        excluded.raw
                    ),
                    updated_at=now()
                where
                       (
                         v2_realtime_exhibition_snapshots.exhibition_time is null
                         and excluded.exhibition_time is not null
                       )
                    or (
                         v2_realtime_exhibition_snapshots.exhibition_time_rank is null
                         and excluded.exhibition_time_rank is not null
                       )
                    or (
                         v2_realtime_exhibition_snapshots.exhibition_time_diff is null
                         and excluded.exhibition_time_diff is not null
                       )
                    or (
                         v2_realtime_exhibition_snapshots.source is null
                         and excluded.source is not null
                       )
                    or (
                         v2_realtime_exhibition_snapshots.snapshot_at is null
                         and excluded.snapshot_at is not null
                       )
                    or (
                         v2_realtime_exhibition_snapshots.raw is null
                         and excluded.raw is not null
                       )
                returning 1
                """,
                (
                    str(race["race_id"]),
                    race["race_date"],
                    str(race.get("venue_id") or "").zfill(2),
                    str(race.get("venue_id") or "").zfill(2),
                    int(race.get("race_no") or 0),
                    snapshot_at,
                    SOURCE,
                    lane,
                    ex_time,
                    row.get("exhibition_time_rank"),
                    row.get("exhibition_time_diff"),
                    Jsonb(raw),
                ),
            )
            if cur.fetchone():
                total += 1
    return total


def process_day(
    conn: psycopg.Connection,
    session: requests.Session,
    target_date: str,
    *,
    write_enabled: bool,
    sleep_sec: float,
    mode: str = MODE_GENERIC,
    plan_only: bool = False,
) -> dict[str, Any]:
    races = _target_races(conn, target_date, mode=mode)
    counts: Counter[str] = Counter()
    counts["target_missing_races"] = len(races)

    if plan_only:
        counts["plan_only_no_http"] = len(races)
        return {
            "target_date": target_date,
            "mode": mode,
            "summary": dict(sorted(counts.items())),
        }

    for race in races:
        venue = str(race.get("venue_id") or "").zfill(2)
        race_no = int(race.get("race_no") or 0)
        url = rt._official_url("beforeinfo", target_date, venue, race_no)
        html = _fetch(session, url, sleep_sec)
        counts["http_requests"] += 1
        if not html:
            counts["fetch_failed"] += 1
            continue
        if rt._looks_no_data(html):
            counts["official_no_data"] += 1
            continue

        exhibition = rt.parse_exhibition(html)
        counts["parsed_beforeinfo"] += 1
        counts["exhibition_rows_parsed"] += len(exhibition)
        counts["exhibition_complete_races"] += int(
            sorted(int(x.get("lane") or 0) for x in exhibition)
            == [1, 2, 3, 4, 5, 6]
        )

        weather: dict[str, Any] = {}
        if mode == MODE_GENERIC:
            weather = rt.parse_weather(html)
            counts["weather_parsed"] += int(any(
                weather.get(k) is not None
                for k in (
                    "weather","temperature_c","water_temperature_c",
                    "wind_speed_m","wind_direction","wave_height_cm",
                )
            ))
        else:
            counts["weather_parse_skipped"] += 1

        if not write_enabled:
            continue

        try:
            if mode == MODE_GENERIC:
                weather_has_data = any(
                    weather.get(k) is not None
                    for k in (
                        "weather","temperature_c","water_temperature_c",
                        "wind_speed_m","wind_direction","wave_height_cm",
                    )
                )
                if weather_has_data:
                    counts["weather_rows_touched"] += _upsert_weather(
                        conn, race, weather
                    )
            if mode == MODE_EXHIBITION_TIME_ONLY:
                counts["exhibition_rows_touched"] += _upsert_exhibition_time_only(
                    conn, race, exhibition
                )
            else:
                counts["exhibition_rows_touched"] += _upsert_exhibition(
                    conn, race, exhibition
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "target_date": target_date,
        "mode": mode,
        "summary": dict(sorted(counts.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--mode", choices=MODES, default=MODE_GENERIC)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument(
        "--sleep-sec",
        type=float,
        default=float(os.getenv("HIST_BEFOREINFO_SLEEP_SEC", str(DEFAULT_SLEEP_SEC))),
    )
    ap.add_argument(
        "--output",
        default="historical-beforeinfo-backfill-manifest.json",
    )
    args = ap.parse_args()

    dates = _date_range(args.start_date, args.end_date)
    if len(dates) > 31:
        raise SystemExit("maximum direct runtime range is 31 days")
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_BEFOREINFO_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )

    print(f"HIST_BEFOREINFO_SOURCE_CONTRACT={SOURCE_CONTRACT}", flush=True)
    print("HIST_BEFOREINFO_TIMING_POLICY=archived_target_race_beforeinfo_predeadline_by_nature", flush=True)
    print("HIST_BEFOREINFO_SNAPSHOT_AT=synthetic_boundary_not_original_fetch_time", flush=True)
    print("HIST_BEFOREINFO_WRITE_POLICY=historical_label_fill_missing_only", flush=True)
    print("HIST_BEFOREINFO_RESULT_ODDS_PAYOUT_READ=0", flush=True)
    print("HIST_BEFOREINFO_LINE=0 BUY=0 PROD_MODEL_CHANGE=0", flush=True)
    print(f"HIST_BEFOREINFO_WRITE_ENABLED={int(write_enabled)}", flush=True)
    print(f"HIST_BEFOREINFO_MODE={args.mode}", flush=True)
    print(f"HIST_BEFOREINFO_PLAN_ONLY={int(args.plan_only)}", flush=True)

    reports: list[dict[str, Any]] = []
    session = requests.Session()
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        for target_date in dates:
            report = process_day(
                conn,
                session,
                target_date,
                write_enabled=write_enabled,
                sleep_sec=max(0.0, args.sleep_sec),
                mode=args.mode,
                plan_only=args.plan_only,
            )
            reports.append(report)
            s = report["summary"]
            print(
                "HIST_BEFOREINFO_DAY="
                f"date:{target_date} "
                f"target:{s.get('target_missing_races',0)} "
                f"parsed:{s.get('parsed_beforeinfo',0)} "
                f"ex_complete:{s.get('exhibition_complete_races',0)} "
                f"weather:{s.get('weather_parsed',0)} "
                f"ex_touched:{s.get('exhibition_rows_touched',0)} "
                f"wx_touched:{s.get('weather_rows_touched',0)} "
                f"fetch_failed:{s.get('fetch_failed',0)} "
                f"no_data:{s.get('official_no_data',0)}",
                flush=True,
            )

    totals: Counter[str] = Counter()
    for report in reports:
        totals.update(report["summary"])

    payload = {
        "contract": "HISTORICAL_OFFICIAL_BEFOREINFO_BACKFILL_V1",
        "source_contract": SOURCE_CONTRACT,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "snapshot_label": SNAPSHOT_LABEL,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "predeadline_interpretation": True,
        "exact_original_fetch_time_known": False,
        "synthetic_snapshot_boundary": True,
        "fill_missing_only": True,
        "result_odds_payout_read": False,
        "write_enabled": write_enabled,
        "mode": args.mode,
        "plan_only": args.plan_only,
        "totals": dict(sorted(totals.items())),
        "days": reports,
        "production_model_change": False,
        "purchase_action": False,
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "HIST_BEFOREINFO_TOTALS="
        + json.dumps(payload["totals"], sort_keys=True),
        flush=True,
    )
    print("HIST_BEFOREINFO_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
