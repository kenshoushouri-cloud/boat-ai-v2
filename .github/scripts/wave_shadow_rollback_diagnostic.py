# -*- coding: utf-8 -*-
"""Rollback-only schema/upsert diagnostic for wave final Shadow collector.

Runs the collector's proposed DDL and generated rows inside one PostgreSQL
transaction, verifies the rows are visible inside that transaction, then
explicitly rolls back and verifies the database is exactly as it was before.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

import collect_wave_venue_lane_final_shadow_pg as collector
from db_pg import _insert_one

TABLE = "v2_wave_venue_lane_final_shadow"


def table_state(conn):
    with conn.cursor() as cur:
        cur.execute(
            """select exists(
                 select 1 from information_schema.tables
                 where table_schema='public' and table_name=%s
               ) ok""",
            (TABLE,),
        )
        exists = bool(cur.fetchone()["ok"])
        count = None
        if exists:
            cur.execute(f"select count(*)::bigint n from {TABLE}")
            count = int(cur.fetchone()["n"])
        return exists, count


def main():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required")

    print("WAVE_ROLLBACK_MODE=rollback_only", flush=True)
    print("WAVE_ROLLBACK_POLICY=no_commit_no_prediction_no_line", flush=True)

    profile = collector.load_profile()
    live = collector.load_live_rows()
    rows, stats = collector.build_rows(profile, live)
    print(f"WAVE_ROLLBACK_PROFILE_GROUPS={len(profile)}", flush=True)
    print(f"WAVE_ROLLBACK_LIVE_ROWS={len(live)}", flush=True)
    print(f"WAVE_ROLLBACK_COMPLETE_RACES={stats['complete']}", flush=True)
    print(f"WAVE_ROLLBACK_COVERED_RACES={stats['covered']}", flush=True)
    print(f"WAVE_ROLLBACK_GENERATED_ROWS={len(rows)}", flush=True)
    if not rows:
        raise RuntimeError("no generated rows; rollback upsert diagnostic would be meaningless")

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as check:
        before_exists, before_count = table_state(check)
    print(f"WAVE_ROLLBACK_BEFORE_EXISTS={int(before_exists)}", flush=True)
    print(f"WAVE_ROLLBACK_BEFORE_COUNT={before_count if before_count is not None else 'NA'}", flush=True)

    conn = psycopg.connect(url, row_factory=dict_row, autocommit=False)
    try:
        with conn.cursor() as cur:
            for ddl in collector.DDL:
                cur.execute(ddl)
            for row in rows:
                _insert_one(
                    cur,
                    TABLE,
                    row,
                    ["race_id", "snapshot_label", "profile_version", "weight"],
                    None,
                )
            cur.execute(
                f"""select count(*)::bigint n
                    from {TABLE}
                    where race_date=%s and snapshot_label=%s and profile_version=%s""",
                (collector.TARGET_DATE, collector.SNAPSHOT_LABEL, collector.PROFILE_VERSION),
            )
            inside = int(cur.fetchone()["n"])
            expected_unique = len({
                (r["race_id"], r["snapshot_label"], r["profile_version"], float(r["weight"]))
                for r in rows
            })
            if inside < expected_unique:
                raise RuntimeError(
                    f"inside-transaction row count too small: inside={inside} expected_at_least={expected_unique}"
                )
            print(f"WAVE_ROLLBACK_INSIDE_TARGET_ROWS={inside}", flush=True)
            print(f"WAVE_ROLLBACK_EXPECTED_UNIQUE_ROWS={expected_unique}", flush=True)
        conn.rollback()
        print("WAVE_ROLLBACK_TRANSACTION=ROLLED_BACK", flush=True)
    finally:
        conn.close()

    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as check:
        after_exists, after_count = table_state(check)
    print(f"WAVE_ROLLBACK_AFTER_EXISTS={int(after_exists)}", flush=True)
    print(f"WAVE_ROLLBACK_AFTER_COUNT={after_count if after_count is not None else 'NA'}", flush=True)

    same = before_exists == after_exists and before_count == after_count
    print(f"WAVE_ROLLBACK_STATE_UNCHANGED={int(same)}", flush=True)
    if not same:
        raise RuntimeError("database state changed despite rollback")
    print("WAVE_ROLLBACK_RESULT=PASS_ROLLBACK_ONLY", flush=True)


if __name__ == "__main__":
    main()
