# -*- coding: utf-8 -*-
"""
pg_realtime_schema_fix.py

Railway Postgres版。
v21_realtime_collector_pg.py 実行前に、リアルタイム系テーブルの不足カラムを補正します。

Railway Start Command:
    python pg_realtime_schema_fix.py

必要Variables:
    DATABASE_URL
"""

import os
import psycopg


DDL = [
    # ----------------------------
    # create tables if missing
    # ----------------------------
    """
    create table if not exists v2_realtime_weather_snapshots (
        id bigserial primary key
    );
    """,
    """
    create table if not exists v2_realtime_exhibition_snapshots (
        id bigserial primary key
    );
    """,
    """
    create table if not exists v2_realtime_entry_snapshots (
        id bigserial primary key
    );
    """,
    """
    create table if not exists v2_realtime_odds_snapshots (
        id bigserial primary key
    );
    """,

    # ----------------------------
    # weather columns
    # ----------------------------
    "alter table v2_realtime_weather_snapshots add column if not exists race_id text;",
    "alter table v2_realtime_weather_snapshots add column if not exists race_date date;",
    "alter table v2_realtime_weather_snapshots add column if not exists venue_id text;",
    "alter table v2_realtime_weather_snapshots add column if not exists venue_code text;",
    "alter table v2_realtime_weather_snapshots add column if not exists race_no integer;",
    "alter table v2_realtime_weather_snapshots add column if not exists snapshot_label text;",
    "alter table v2_realtime_weather_snapshots add column if not exists snapshot_at timestamptz;",
    "alter table v2_realtime_weather_snapshots add column if not exists source text;",
    "alter table v2_realtime_weather_snapshots add column if not exists weather text;",
    "alter table v2_realtime_weather_snapshots add column if not exists temperature_c numeric;",
    "alter table v2_realtime_weather_snapshots add column if not exists water_temperature_c numeric;",
    "alter table v2_realtime_weather_snapshots add column if not exists wind_speed_m numeric;",
    "alter table v2_realtime_weather_snapshots add column if not exists wind_direction text;",
    "alter table v2_realtime_weather_snapshots add column if not exists wave_height_cm numeric;",
    "alter table v2_realtime_weather_snapshots add column if not exists raw jsonb;",
    "alter table v2_realtime_weather_snapshots add column if not exists updated_at timestamptz;",

    # ----------------------------
    # exhibition columns
    # ----------------------------
    "alter table v2_realtime_exhibition_snapshots add column if not exists race_id text;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists race_date date;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists venue_id text;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists venue_code text;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists race_no integer;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists snapshot_label text;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists snapshot_at timestamptz;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists source text;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists lane integer;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists exhibition_course integer;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists exhibition_time numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists exhibition_time_rank integer;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists exhibition_time_diff numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists start_timing numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists start_timing_rank integer;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists start_timing_diff numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists tilt numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists original_tilt numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists tilt_change numeric;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists raw jsonb;",
    "alter table v2_realtime_exhibition_snapshots add column if not exists updated_at timestamptz;",

    # ----------------------------
    # entry columns
    # ----------------------------
    "alter table v2_realtime_entry_snapshots add column if not exists race_id text;",
    "alter table v2_realtime_entry_snapshots add column if not exists race_date date;",
    "alter table v2_realtime_entry_snapshots add column if not exists venue_id text;",
    "alter table v2_realtime_entry_snapshots add column if not exists venue_code text;",
    "alter table v2_realtime_entry_snapshots add column if not exists race_no integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists snapshot_label text;",
    "alter table v2_realtime_entry_snapshots add column if not exists snapshot_at timestamptz;",
    "alter table v2_realtime_entry_snapshots add column if not exists source text;",
    "alter table v2_realtime_entry_snapshots add column if not exists lane integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists racer_number integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists racer_name text;",
    "alter table v2_realtime_entry_snapshots add column if not exists racer_class text;",
    "alter table v2_realtime_entry_snapshots add column if not exists original_course integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists exhibition_course integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists is_course_changed boolean;",
    "alter table v2_realtime_entry_snapshots add column if not exists motor_no integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists boat_no integer;",
    "alter table v2_realtime_entry_snapshots add column if not exists tilt numeric;",
    "alter table v2_realtime_entry_snapshots add column if not exists raw jsonb;",
    "alter table v2_realtime_entry_snapshots add column if not exists updated_at timestamptz;",

    # ----------------------------
    # odds columns
    # ----------------------------
    "alter table v2_realtime_odds_snapshots add column if not exists race_id text;",
    "alter table v2_realtime_odds_snapshots add column if not exists race_date date;",
    "alter table v2_realtime_odds_snapshots add column if not exists venue_id text;",
    "alter table v2_realtime_odds_snapshots add column if not exists venue_code text;",
    "alter table v2_realtime_odds_snapshots add column if not exists race_no integer;",
    "alter table v2_realtime_odds_snapshots add column if not exists snapshot_label text;",
    "alter table v2_realtime_odds_snapshots add column if not exists snapshot_at timestamptz;",
    "alter table v2_realtime_odds_snapshots add column if not exists source text;",
    "alter table v2_realtime_odds_snapshots add column if not exists ticket text;",
    "alter table v2_realtime_odds_snapshots add column if not exists odds numeric;",
    "alter table v2_realtime_odds_snapshots add column if not exists market_rank integer;",
    "alter table v2_realtime_odds_snapshots add column if not exists prev_odds numeric;",
    "alter table v2_realtime_odds_snapshots add column if not exists odds_delta numeric;",
    "alter table v2_realtime_odds_snapshots add column if not exists odds_delta_pct numeric;",
    "alter table v2_realtime_odds_snapshots add column if not exists prev_market_rank integer;",
    "alter table v2_realtime_odds_snapshots add column if not exists market_rank_delta integer;",
    "alter table v2_realtime_odds_snapshots add column if not exists is_favorite boolean;",
    "alter table v2_realtime_odds_snapshots add column if not exists is_odds_too_low boolean;",
    "alter table v2_realtime_odds_snapshots add column if not exists is_odds_drift boolean;",
    "alter table v2_realtime_odds_snapshots add column if not exists is_odds_steam boolean;",
    "alter table v2_realtime_odds_snapshots add column if not exists raw jsonb;",
    "alter table v2_realtime_odds_snapshots add column if not exists updated_at timestamptz;",

    # ----------------------------
    # unique indexes
    # ----------------------------
    "create unique index if not exists uq_v2_rt_weather_race_label on v2_realtime_weather_snapshots (race_id, snapshot_label);",
    "create unique index if not exists uq_v2_rt_exh_race_label_lane on v2_realtime_exhibition_snapshots (race_id, snapshot_label, lane);",
    "create unique index if not exists uq_v2_rt_entry_race_label_lane on v2_realtime_entry_snapshots (race_id, snapshot_label, lane);",
    "create unique index if not exists uq_v2_rt_odds_race_label_ticket on v2_realtime_odds_snapshots (race_id, snapshot_label, ticket);",
]


CHECK_COLUMNS = {
    "v2_realtime_weather_snapshots": ["race_id", "snapshot_label", "snapshot_at", "raw"],
    "v2_realtime_exhibition_snapshots": ["race_id", "snapshot_label", "lane", "exhibition_time", "raw"],
    "v2_realtime_entry_snapshots": ["race_id", "snapshot_label", "lane", "racer_number", "raw"],
    "v2_realtime_odds_snapshots": ["race_id", "snapshot_label", "ticket", "odds", "market_rank", "raw"],
}


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL が必要です。")

    print("=== pg realtime schema fix ===", flush=True)
    print("DATABASE_URL: found", flush=True)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for i, sql in enumerate(DDL, start=1):
                cur.execute(sql)
                if i % 20 == 0:
                    print(f"applied DDL: {i}/{len(DDL)}", flush=True)
            conn.commit()

        with conn.cursor() as cur:
            print("--- column check ---", flush=True)
            for table, cols in CHECK_COLUMNS.items():
                cur.execute(
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema = 'public'
                      and table_name = %s
                    order by ordinal_position;
                    """,
                    (table,),
                )
                existing = {r[0] for r in cur.fetchall()}
                missing = [c for c in cols if c not in existing]
                if missing:
                    print(f"{table}: NG missing={missing}", flush=True)
                else:
                    print(f"{table}: OK", flush=True)

    print("=== realtime schema fix finished ===", flush=True)


if __name__ == "__main__":
    main()