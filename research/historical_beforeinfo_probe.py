# -*- coding: utf-8 -*-
"""Read-only probe for archived BOAT RACE official beforeinfo pages.

Historical truth contract:
- target-race archived beforeinfo is treated as a pre-deadline source by nature;
- no result/odds/payout page is read;
- no PostgreSQL access;
- this probe only validates that archived official beforeinfo remains fetchable
  and compatible with the current Production parser.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

import v21_realtime_collector_pg as rt


def probe(date_str: str, venue: str, race_no: int) -> dict:
    url = rt._official_url("beforeinfo", date_str, venue, race_no)
    response = requests.get(
        url,
        headers={"User-Agent": "boat-ai-v2-historical-beforeinfo-probe/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    html = response.text
    if rt._looks_no_data(html):
        raise RuntimeError("official archived beforeinfo returned no-data page")

    exhibition = rt.parse_exhibition(html)
    weather = rt.parse_weather(html)
    lanes = sorted(int(row.get("lane") or 0) for row in exhibition)
    if lanes != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError(f"expected six exhibition lanes, got {lanes}")

    ex_time_count = sum(
        1 for row in exhibition if row.get("exhibition_time") not in (None, "")
    )
    st_count = sum(
        1 for row in exhibition if row.get("start_timing") not in (None, "")
    )
    weather_fields = {
        key: weather.get(key)
        for key in (
            "weather",
            "temperature_c",
            "water_temperature_c",
            "wind_speed_m",
            "wind_direction",
            "wave_height_cm",
        )
    }
    nonnull_weather = sum(v is not None for v in weather_fields.values())

    return {
        "contract": "HISTORICAL_OFFICIAL_BEFOREINFO_PROBE_V1",
        "date": date_str,
        "venue": str(venue).zfill(2),
        "race_no": int(race_no),
        "source": "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO",
        "predeadline_by_nature": True,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "result_page_read": False,
        "odds_page_read": False,
        "payout_read": False,
        "db_read": False,
        "db_write": False,
        "exhibition_rows": len(exhibition),
        "exhibition_time_values": ex_time_count,
        "start_timing_values": st_count,
        "weather_nonnull_fields": nonnull_weather,
        "weather": weather_fields,
        "production_change": False,
        "purchase_action": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2025-07-01")
    ap.add_argument("--venue", default="21")
    ap.add_argument("--race-no", type=int, default=1)
    ap.add_argument("--output", default="historical-beforeinfo-probe.json")
    args = ap.parse_args()

    payload = probe(args.date, args.venue, args.race_no)
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "HIST_BEFOREINFO_PROBE="
        + json.dumps(payload, ensure_ascii=False, sort_keys=True),
        flush=True,
    )
    if payload["exhibition_time_values"] != 6:
        raise RuntimeError("historical exhibition-time values incomplete")
    if payload["weather_nonnull_fields"] < 4:
        raise RuntimeError("historical weather fields insufficient")
    print("HIST_BEFOREINFO_PROBE_RESULT=PASS_ARCHIVED_OFFICIAL", flush=True)


if __name__ == "__main__":
    main()
