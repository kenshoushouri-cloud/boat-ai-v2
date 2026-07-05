import os
import psycopg


def main():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    print("=== Railway Postgres write test ===")
    print("DATABASE_URL: found")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                create table if not exists pg_health_check (
                    id bigserial primary key,
                    checked_at timestamptz not null default now(),
                    note text
                );
            """)

            cur.execute("""
                insert into pg_health_check (note)
                values (%s)
                returning id, checked_at, note;
            """, ("railway postgres write test ok",))

            row = cur.fetchone()

            cur.execute("select count(*) from pg_health_check;")
            count_row = cur.fetchone()

        conn.commit()

    print("write: OK")
    print(f"inserted_id: {row[0]}")
    print(f"checked_at: {row[1]}")
    print(f"note: {row[2]}")
    print(f"total_rows: {count_row[0]}")
    print("=== write test finished ===")


if __name__ == "__main__":
    main()