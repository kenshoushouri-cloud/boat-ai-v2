# -*- coding: utf-8 -*-
"""
probe_historical_beforeinfo_availability_pg_v2.py

過去 beforeinfo の取得可否を再確認する読み取り専用プローブ。
v21 の既存 parser は使いつつ、気象だけは文字化けに依存しない
日本語ラベルベース parser で再確認する。

DB更新・LINE通知・本番変更なし。
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List

from db_pg import fetch_all
import v21_realtime_collector_pg as v21

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

PROBE_DATE = os.getenv("HIST_PROBE_DATE", "2025-07-01").strip()
MAX_VENUES = max(1, int(os.getenv("HIST_PROBE_MAX_VENUES", "3")))
RACE_NOS = [
    int(x.strip())
    for x in os.getenv("HIST_PROBE_RACE_NOS", "1,6,12").split(",")
    if x.strip().isdigit()
]

def norm(s: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s or ""))).strip()

def soup_text(html: str) -> str:
    if BeautifulSoup is not None:
        return norm(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    return norm(re.sub(r"<[^>]+>", " ", html))

def safe_float(v: Any):
    try:
        if v in (None, ""):
            return None
        s = norm(v).replace(",", "")
        if s.startswith("."):
            s = "0" + s
        return float(s)
    except Exception:
        return None

def parse_weather_v2(html: str) -> Dict[str, Any]:
    text = soup_text(html)

    def rx(pattern: str):
        m = re.search(pattern, text, flags=re.I)
        return safe_float(m.group(1)) if m else None

    weather = None
    for w in ("晴", "曇", "くもり", "雨", "雪", "霧"):
        if w in text:
            weather = w
            break

    wind_direction = None
    # まず方角表記を優先
    for d in ("北東", "南東", "南西", "北西", "北", "東", "南", "西",
              "向い風", "追い風", "右横風", "左横風"):
        if d in text:
            wind_direction = d
            break

    return {
        "weather": weather,
        "temperature_c": rx(r"気温\s*([+-]?\d+(?:\.\d+)?)\s*℃"),
        "water_temperature_c": rx(r"水温\s*([+-]?\d+(?:\.\d+)?)\s*℃"),
        "wind_speed_m": rx(r"風速\s*([0-9]+(?:\.\d+)?)\s*m"),
        "wind_direction": wind_direction,
        "wave_height_cm": rx(r"波高\s*([0-9]+(?:\.\d+)?)\s*cm"),
        "raw_text": text[:4000],
    }

def has(v: Any) -> bool:
    return v is not None and v != ""

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ probe_historical_beforeinfo_availability_pg_v2.py VERSION 2026-08-13 weather-parser-v2", flush=True)
    print(f"HIST_PROBE_DATE={PROBE_DATE} MAX_VENUES={MAX_VENUES} RACE_NOS={RACE_NOS}", flush=True)
    print("読み取り専用。DB更新・LINE通知・本番変更なし。", flush=True)

    races = fetch_all("""
        select race_id,race_date,venue_id,venue_code,venue_name,race_no,race_name
        from v2_races
        where race_date=%s
        order by venue_id,race_no
    """, (PROBE_DATE,))

    byv = defaultdict(list)
    for r in races:
        v = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        byv[v].append(r)

    selected = []
    for v in sorted(byv)[:MAX_VENUES]:
        byr = {int(r.get("race_no") or 0): r for r in byv[v]}
        for rno in RACE_NOS:
            if rno in byr:
                selected.append(byr[rno])

    ids = [str(r["race_id"]) for r in selected]
    if not ids:
        print("対象レースなし。", flush=True)
        return

    ph = ",".join(["%s"] * len(ids))
    er = fetch_all(
        f"select * from v2_race_entries where race_id in ({ph}) order by race_id,lane",
        tuple(ids),
    )
    eb = defaultdict(list)
    for e in er:
        eb[str(e.get("race_id") or "")].append(e)

    summary = defaultdict(int)

    print("=== probe samples ===", flush=True)

    for r in selected:
        summary["samples"] += 1
        rid = str(r["race_id"])
        v = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        rno = int(r.get("race_no") or 0)

        html = v21._fetch(v21._official_url("beforeinfo", PROBE_DATE, v, rno))
        if not html:
            print(f"{rid} status=FETCH_FAILED", flush=True)
            continue

        summary["http_ok"] += 1

        w = parse_weather_v2(html)
        ex = v21.parse_exhibition(html)
        _, players = v21.parse_beforeinfo_extra(html, eb.get(rid, []))

        wc = sum(has(w.get(k)) for k in (
            "weather", "temperature_c", "water_temperature_c",
            "wind_speed_m", "wind_direction", "wave_height_cm"
        ))
        if wc:
            summary["weather_any"] += 1
        if wc >= 5:
            summary["weather_full"] += 1
        if len(ex) == 6:
            summary["exhibition_6"] += 1

        valid_players = [x for x in players if x.get("lane") in (1,2,3,4,5,6)]
        if len(valid_players) == 6:
            summary["racer_condition_6"] += 1

        weights = sum(has(x.get("weight_kg")) for x in valid_players)
        prev_st = sum(has(x.get("previous_st")) for x in valid_players)
        prev_fin = sum(has(x.get("previous_finish")) for x in valid_players)

        # 既存parse_exhibitionが進入変更を拾えているか簡易確認
        changed = sum(
            1 for x in ex
            if x.get("exhibition_course") not in (None, x.get("lane"))
        )

        print(
            f"{rid} {r.get('venue_name') or v} {rno}R "
            f"weather={wc}/6 exhibition={len(ex)}/6 "
            f"course_changed={changed} "
            f"weight={weights}/6 prev_st={prev_st}/6 prev_finish={prev_fin}/6",
            flush=True,
        )
        print(
            f"  weather={w.get('weather')} temp={w.get('temperature_c')} "
            f"water={w.get('water_temperature_c')} wind={w.get('wind_speed_m')} "
            f"dir={w.get('wind_direction')} wave={w.get('wave_height_cm')}",
            flush=True,
        )

    print("=== probe summary ===", flush=True)
    for k in (
        "samples","http_ok","weather_any","weather_full",
        "exhibition_6","racer_condition_6"
    ):
        print(f"{k}={summary[k]}", flush=True)

    n = summary["samples"] or 1
    print(f"weather_any_rate={summary['weather_any']/n*100:.1f}%", flush=True)
    print(f"weather_full_rate={summary['weather_full']/n*100:.1f}%", flush=True)
    print(f"exhibition_complete_rate={summary['exhibition_6']/n*100:.1f}%", flush=True)

    if summary["exhibition_6"] == summary["samples"] and summary["weather_any"] > 0:
        print("HISTORICAL_BACKFILL_READY=YES", flush=True)
    elif summary["exhibition_6"] > 0:
        print("HISTORICAL_BACKFILL_READY=EXHIBITION_ONLY", flush=True)
    else:
        print("HISTORICAL_BACKFILL_READY=NO", flush=True)

    print("=== probe v2 finished ===", flush=True)

if __name__ == "__main__":
    main()