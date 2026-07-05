import os
import psycopg


TABLES = [
    "v2_venues",
    "v2_races",
    "v2_race_entries",
    "v2_results",
    "v2_odds_trifecta",
    "v2_realtime_odds_snapshots",
    "v2_exhibition",
    "v2_race_weather",
    "v2_feature_snapshots",
    "v2_realtime_decisions",
    "v2_learning_daily_reports",
    "v2_line_notifications",
    "pg_health_check",
]


def main():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    print("=== Railway Postgres table check ===")
    print("DATABASE_URL: found")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for table in TABLES:
                cur.execute(
                    """
                    select exists (
                        select 1
                        from information_schema.tables
                        where table_schema = 'public'
                          and table_name = %s
                    );
                    """,
                    (table,),
                )
                exists = cur.fetchone()[0]

                if not exists:
                    print(f"{table}: missing")
                    continue

                cur.execute(f"select count(*) from {table};")
                count = cur.fetchone()[0]
                print(f"{table}: OK rows={count}")

    print("=== table check finished ===")


if __name__ == "__main__":
    main()