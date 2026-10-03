from __future__ import annotations

import os
import sys
import time

import psycopg

ATTEMPTS = 18
SLEEP_SEC = 10
CONNECT_TIMEOUT = 5

def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("CANDIDATE_V4_WAKE_FAIL=DATABASE_URL_MISSING", file=sys.stderr, flush=True)
        return 2

    for attempt in range(1, ATTEMPTS + 1):
        try:
            with psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET default_transaction_read_only = on")
                    cur.execute("SELECT 1")
                    row = cur.fetchone()
                    if row and row[0] == 1:
                        print(f"CANDIDATE_V4_WAKE_PASS=1 ATTEMPT={attempt}", flush=True)
                        return 0
        except Exception as exc:
            print(
                f"CANDIDATE_V4_WAKE_RETRY={attempt} ERROR={type(exc).__name__}",
                flush=True,
            )
        if attempt < ATTEMPTS:
            time.sleep(SLEEP_SEC)

    print("CANDIDATE_V4_WAKE_FAIL=1", file=sys.stderr, flush=True)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
