"""Guarded 12-table V5/V6 common-data STAGING, not production cutover.

Runs only 02:00-06:15 JST, after the 01:20 result catchup and before 07:00
daily/forward collection. Source writers/timers are never touched. Every
table is copied atomically in one repeatable-read transaction. Each target
is only a historical snapshot and MUST NOT be used by a live writer until
catch-up, indexing, privilege, FK, triggers and route checks pass separately.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import os
import shutil
import sys
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql

SOURCES = (
    ("v2_races", "races"),
    ("v2_race_entries", "entries"),
    ("v2_results", "results"),
    ("v2_result_entries", "racer_results"),
    ("v2_odds_trifecta", "trifecta_odds"),
    ("v2_racer_course_stats_snapshots", "racer_course_stats_snapshots"),
    ("v2_realtime_entry_snapshots", "entry_snapshots"),
    ("v2_realtime_exhibition_snapshots", "exhibition_snapshots"),
    ("v2_realtime_odds_snapshots", "odds_snapshots"),
    ("v2_realtime_weather_snapshots", "weather_snapshots"),
    ("v2_realtime_race_condition_snapshots", "race_condition_snapshots"),
    ("v2_realtime_racer_condition_snapshots", "racer_condition_snapshots"),
)
TZ = ZoneInfo("Asia/Tokyo")
ADVISORY_LOCK = 7310102326


def now():
    return datetime.now(TZ)


def log(*args):
    print(now().isoformat(timespec="seconds"), *args, flush=True)


def scalar(cur, query, params=()):
    cur.execute(query, params)
    row = cur.fetchone()
    return row[0] if row else None


def rel(schema, table):
    return sql.Identifier(schema, table)


def remaining_seconds():
    t = now()
    deadline = t.replace(hour=6, minute=15, second=0, microsecond=0)
    if t.hour < 2 or t >= deadline:
        return 0
    return (deadline - t).total_seconds()


def inventory(conn):
    with conn.cursor() as c:
        if scalar(c, "SELECT current_database()") != "railway":
            raise RuntimeError("STOP: wrong database")
        if scalar(c, "SELECT current_user") != "postgres":
            raise RuntimeError("STOP: must connect as postgres")
        if scalar(c, "SELECT to_regnamespace('boat_data')") is None:
            raise RuntimeError("STOP: boat_data schema not created")
        manifest = scalar(c, "SELECT to_regclass('boat_data._copy_manifest')") is not None
        rows = []
        for source, dest in SOURCES:
            old, new = "public." + source, "boat_data." + dest
            if scalar(c, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (old,)) not in ("r", "p"):
                raise RuntimeError("STOP: source table not present: " + old)
            target = scalar(c, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (new,))
            if target is not None:
                if target != "r" or not manifest:
                    raise RuntimeError("STOP: unexpected target exists: " + new)
                n = scalar(c, """SELECT count(*) FROM boat_data._copy_manifest
                    WHERE source_name=%s AND dest_name=%s AND status='STAGED_SNAPSHOT'""",
                    (old, new))
                if n != 1:
                    raise RuntimeError("STOP: existing table lacks verified manifest: " + new)
            n_generated = scalar(c, """SELECT count(*) FROM pg_attribute
                WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped
                AND (attgenerated<>'' OR attidentity<>'')""", (old,))
            n_serial = scalar(c, """SELECT count(*) FROM pg_attrdef
                WHERE adrelid=to_regclass(%s)
                  AND pg_get_expr(adbin,adrelid) LIKE 'nextval(%%'""", (old,))
            if n_generated or n_serial:
                raise RuntimeError("STOP: identity/serial needs dedicated copy: " + old)
            size = scalar(c, "SELECT pg_total_relation_size(to_regclass(%s))", (old,))
            rows.append((source, dest, size, target is not None))
            log("SOURCE", old, "=>", new, "size_mb=" + str(size // 1048576),
                "already_staged=" + str(target is not None))
        free = shutil.disk_usage(scalar(c, "SHOW data_directory")).free
        required = max(12 * 1024**3, 3 * sum(x[2] for x in rows) + 6 * 1024**3)
        log("DISK_GUARD", "free_GB=%.1f" % (free / 1024**3),
            "required_GB=%.1f" % (required / 1024**3))
        if free < required:
            raise RuntimeError("STOP: insufficient disk/WAL headroom")
    return sorted(rows, key=lambda x: x[2])


def ensure_manifest(conn):
    with conn.transaction():
        with conn.cursor() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS boat_data._copy_manifest (
              source_name text PRIMARY KEY,
              dest_name text UNIQUE NOT NULL,
              source_rows bigint NOT NULL,
              copied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
              status text NOT NULL CHECK (status='STAGED_SNAPSHOT')
            )""")


def copy_table(conn, source, dest):
    remaining = remaining_seconds()
    if remaining < 100:
        raise RuntimeError("STOP: next 07:00 collection needs quiet time")
    timeout = int(min(1200, remaining - 45))
    log("COPY_START", source, "=>", dest, "max_seconds=" + str(timeout))
    with conn.transaction():
        with conn.cursor() as c:
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            c.execute("SELECT set_config('lock_timeout', '1500ms', true)")
            c.execute("SELECT set_config('statement_timeout', %s, true)",
                      (str(timeout * 1000),))
            c.execute(sql.SQL("CREATE TABLE {} (LIKE {} INCLUDING ALL)").format(
                rel("boat_data", dest), rel("public", source)))
            c.execute(sql.SQL("INSERT INTO {} SELECT * FROM {}").format(
                rel("boat_data", dest), rel("public", source)))
            inserted = c.rowcount
            source_n = scalar(c, sql.SQL("SELECT count(*) FROM {}").format(
                rel("public", source)))
            target_n = scalar(c, sql.SQL("SELECT count(*) FROM {}").format(
                rel("boat_data", dest)))
            if inserted != source_n or target_n != source_n:
                raise RuntimeError("STOP: source/target count mismatch; rollback: " + source)
            c.execute("""INSERT INTO boat_data._copy_manifest
                (source_name, dest_name, source_rows, status)
                VALUES (%s, %s, %s, 'STAGED_SNAPSHOT')""",
                ("public." + source, "boat_data." + dest, source_n))
            log("SNAPSHOT_SAME_TRANSACTION_COUNTS_OK",
                dest, "rows=" + str(target_n))
    log("COPY_COMMITTED", dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and os.environ.get("CONFIRM_BOAT_BULK_STAGE") != "YES":
        parser.error("--apply requires CONFIRM_BOAT_BULK_STAGE=YES")
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL is required")
    log("MODE", "APPLY_STAGING_ONLY" if args.apply else "PREVIEW_READONLY")
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        with conn.cursor() as c:
            if not scalar(c, "SELECT pg_try_advisory_lock(%s)", (ADVISORY_LOCK,)):
                raise RuntimeError("STOP: another staging process already running")
        try:
            plan = inventory(conn)
            if not args.apply:
                log("STAGING_PREVIEW_DONE_NO_DB_WRITES", "tables=" + str(len(plan)))
                return
            if not remaining_seconds():
                raise RuntimeError("STOP: staging allowed only at 02:00-06:15 JST")
            ensure_manifest(conn)
            copied, skipped = 0, 0
            for source, dest, _, exists in plan:
                if exists:
                    log("SKIP_PREVIOUS_STAGING", dest, "NOT_LIVE_VERIFIED")
                    skipped += 1
                else:
                    copy_table(conn, source, dest)
                    copied += 1
            log("BULK_STAGING_COMPLETE", "new=" + str(copied),
                "earlier=" + str(skipped),
                "NO_PRODUCTION_CUTOVER_NO_SOURCE_DELETES")
        finally:
            with conn.cursor() as c:
                c.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK,))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("GUARDED_BULK_STAGE_STOP", type(exc).__name__, str(exc))
        sys.exit(1)
