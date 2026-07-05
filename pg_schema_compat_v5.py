import os
import psycopg


DDL_STATEMENTS = [
    # v2_venues compatibility
    """
    alter table v2_venues
    add column if not exists venue_id text;
    """,
    """
    alter table v2_venues
    add column if not exists is_active boolean default true;
    """,
    """
    update v2_venues
    set venue_id = venue_code
    where venue_id is null
      and venue_code is not null;
    """,
    """
    create unique index if not exists ux_v2_venues_venue_id
    on v2_venues (venue_id);
    """,

    # v2_races compatibility
    """
    alter table v2_races
    add column if not exists venue_id text;
    """,
    """
    alter table v2_races
    add column if not exists race_name text;
    """,
    """
    alter table v2_races
    add column if not exists data_quality_score integer default 0;
    """,
    """
    alter table v2_races
    add column if not exists missing_count integer default 0;
    """,

    # v2_race_entries compatibility
    """
    alter table v2_race_entries
    add column if not exists course integer;
    """,
    """
    alter table v2_race_entries
    add column if not exists racer_number integer;
    """,
    """
    alter table v2_race_entries
    add column if not exists racer_class integer;
    """,
    """
    alter table v2_race_entries
    add column if not exists racer_class_text text;
    """,
    """
    alter table v2_race_entries
    add column if not exists origin text;
    """,
    """
    alter table v2_race_entries
    add column if not exists national_place2_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists national_place3_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists local_place2_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists local_place3_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists motor_place2_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists motor_place3_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists boat_place2_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists boat_place3_rate numeric;
    """,
    """
    alter table v2_race_entries
    add column if not exists recent_form jsonb;
    """,

    # v2_results compatibility
    """
    alter table v2_results
    add column if not exists result_status text;
    """,
    """
    alter table v2_results
    add column if not exists race_status text;
    """,
    """
    alter table v2_results
    add column if not exists source text;
    """,
    """
    alter table v2_results
    add column if not exists fetched_at timestamptz;
    """,
    """
    alter table v2_results
    add column if not exists first_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists second_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists third_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists fourth_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists fifth_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists sixth_lane integer;
    """,
    """
    alter table v2_results
    add column if not exists trifecta_payout_yen integer;
    """,

    # v2_odds_trifecta compatibility
    """
    alter table v2_odds_trifecta
    add column if not exists is_final boolean default true;
    """,
    """
    alter table v2_odds_trifecta
    add column if not exists fetched_at timestamptz;
    """,
    """
    create unique index if not exists ux_v2_odds_trifecta_race_ticket
    on v2_odds_trifecta (race_id, ticket);
    """,
]


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    print("=== Railway Postgres v5 compatibility schema ===")
    print("DATABASE_URL: found")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for ddl in DDL_STATEMENTS:
                cur.execute(ddl)

            cur.execute("""
                select table_name, count(*) as column_count
                from information_schema.columns
                where table_schema = 'public'
                  and table_name like 'v2_%'
                group by table_name
                order by table_name;
            """)
            rows = cur.fetchall()

        conn.commit()

    print("compat schema: OK")
    for table_name, column_count in rows:
        print(f"{table_name}: columns={column_count}")

    print("=== compatibility schema finished ===")


if __name__ == "__main__":
    main()