import os
import psycopg


DDL_STATEMENTS = [
    """
    create table if not exists v2_venues (
        venue_code text primary key,
        venue_name text,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_races (
        race_id text primary key,
        race_date date,
        venue_code text,
        venue_name text,
        race_no integer,
        race_title text,
        deadline_at timestamptz,
        status text,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_race_entries (
        id bigserial primary key,
        race_id text not null,
        lane integer not null,
        racer_no text,
        racer_name text,
        class text,
        branch text,
        age integer,
        weight numeric,
        f_count integer,
        l_count integer,
        avg_st numeric,
        national_win_rate numeric,
        national_2rate numeric,
        local_win_rate numeric,
        local_2rate numeric,
        motor_no text,
        motor_2rate numeric,
        boat_no text,
        boat_2rate numeric,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now(),
        unique (race_id, lane)
    );
    """,

    """
    create table if not exists v2_results (
        race_id text primary key,
        race_date date,
        venue_code text,
        race_no integer,
        trifecta_ticket text,
        trifecta_payout integer,
        finish_order text,
        winning_method text,
        official boolean not null default false,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_odds_trifecta (
        id bigserial primary key,
        race_id text not null,
        race_date date,
        venue_code text,
        race_no integer,
        ticket text not null,
        odds numeric,
        source text,
        captured_at timestamptz not null default now(),
        raw jsonb,
        created_at timestamptz not null default now(),
        unique (race_id, ticket, source)
    );
    """,

    """
    create table if not exists v2_realtime_odds_snapshots (
        id bigserial primary key,
        race_id text not null,
        ticket text not null,
        odds numeric,
        captured_at timestamptz not null default now(),
        source text,
        raw jsonb,
        created_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_exhibition (
        id bigserial primary key,
        race_id text not null,
        lane integer not null,
        exhibition_time numeric,
        tilt numeric,
        course integer,
        start_timing numeric,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now(),
        unique (race_id, lane)
    );
    """,

    """
    create table if not exists v2_race_weather (
        race_id text primary key,
        weather text,
        wind_speed numeric,
        wind_direction text,
        wave_height numeric,
        air_temp numeric,
        water_temp numeric,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_feature_snapshots (
        id bigserial primary key,
        race_id text not null,
        selector_mode text,
        features jsonb,
        raw jsonb,
        created_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_realtime_decisions (
        id bigserial primary key,
        race_id text not null,
        race_date date,
        venue_code text,
        race_no integer,
        run_at timestamptz not null default now(),
        selector_mode text,
        decision text,
        decision_rank text,
        ticket text,
        odds numeric,
        probability numeric,
        expected_value numeric,
        reason text,
        selected_tickets jsonb,
        raw jsonb,
        created_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_learning_daily_reports (
        report_date date primary key,
        total_races integer default 0,
        decisions integer default 0,
        buy_count integer default 0,
        hit_count integer default 0,
        stake integer default 0,
        return_amount integer default 0,
        profit integer default 0,
        roi numeric,
        raw jsonb,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    );
    """,

    """
    create table if not exists v2_line_notifications (
        id bigserial primary key,
        sent_at timestamptz not null default now(),
        notification_type text,
        race_id text,
        message text,
        status text,
        raw jsonb,
        created_at timestamptz not null default now()
    );
    """,

    """
    create index if not exists idx_v2_races_date
    on v2_races (race_date);
    """,

    """
    create index if not exists idx_v2_races_venue_date
    on v2_races (venue_code, race_date);
    """,

    """
    create index if not exists idx_v2_race_entries_race_id
    on v2_race_entries (race_id);
    """,

    """
    create index if not exists idx_v2_results_date
    on v2_results (race_date);
    """,

    """
    create index if not exists idx_v2_odds_race_id
    on v2_odds_trifecta (race_id);
    """,

    """
    create index if not exists idx_v2_odds_race_date
    on v2_odds_trifecta (race_date);
    """,

    """
    create index if not exists idx_v2_realtime_decisions_race_id
    on v2_realtime_decisions (race_id);
    """,

    """
    create index if not exists idx_v2_realtime_decisions_run_at
    on v2_realtime_decisions (run_at);
    """,
]


def main():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    print("=== Railway Postgres schema bootstrap ===")
    print("DATABASE_URL: found")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for sql in DDL_STATEMENTS:
                cur.execute(sql)

            cur.execute("""
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_name like 'v2_%'
                order by table_name;
            """)

            tables = cur.fetchall()

        conn.commit()

    print("schema create: OK")
    print("created / existing tables:")
    for row in tables:
        print(f"- {row[0]}")
    print("=== schema bootstrap finished ===")


if __name__ == "__main__":
    main()