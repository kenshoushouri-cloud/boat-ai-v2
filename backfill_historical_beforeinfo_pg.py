# -*- coding: utf-8 -*-
"""
backfill_historical_beforeinfo_pg.py

Historical beforeinfo backfill for Railway Postgres.

VERSION:
    2026-08-13 historical-beforeinfo-backfill-v2-parallel

方針:
- BOAT RACE公式 beforeinfo のHTTP取得＋parseを並列化
- DB保存はメインスレッドでbulk upsert
- LINE通知なし
- 本番候補判定なし
- 購入処理なし
- snapshot_label=historical
- race_id + snapshot_label (+ lane) でupsert
- 再実行可能

初回テスト:
    HIST_START_DATE=2025-07-01
    HIST_END_DATE=2025-07-01
    HIST_WORKERS=4

月次:
    HIST_START_DATE=2025-07-01
    HIST_END_DATE=2025-07-31
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all, upsert_rows
import v21_realtime_collector_pg as v21

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


VERSION = "2026-08-13 historical-beforeinfo-backfill-v2-parallel"

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

WORKERS = max(
    1,
    min(
        8,
        int(os.getenv("HIST_WORKERS", "4")),
    ),
)

SLEEP_SEC = max(
    0.0,
    float(os.getenv("HIST_SLEEP_SEC", "0.05")),
)

MAX_RACES = max(
    0,
    int(os.getenv("HIST_MAX_RACES", "0")),
)

BULK_RACES = max(
    10,
    int(os.getenv("HIST_BULK_RACES", "50")),
)

REQUIRE_SIX_EXHIBITION = (
    os.getenv(
        "HIST_REQUIRE_SIX_EXHIBITION",
        "1",
    )
    .strip()
    .lower()
    in ("1", "true", "yes")
)


# ---------------------------------------------------------
# Utility
# ---------------------------------------------------------

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


def now_iso() -> str:
    return v21._now_iso()


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


# ---------------------------------------------------------
# Weather parser v2
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# DB helpers
# ---------------------------------------------------------

def bulk_upsert(
    table: str,
    rows: List[Dict[str, Any]],
    conflict_cols: List[str],
    chunk_size: int = 500,
) -> int:

    if not rows:
        return 0

    total = 0

    for i in range(
        0,
        len(rows),
        chunk_size,
    ):
        chunk = rows[
            i:i + chunk_size
        ]

        total += upsert_rows(
            table,
            chunk,
            conflict_cols,
        )

    return total


def load_entries(
    race_ids: List[str],
):
    out = defaultdict(list)

    if not race_ids:
        return out

    # 1日最大数百Rなのでまとめて取得可能
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

    for row in rows:
        out[
            str(row.get("race_id") or "")
        ].append(row)

    return out


# ---------------------------------------------------------
# Row builders
# ---------------------------------------------------------

def build_weather_row(
    race: Dict[str, Any],
    weather: Dict[str, Any],
) -> Dict[str, Any]:

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    now = now_iso()

    return {
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


def build_exhibition_rows(
    race: Dict[str, Any],
    entries: List[Dict[str, Any]],
    exhibition: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

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

        now = now_iso()

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

    return rows


def build_condition_rows(
    race: Dict[str, Any],
    race_condition: Dict[str, Any],
    players: List[Dict[str, Any]],
) -> Tuple[
    Dict[str, Any],
    List[Dict[str, Any]],
]:

    rid = str(race["race_id"])

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    race_no = int(
        race.get("race_no") or 0
    )

    now = now_iso()

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

    return race_row, player_rows


# ---------------------------------------------------------
# Worker
# ---------------------------------------------------------

def fetch_and_parse(
    date_str: str,
    race: Dict[str, Any],
    entries: List[Dict[str, Any]],
) -> Dict[str, Any]:

    rid = str(race["race_id"])

    venue = str(
        race.get("venue_id")
        or race.get("venue_code")
        or ""
    ).zfill(2)

    race_no = int(
        race.get("race_no") or 0
    )

    try:

        url = v21._official_url(
            "beforeinfo",
            date_str,
            venue,
            race_no,
        )

        html = v21._fetch(url)

        if not html:
            return {
                "race_id": rid,
                "status": "FETCH_FAILED",
            }

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
                entries,
            )
        )

        weather_row = build_weather_row(
            race,
            weather,
        )

        exhibition_rows = []

        exhibition_complete = (
            len(exhibition) == 6
        )

        if (
            not REQUIRE_SIX_EXHIBITION
            or exhibition_complete
        ):
            exhibition_rows = (
                build_exhibition_rows(
                    race,
                    entries,
                    exhibition,
                )
            )

        race_row, player_rows = (
            build_condition_rows(
                race,
                race_condition,
                players,
            )
        )

        if SLEEP_SEC > 0:
            time.sleep(
                SLEEP_SEC
            )

        return {
            "race_id": rid,
            "status": "OK",
            "weather_row": weather_row,
            "exhibition_rows": (
                exhibition_rows
            ),
            "exhibition_count": len(
                exhibition
            ),
            "exhibition_complete": (
                exhibition_complete
            ),
            "race_condition_row": (
                race_row
            ),
            "racer_condition_rows": (
                player_rows
            ),
        }

    except Exception as exc:

        return {
            "race_id": rid,
            "status": "ERROR",
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }


# ---------------------------------------------------------
# Flush
# ---------------------------------------------------------

def flush_buffers(
    buffers: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, int]:

    saved = defaultdict(int)

    saved["weather_rows"] = bulk_upsert(
        "v2_realtime_weather_snapshots",
        buffers["weather"],
        [
            "race_id",
            "snapshot_label",
        ],
    )

    saved["exhibition_rows"] = bulk_upsert(
        "v2_realtime_exhibition_snapshots",
        buffers["exhibition"],
        [
            "race_id",
            "snapshot_label",
            "lane",
        ],
    )

    saved["race_condition_rows"] = (
        bulk_upsert(
            "v2_realtime_race_condition_snapshots",
            buffers["race_condition"],
            [
                "race_id",
                "snapshot_label",
            ],
        )
    )

    saved["racer_condition_rows"] = (
        bulk_upsert(
            "v2_realtime_racer_condition_snapshots",
            buffers["racer_condition"],
            [
                "race_id",
                "snapshot_label",
                "lane",
            ],
        )
    )

    for key in buffers:
        buffers[key].clear()

    return saved


# ---------------------------------------------------------
# Day processing
# ---------------------------------------------------------

def process_date(
    date_str: str,
    total: Dict[str, int],
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
        f"\n=== {date_str} "
        f"races={len(races)} ===",
        flush=True,
    )

    if not races:
        total[
            "dates_no_races"
        ] += 1
        return

    race_ids = [
        str(r["race_id"])
        for r in races
    ]

    entries_by = load_entries(
        race_ids
    )

    day = defaultdict(int)

    buffers = {
        "weather": [],
        "exhibition": [],
        "race_condition": [],
        "racer_condition": [],
    }

    completed_since_flush = 0

    started = time.monotonic()

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as executor:

        futures = {}

        for race in races:

            rid = str(
                race["race_id"]
            )

            future = executor.submit(
                fetch_and_parse,
                date_str,
                race,
                entries_by.get(
                    rid,
                    [],
                ),
            )

            futures[future] = rid

        completed = 0

        for future in as_completed(
            futures
        ):

            completed += 1
            completed_since_flush += 1

            rid = futures[future]

            try:
                result = future.result()

            except Exception as exc:
                result = {
                    "race_id": rid,
                    "status": "ERROR",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }

            day["races"] += 1
            total["races"] += 1

            status = result.get(
                "status"
            )

            if status == "FETCH_FAILED":

                day[
                    "fetch_failed"
                ] += 1

                total[
                    "fetch_failed"
                ] += 1

                print(
                    f"[{completed}/{len(races)}] "
                    f"{rid} FETCH_FAILED",
                    flush=True,
                )

            elif status == "ERROR":

                day["errors"] += 1
                total["errors"] += 1

                print(
                    f"[{completed}/{len(races)}] "
                    f"{rid} ERROR "
                    f"{result.get('error')}",
                    flush=True,
                )

            else:

                day["http_ok"] += 1
                total["http_ok"] += 1

                buffers[
                    "weather"
                ].append(
                    result[
                        "weather_row"
                    ]
                )

                buffers[
                    "exhibition"
                ].extend(
                    result[
                        "exhibition_rows"
                    ]
                )

                buffers[
                    "race_condition"
                ].append(
                    result[
                        "race_condition_row"
                    ]
                )

                buffers[
                    "racer_condition"
                ].extend(
                    result[
                        "racer_condition_rows"
                    ]
                )

                if not result.get(
                    "exhibition_complete"
                ):
                    day[
                        "exhibition_incomplete"
                    ] += 1

                    total[
                        "exhibition_incomplete"
                    ] += 1

                if (
                    completed <= 10
                    or completed % 25 == 0
                    or completed == len(races)
                ):
                    elapsed = (
                        time.monotonic()
                        - started
                    )

                    print(
                        f"progress "
                        f"{completed}/{len(races)} "
                        f"race_id={rid} "
                        f"exhibition="
                        f"{result.get('exhibition_count')}/6 "
                        f"elapsed={elapsed:.1f}s",
                        flush=True,
                    )

            if (
                completed_since_flush
                >= BULK_RACES
            ):

                saved = flush_buffers(
                    buffers
                )

                for key, value in (
                    saved.items()
                ):
                    day[key] += value
                    total[key] += value

                completed_since_flush = 0

                print(
                    f"bulk_flush "
                    f"completed={completed}/"
                    f"{len(races)} "
                    f"weather="
                    f"{saved['weather_rows']} "
                    f"exhibition="
                    f"{saved['exhibition_rows']} "
                    f"race_condition="
                    f"{saved['race_condition_rows']} "
                    f"racer_condition="
                    f"{saved['racer_condition_rows']}",
                    flush=True,
                )

    # 残りを保存
    if any(
        buffers[key]
        for key in buffers
    ):
        saved = flush_buffers(
            buffers
        )

        for key, value in (
            saved.items()
        ):
            day[key] += value
            total[key] += value

        print(
            f"final_flush "
            f"weather="
            f"{saved['weather_rows']} "
            f"exhibition="
            f"{saved['exhibition_rows']} "
            f"race_condition="
            f"{saved['race_condition_rows']} "
            f"racer_condition="
            f"{saved['racer_condition_rows']}",
            flush=True,
        )

    elapsed = (
        time.monotonic()
        - started
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

    print(
        f"elapsed_sec={elapsed:.1f}",
        flush=True,
    )

    if elapsed > 0:
        print(
            f"races_per_sec="
            f"{len(races) / elapsed:.2f}",
            flush=True,
        )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

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
        f"HIST_WORKERS={WORKERS}",
        flush=True,
    )

    print(
        f"HIST_BULK_RACES={BULK_RACES}",
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
        f"HIST_REQUIRE_SIX_EXHIBITION="
        f"{REQUIRE_SIX_EXHIBITION}",
        flush=True,
    )

    print(
        "HTTP取得・parseのみ並列。"
        "DB保存はbulk upsert。",
        flush=True,
    )

    print(
        "LINE通知・候補判定・購入処理なし。",
        flush=True,
    )

    total = defaultdict(int)

    started = time.monotonic()

    for date_str in daterange(
        START_DATE,
        END_DATE,
    ):
        process_date(
            date_str,
            total,
        )

    elapsed = (
        time.monotonic()
        - started
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
        f"elapsed_sec={elapsed:.1f}",
        flush=True,
    )

    if elapsed > 0:
        print(
            f"races_per_sec="
            f"{total['races'] / elapsed:.2f}",
            flush=True,
        )

    print(
        "=== historical beforeinfo "
        "backfill finished ===",
        flush=True,
    )


if __name__ == "__main__":
    main()