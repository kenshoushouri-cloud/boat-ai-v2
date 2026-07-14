# -*- coding: utf-8 -*-
"""
diagnose_feature_data_inventory_pg.py

Railway Postgresに保存済みの気象・展示・オッズ・モーター関連データを棚卸しします。
読み取り専用です。LINE送信・DB更新は行いません。

Railway Start Command:
    python -u diagnose_feature_data_inventory_pg.py
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
END_DATE = os.getenv("DIAG_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("DIAG_START_DATE") or (
    datetime.strptime(END_DATE, "%Y-%m-%d") - timedelta(days=44)
).strftime("%Y-%m-%d")
SAMPLE_LIMIT = max(1, int(os.getenv("DIAG_SAMPLE_LIMIT", "5")))

TARGET_TABLES = [
    "v2_races",
    "v2_race_weather",
    "v2_exhibition",
    "v2_realtime_odds_snapshots",
    "v2_odds_trifecta",
    "v2_race_entries",
    "v2_results",
    "v2_feature_snapshots",
    "v2_realtime_decisions",
]

ALIASES = {
    "v2_race_weather": {
        "weather": ["weather", "weather_text", "weather_name"],
        "wind_direction": ["wind_direction", "wind_dir", "wind"],
        "wind_speed": ["wind_speed", "wind_speed_mps", "wind_mps"],
        "wave_height": ["wave_height", "wave_height_cm", "wave_cm"],
        "air_temperature": ["air_temperature", "temperature", "air_temp", "temperature_c"],
        "water_temperature": ["water_temperature", "water_temp", "water_temperature_c"],
        "observed_at": ["observed_at", "fetched_at", "captured_at", "created_at", "updated_at"],
    },
    "v2_exhibition": {
        "lane": ["lane", "course", "boat_no"],
        "exhibition_time": ["exhibition_time", "tenji_time", "display_time"],
        "exhibition_rank": ["exhibition_rank", "tenji_rank", "display_rank"],
        "start_timing": ["start_timing", "exhibition_st", "tenji_st"],
        "entry_course": ["entry_course", "actual_course", "course"],
        "observed_at": ["observed_at", "fetched_at", "captured_at", "created_at", "updated_at"],
    },
    "v2_race_entries": {
        "motor_no": ["motor_no", "motor_number"],
        "motor_2rate": ["motor_place2_rate", "motor_2rate", "motor_second_rate", "motor_2ren_rate"],
        "motor_win_rate": ["motor_win_rate", "motor_rate"],
        "boat_no": ["boat_no", "boat_number"],
        "boat_2rate": ["boat_place2_rate", "boat_2rate", "boat_second_rate", "boat_2ren_rate"],
    },
}


def table_exists(table: str) -> bool:
    row = fetch_one(
        """select exists (
               select 1 from information_schema.tables
               where table_schema='public' and table_name=%s
           ) as ok;""",
        (table,),
    )
    return bool(row and row.get("ok"))


def columns(table: str) -> List[str]:
    rows = fetch_all(
        """select column_name from information_schema.columns
           where table_schema='public' and table_name=%s
           order by ordinal_position;""",
        (table,),
    )
    return [str(r.get("column_name")) for r in rows]


def pick(cols: Sequence[str], names: List[str]) -> Optional[str]:
    s = set(cols)
    for n in names:
        if n in s:
            return n
    return None


def date_col(cols: Sequence[str]) -> Optional[str]:
    for n in ("race_date", "target_date", "date"):
        if n in cols:
            return n
    return None


def count_rows(table: str, dcol: Optional[str]) -> Dict[str, Any]:
    if dcol:
        return fetch_one(
            f"""select count(*) as rows, min({dcol}) as min_date, max({dcol}) as max_date
                from {table}
                where {dcol} >= %s and {dcol} <= %s;""",
            (START_DATE, END_DATE),
        ) or {}
    return fetch_one(f"select count(*) as rows from {table};") or {}


def non_null_count(table: str, dcol: Optional[str], col: str) -> int:
    if dcol:
        row = fetch_one(
            f"""select count(*) as n from {table}
                where {dcol} >= %s and {dcol} <= %s and {col} is not null;""",
            (START_DATE, END_DATE),
        )
    else:
        row = fetch_one(f"select count(*) as n from {table} where {col} is not null;")
    return int((row or {}).get("n") or 0)


def distinct_races(table: str, dcol: Optional[str], cols: Sequence[str]) -> int:
    if "race_id" not in cols:
        return 0
    if dcol:
        row = fetch_one(
            f"""select count(distinct race_id) as n from {table}
                where {dcol} >= %s and {dcol} <= %s;""",
            (START_DATE, END_DATE),
        )
    else:
        row = fetch_one(f"select count(distinct race_id) as n from {table};")
    return int((row or {}).get("n") or 0)


def sample_rows(table: str, cols: Sequence[str], dcol: Optional[str]) -> None:
    preferred = [
        c for c in (
            "race_id", "race_date", "venue_id", "race_no", "lane",
            "weather", "wind_direction", "wind_speed", "wave_height",
            "air_temperature", "water_temperature", "exhibition_time",
            "exhibition_rank", "start_timing", "motor_no",
            "motor_place2_rate", "snapshot_label", "captured_at",
            "observed_at", "created_at"
        ) if c in cols
    ]
    if not preferred:
        preferred = list(cols[:8])
    if not preferred:
        return
    sel = ", ".join(preferred)
    if dcol:
        rows = fetch_all(
            f"""select {sel} from {table}
                where {dcol} >= %s and {dcol} <= %s
                order by {dcol} desc limit %s;""",
            (START_DATE, END_DATE, SAMPLE_LIMIT),
        )
    else:
        rows = fetch_all(f"select {sel} from {table} limit %s;", (SAMPLE_LIMIT,))
    for r in rows:
        print("  sample:", r, flush=True)


def race_coverage(table: str) -> None:
    if not (table_exists("v2_races") and table_exists(table)):
        return
    cols = columns(table)
    if "race_id" not in cols:
        return
    dcol = date_col(cols)
    base = fetch_one(
        """select count(distinct race_id) as n from v2_races
           where race_date >= %s and race_date <= %s;""",
        (START_DATE, END_DATE),
    )
    base_n = int((base or {}).get("n") or 0)

    if dcol:
        got = fetch_one(
            f"""select count(distinct race_id) as n from {table}
                where {dcol} >= %s and {dcol} <= %s;""",
            (START_DATE, END_DATE),
        )
    else:
        got = fetch_one(
            f"""select count(distinct t.race_id) as n
                from {table} t join v2_races r on r.race_id=t.race_id
                where r.race_date >= %s and r.race_date <= %s;""",
            (START_DATE, END_DATE),
        )
    got_n = int((got or {}).get("n") or 0)
    pct = got_n / base_n * 100 if base_n else 0
    print(f"{table} distinct-race coverage={got_n}/{base_n} ({pct:.1f}%)", flush=True)

    if table == "v2_exhibition":
        lane = pick(cols, ["lane", "course", "boat_no"])
        if lane:
            if dcol:
                row = fetch_one(
                    f"""select count(*) as n from (
                            select race_id from {table}
                            where {dcol} >= %s and {dcol} <= %s
                            group by race_id
                            having count(distinct {lane})=6
                        ) x;""",
                    (START_DATE, END_DATE),
                )
            else:
                row = fetch_one(
                    f"""select count(*) as n from (
                            select e.race_id
                            from {table} e join v2_races r on r.race_id=e.race_id
                            where r.race_date >= %s and r.race_date <= %s
                            group by e.race_id
                            having count(distinct e.{lane})=6
                        ) x;""",
                    (START_DATE, END_DATE),
                )
            full_n = int((row or {}).get("n") or 0)
            full_pct = full_n / base_n * 100 if base_n else 0
            print(f"v2_exhibition full-6-lane coverage={full_n}/{base_n} ({full_pct:.1f}%)", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ diagnose_feature_data_inventory_pg.py VERSION 2026-07-14", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("読み取り専用です。LINE送信・DB更新は行いません。", flush=True)

    for table in TARGET_TABLES:
        print(f"{table}: {'YES' if table_exists(table) else 'NO'}", flush=True)

    for table in TARGET_TABLES:
        if not table_exists(table):
            continue
        cols = columns(table)
        dcol = date_col(cols)
        stats = count_rows(table, dcol)
        rows = int(stats.get("rows") or 0)

        print("\n" + "=" * 72, flush=True)
        print(f"TABLE={table}", flush=True)
        print(f"columns ({len(cols)}): {', '.join(cols)}", flush=True)
        print(
            f"rows={rows} min_date={stats.get('min_date')} max_date={stats.get('max_date')} "
            f"distinct_races={distinct_races(table, dcol, cols)}",
            flush=True,
        )

        for logical, names in ALIASES.get(table, {}).items():
            actual = pick(cols, names)
            if not actual:
                print(f"  {logical}: column_missing", flush=True)
                continue
            n = non_null_count(table, dcol, actual)
            pct = n / rows * 100 if rows else 0
            print(f"  {logical}: column={actual} non_null={n}/{rows} ({pct:.1f}%)", flush=True)

        sample_rows(table, cols, dcol)

    print("\n" + "=" * 72, flush=True)
    print("COVERAGE SUMMARY", flush=True)
    race_coverage("v2_race_weather")
    race_coverage("v2_exhibition")

    print("\n判定目安", flush=True)
    print("- 気象coverageが低い: morning/day/night/finalの履歴保存を追加", flush=True)
    print("- 展示6艇coverageが低い: final判定前の展示取得を補強", flush=True)
    print("- motor_2rate列が無い/空: 固定値のまま。実値保存を先に追加", flush=True)
    print("- captured_at等が無い: 時系列比較用の履歴テーブルが必要", flush=True)
    print("=== feature data inventory finished ===", flush=True)


if __name__ == "__main__":
    main()