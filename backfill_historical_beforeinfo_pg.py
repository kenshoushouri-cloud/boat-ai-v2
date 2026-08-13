# -*- coding: utf-8 -*-
"""
backfill_historical_beforeinfo_pg.py

BOAT RACE公式の過去beforeinfoを取得し、
過去の展示・気象・レース状態・選手状態をRailway Postgresへ補修する。

初回テスト推奨:
    HIST_START_DATE=2025-07-01
    HIST_END_DATE=2025-07-01

保存先:
    v2_realtime_weather_snapshots
    v2_realtime_exhibition_snapshots
    v2_realtime_race_condition_snapshots
    v2_realtime_racer_condition_snapshots

特徴:
- LINE通知なし
- 候補判定なし
- 購入処理なし
- historical専用snapshot_label
- upsert対応
- 再実行可能
- 既存v21 parserを可能な限り利用
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from db_pg import fetch_all, upsert_rows
import v21_realtime_collector_pg as v21

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


VERSION = "2026-08-13 historical-beforeinfo-backfill-v1"

START_DATE = os.getenv(
    "HIST_START_DATE",
    "2025-07-01",
).strip()

END_DATE = os.getenv(
    "HIST_END_DATE",
    START_DATE,
).strip()

SNAPSHOT_LABEL = os.getenv(
    "HIST_SNAPSHOT_LABEL",
    "historical",
).strip() or "historical"

SLEEP_SEC = max(
    0.0,
    float(os.getenv("HIST_SLEEP_SEC", "0.15")),
)

MAX_RACES = max(
    0,
    int(os.getenv("HIST_MAX_RACES", "0")),
)

REQUIRE_SIX_EXHIBITION = (
    os.getenv("HIST_REQUIRE_SIX_EXHIBITION", "1")
    .strip()
    .lower()
    in ("1", "true", "yes")
)


def norm(s: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize(
            "NFKC",
            str(s or ""),
        ),
    ).strip()


def soup_text(html: str) -> str:
    if BeautifulSoup is not None:
        return norm(
            BeautifulSoup(
                html,
                "html.parser",
            ).get_text(
                " ",
                strip=True,
            )
        )

    return norm(
        re.sub(
            r"<[^>]+>",
            " ",
            html,
        )
    )


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


def parse_weather_v2(
    html: str,
) -> Dict[str, Any]:

    text = soup_text(html)

    def rx(pattern: str):
        m = re.search(
            pattern,
            text,
            flags=re.I,
        )

        return (
            safe_float(m.group(1))
            if m
            else None
        )

    weather = None

    for w in (
        "晴",
        "曇",
        "くもり",
        "雨",
        "雪",
        "霧",
    ):
        if w in text:
            weather = w
            break

    wind_direction = None

    for d in (
        "北東",
        "南東",
        "南西",
        "北西",
        "北",
        "東",
        "南",
        "西",
        "向い風",
        "追い風",
        "右横風",
        "左横風",
    ):
        if d in text:
            wind_direction = d
            break

    return {
        "weather": weather,
        "temperature_c": rx(
            r"気温\s*([+-]?\d+(?:\.\d+)?)\s*℃"
        ),
        "water_temperature_c": rx(
            r"水温\s*([+-]?\d+(?:\.\d+)?)\s*℃"
        ),
        "wind_speed_m": rx(
            r"風速\s*([0-9]+(?:\.\d+)?)\s*m"
        ),
        "wind_direction": wind_direction,
        "wave_height_cm": rx(
            r"波高\s*([0-9]+(?:\.\d+)?)\s*cm"
        ),
        "raw_text": text[:4000],
    }


def daterange(
    start_date: str,
    end_date: str,
):
    start = datetime.strptime(
        start_date,
        "%Y-%m-%d",
    ).date()

    end = datetime.strptime(
        end_date,
        "%Y-%m-%d",
    ).date()

    if end < start:
        raise ValueError(
            "HIST_END_DATE must be >= HIST_START_DATE"
        )

    d = start

    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def upsert(
    table: str,
    rows: List[Dict[str, Any]],
    conflict_cols: List[str],
) -> int:

    if not rows:
        return 0

    return upsert_rows(
        table,
        rows,
        conflict_cols,
    )


def load_entries(
    race_ids: List[str],
):
    if not race_ids:
        return defaultdict(list)

    placeholders = ",".join(
        ["%s"] * len(race_ids)
    )

    rows = fetch_all(
        f"""
        select *
        from v2_race_entries
        where race_id in ({placeholders})
        order by race_id,lane
        """,
        tuple(race_ids),
    )

    out = defaultdict(list)

    for row in rows:
        out[
            str(row.get("race_id") or "")
        ].append(row)

    return out


def save_weather(
    race: Dict[str, Any],
    weather: Dict[str, Any],
) -> int:

    now = v21._now_iso()

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    row = {
        "race_id": str(race["race_id"]),
        "race_date": race.get("race_date"),
        "venue_id": venue,
        "venue_code": venue,
        "race_no": int(
            race.get("race_no") or 0
        ),
        "snapshot_label": SNAPSHOT_LABEL,
        "snapshot_at": now,
        "source": "official_beforeinfo_historical",
        "weather": weather.get("weather"),
        "temperature_c": weather.get(
            "temperature_c"
        ),
        "water_temperature_c": weather.get(
            "water_temperature_c"
        ),
        "wind_speed_m": weather.get(
            "wind_speed_m"
        ),
        "wind_direction": weather.get(
            "wind_direction"
        ),
        "wave_height_cm": weather.get(
            "wave_height_cm"
        ),
        "raw": {
            "text": weather.get(
                "raw_text",
                "",
            )
        },
        "updated_at": now,
    }

    return upsert(
        "v2_realtime_weather_snapshots",
        [row],
        [
            "race_id",
            "snapshot_label",
        ],
    )


def save_exhibition(
    race: Dict[str, Any],
    entries: List[Dict[str, Any]],
    exhibition: List[Dict[str, Any]],
) -> int:

    if not exhibition:
        return 0

    rid = str(race["race_id"])

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    race_no = int(
        race.get("race_no") or 0
    )

    entries_by_lane = {
        int(e.get("lane") or 0): e
        for e in entries
    }

    rows = []

    for x in exhibition:

        lane = int(
            x.get("lane") or 0
        )

        if lane not in range(1, 7):
            continue

        entry = entries_by_lane.get(
            lane,
            {},
        )

        now = v21._now_iso()

        original_tilt = safe_float(
            entry.get("tilt")
        )

        tilt = safe_float(
            x.get("tilt")
        )

        tilt_change = None

        if (
            tilt is not None
            and original_tilt is not None
        ):
            tilt_change = round(
                tilt - original_tilt,
                3,
            )

        rows.append({
            "race_id": rid,
            "race_date": race.get(
                "race_date"
            ),
            "venue_id": venue,
            "venue_code": venue,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "snapshot_at": now,
            "source": (
                "official_beforeinfo_historical"
            ),
            "lane": lane,
            "exhibition_course": (
                x.get("exhibition_course")
                or lane
            ),
            "exhibition_time": x.get(
                "exhibition_time"
            ),
            "exhibition_time_rank": x.get(
                "exhibition_time_rank"
            ),
            "exhibition_time_diff": x.get(
                "exhibition_time_diff"
            ),
            "start_timing": x.get(
                "start_timing"
            ),
            "start_timing_rank": x.get(
                "start_timing_rank"
            ),
            "start_timing_diff": x.get(
                "start_timing_diff"
            ),
            "tilt": tilt,
            "original_tilt": original_tilt,
            "tilt_change": tilt_change,
            "raw": {
                "cells": x.get(
                    "raw_cells",
                    [],
                )
            },
            "updated_at": now,
        })

    return upsert(
        "v2_realtime_exhibition_snapshots",
        rows,
        [
            "race_id",
            "snapshot_label",
            "lane",
        ],
    )


def save_conditions(
    race: Dict[str, Any],
    race_condition: Dict[str, Any],
    players: List[Dict[str, Any]],
) -> tuple[int, int]:

    rid = str(race["race_id"])

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    race_no = int(
        race.get("race_no") or 0
    )

    now = v21._now_iso()

    race_row = {
        "race_id": rid,
        "race_date": race.get(
            "race_date"
        ),
        "venue_id": venue,
        "venue_code": venue,
        "race_no": race_no,
        "snapshot_label": SNAPSHOT_LABEL,
        "snapshot_at": now,
        "source": (
            "official_beforeinfo_historical"
        ),
        "is_stabilizer_used": (
            race_condition.get(
                "is_stabilizer_used"
            )
        ),
        "is_fixed_entry": (
            race_condition.get(
                "is_fixed_entry"
            )
        ),
        "race_distance_m": (
            race_condition.get(
                "race_distance_m"
            )
        ),
        "has_new_propeller": (
            race_condition.get(
                "has_new_propeller"
            )
        ),
        "parts_replacement_count": (
            race_condition.get(
                "parts_replacement_count"
            )
        ),
        "raw": {
            "text": race_condition.get(
                "raw_text",
                "",
            )
        },
        "updated_at": now,
    }

    player_rows = []

    for p in players:

        lane = int(
            p.get("lane") or 0
        )

        if lane not in range(1, 7):
            continue

        player_rows.append({
            "race_id": rid,
            "race_date": race.get(
                "race_date"
            ),
            "venue_id": venue,
            "venue_code": venue,
            "race_no": race_no,
            "snapshot_label": SNAPSHOT_LABEL,
            "snapshot_at": now,
            "source": (
                "official_beforeinfo_historical"
            ),
            "lane": lane,
            "racer_number": p.get(
                "racer_number"
            ),
            "weight_kg": p.get(
                "weight_kg"
            ),
            "adjustment_weight_kg": p.get(
                "adjustment_weight_kg"
            ),
            "is_new_propeller": p.get(
                "is_new_propeller"
            ),
            "parts_replacements": p.get(
                "parts_replacements",
                [],
            ),
            "previous_race_no": p.get(
                "previous_race_no"
            ),
            "previous_course": p.get(
                "previous_course"
            ),
            "previous_st": p.get(
                "previous_st"
            ),
            "previous_finish": p.get(
                "previous_finish"
            ),
            "raw": {
                "cells": p.get(
                    "raw_cells",
                    [],
                )
            },
            "updated_at": now,
        })

    n1 = upsert(
        "v2_realtime_race_condition_snapshots",
        [race_row],
        [
            "race_id",
            "snapshot_label",
        ],
    )

    n2 = upsert(
        "v2_realtime_racer_condition_snapshots",
        player_rows,
        [
            "race_id",
            "snapshot_label",
            "lane",
        ],
    )

    return n1, n2


def process_date(
    date_str: str,
    total_summary: Dict[str, int],
) -> None:

    races = fetch_all(
        """
        select
            race_id,
            race_date,
            venue_id,
            venue_code,
            venue_name,
            race_no,
            race_name
        from v2_races
        where race_date=%s
        order by venue_id,race_no
        """,
        (date_str,),
    )

    if MAX_RACES:
        races = races[:MAX_RACES]

    print(
        f"\n=== {date_str} races={len(races)} ===",
        flush=True,
    )

    if not races:
        total_summary["dates_no_races"] += 1
        return

    race_ids = [
        str(r["race_id"])
        for r in races
    ]

    entries_by = load_entries(
        race_ids
    )

    day = defaultdict(int)

    for i, race in enumerate(
        races,
        1,
    ):

        rid = str(
            race["race_id"]
        )

        venue = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)

        race_no = int(
            race.get("race_no") or 0
        )

        total_summary["races"] += 1
        day["races"] += 1

        try:
            url = v21._official_url(
                "beforeinfo",
                date_str,
                venue,
                race_no,
            )

            html = v21._fetch(url)

            if not html:
                day["fetch_failed"] += 1
                total_summary[
                    "fetch_failed"
                ] += 1

                print(
                    f"[{i}/{len(races)}] "
                    f"{rid} FETCH_FAILED",
                    flush=True,
                )
                continue

            day["http_ok"] += 1
            total_summary["http_ok"] += 1

            weather = parse_weather_v2(
                html
            )

            exhibition = (
                v21.parse_exhibition(
                    html
                )
            )

            race_condition, players = (
                v21.parse_beforeinfo_extra(
                    html,
                    entries_by.get(
                        rid,
                        [],
                    ),
                )
            )

            nw = save_weather(
                race,
                weather,
            )

            if (
                REQUIRE_SIX_EXHIBITION
                and len(exhibition) != 6
            ):
                nx = 0
                day[
                    "exhibition_incomplete"
                ] += 1
                total_summary[
                    "exhibition_incomplete"
                ] += 1
            else:
                nx = save_exhibition(
                    race,
                    entries_by.get(
                        rid,
                        [],
                    ),
                    exhibition,
                )

            nr, np = save_conditions(
                race,
                race_condition,
                players,
            )

            day["weather_rows"] += nw
            day["exhibition_rows"] += nx
            day["race_condition_rows"] += nr
            day["racer_condition_rows"] += np

            total_summary[
                "weather_rows"
            ] += nw

            total_summary[
                "exhibition_rows"
            ] += nx

            total_summary[
                "race_condition_rows"
            ] += nr

            total_summary[
                "racer_condition_rows"
            ] += np

            print(
                f"[{i}/{len(races)}] "
                f"{rid} "
                f"before=OK "
                f"weather={nw} "
                f"exhibition={len(exhibition)}/6 "
                f"saved_exhibition={nx} "
                f"race_condition={nr} "
                f"racer_condition={np}",
                flush=True,
            )

        except Exception as exc:

            day["errors"] += 1
            total_summary[
                "errors"
            ] += 1

            print(
                f"[{i}/{len(races)}] "
                f"{rid} ERROR "
                f"{type(exc).__name__}: "
                f"{exc}",
                flush=True,
            )

        if SLEEP_SEC > 0:
            time.sleep(
                SLEEP_SEC
            )

    print(
        f"--- {date_str} summary ---",
        flush=True,
    )

    for key in (
        "races",
        "http_ok",
        "fetch_failed",
        "weather_rows",
        "exhibition_rows",
        "exhibition_incomplete",
        "race_condition_rows",
        "racer_condition_rows",
        "errors",
    ):
        print(
            f"{key}={day[key]}",
            flush=True,
        )


def main() -> None:

    if not os.getenv(
        "DATABASE_URL"
    ):
        raise RuntimeError(
            "DATABASE_URL が必要です。"
        )

    print(
        "✅ backfill_historical_beforeinfo_pg.py "
        f"VERSION {VERSION}",
        flush=True,
    )

    print(
        f"HIST_START_DATE={START_DATE}",
        flush=True,
    )

    print(
        f"HIST_END_DATE={END_DATE}",
        flush=True,
    )

    print(
        f"HIST_SNAPSHOT_LABEL={SNAPSHOT_LABEL}",
        flush=True,
    )

    print(
        f"HIST_SLEEP_SEC={SLEEP_SEC}",
        flush=True,
    )

    print(
        f"HIST_MAX_RACES={MAX_RACES}",
        flush=True,
    )

    print(
        "LINE通知・候補判定・購入処理なし。",
        flush=True,
    )

    print(
        "historical snapshotとしてDBへupsertします。",
        flush=True,
    )

    total = defaultdict(int)

    for date_str in daterange(
        START_DATE,
        END_DATE,
    ):
        process_date(
            date_str,
            total,
        )

    print(
        "\n=== historical beforeinfo "
        "backfill total summary ===",
        flush=True,
    )

    for key in (
        "races",
        "http_ok",
        "fetch_failed",
        "weather_rows",
        "exhibition_rows",
        "exhibition_incomplete",
        "race_condition_rows",
        "racer_condition_rows",
        "errors",
        "dates_no_races",
    ):
        print(
            f"{key}={total[key]}",
            flush=True,
        )

    print(
        "=== historical beforeinfo "
        "backfill finished ===",
        flush=True,
    )


if __name__ == "__main__":
    main()