import os
import psycopg


def main():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    print("=== Railway Postgres connection test ===")
    print("DATABASE_URL: found")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select now(), current_database(), current_user;")
            row = cur.fetchone()

    print("connected: OK")
    print(f"now: {row[0]}")
    print(f"database: {row[1]}")
    print(f"user: {row[2]}")
    print("=== test finished ===")


if __name__ == "__main__":
    main()