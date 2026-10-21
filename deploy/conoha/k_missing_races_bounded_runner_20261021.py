# -*- coding: utf-8 -*-
"""Bounded operator for ConoHa historical K missing-race restoration.

Default: read-only preview. --apply additionally requires the separate
CONFIRM_V5_K_RACE_REPAIR=YES gate, and only starts the existing insert-only
worker (never the legacy unrestricted upsert collector).
Run as postgres. Does not touch timers, weights, or settled result entries.
One process at a time; restart after failures only after manual DB inspection.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys

import psycopg

WORKER = Path(__file__).with_name("k_missing_races_insert_only_20261021.py")
DB = "postgresql:///railway"
LOCK = "/tmp/boat_v5_k_missing_races_runner.lock"


def snapshot(day: str) -> tuple[int, int, int, int]:
    key = day.replace("-", "") + "_"
    next_day = str(int(day.replace("-", "")) + 1) + "_"
    # Both authorized dates are October 16/17, so this next-day key is safe.
    with psycopg.connect(
        DB,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as conn:
        with conn.cursor() as c:
            c.execute(
                """
                WITH rs AS (
                    SELECT r.race_id, count(e.lane) AS n,
                           count(DISTINCT e.lane) AS lanes
                    FROM public.v2_races AS r
                    LEFT JOIN public.v2_race_entries AS e
                      ON e.race_id=r.race_id
                    WHERE r.race_id >= %s AND r.race_id < %s
                    GROUP BY r.race_id
                )
                SELECT count(*)::int, coalesce(sum(n),0)::int,
                       count(*) FILTER(WHERE n<>6 OR lanes<>6)::int,
                       (SELECT count(*)::int FROM public.v2_results
                        WHERE race_id >= %s AND race_id < %s)
                FROM rs
                """,
                (key, next_day, key, next_day),
            )
            row = c.fetchone()
    assert row is not None
    return tuple(int(v) for v in row)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--day", choices=("2026-10-16", "2026-10-17"), required=True)
    p.add_argument("--batches", type=int, default=1)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    if not 1 <= args.batches <= 2:
        raise SystemExit("STOP: --batches must be 1 or 2")
    if args.apply and os.environ.get("CONFIRM_V5_K_RACE_REPAIR") != "YES":
        raise SystemExit("STOP: explicit apply gate absent")
    if not WORKER.is_file():
        raise SystemExit("STOP: source worker unavailable")

    # Prevent concurrent invocations of this helper. Existing daily jobs are
    # not restarted or reconfigured.
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("STOP: another bounded recovery runner is active")

        before = snapshot(args.day)
        print(f"START day={args.day} races,entries,bad6,results={before}", flush=True)
        if before[2] != 0:
            raise SystemExit("STOP: existing incomplete/duplicate rosters; inspect manually")

        if not args.apply:
            cmd = [sys.executable, str(WORKER), "--day", args.day, "--limit", "6"]
            outcome = subprocess.run(cmd, check=False)
            if outcome.returncode:
                raise SystemExit(f"STOP: dry-run worker exit={outcome.returncode}")
            if snapshot(args.day) != before:
                raise SystemExit("STOP: DB changed during dry-run; inspect changes")
            print("BOUNDED_DRY_RUN_OK_NO_DB_WRITES", flush=True)
            return 0

        for number in range(1, args.batches + 1):
            before = snapshot(args.day)
            print(f"=== BATCH {number}/{args.batches} BEFORE={before} ===", flush=True)
            cmd = [sys.executable, str(WORKER), "--day", args.day,
                   "--limit", "6", "--apply"]
            completed = subprocess.run(cmd, check=False)
            after = snapshot(args.day)
            delta = tuple(a - b for a, b in zip(after, before))
            print(f"AFTER={after} DELTA={delta}", flush=True)
            if completed.returncode:
                raise SystemExit("STOP: worker failed; do not rerun before checking saved IDs")
            added = delta[0]
            if (not 1 <= added <= 6 or delta[1] != 6 * added
                    or delta[2] != 0 or delta[3] != added):
                raise SystemExit("STOP: post-batch counts inconsistent; inspect DB, do not rerun")
            print(f"BOUNDED_BATCH_PASS number={number} added={added}", flush=True)
            if added < 6:
                print("PARTIAL_BATCH_STOP: likely approaching completion", flush=True)
                break
        print("BOUNDED_RUN_DONE", flush=True)
        return 0
    finally:
        os.close(fd)


if __name__ == "__main__":
    sys.exit(main())
