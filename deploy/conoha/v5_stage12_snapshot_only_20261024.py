#!/usr/bin/env python3
"""One-night COPY-FIRST for the 12 un-staged V5 shared families.

Adds ONLY isolated boat_data_stage physical snapshot tables (not the 13 live
boat_data VIEWs). Never changes legacy source, its collectors, write routes,
timers, BUY or backups. Each table CREATE + INSERT SELECT + rowcount checks +
completion comment is ONE transaction. On failure, the current table rolls back.
Existing stage tables are never dropped/truncated/re-copied. This is NOT CDC,
a live replica, a final equality proof, or production cutover.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from datetime import datetime
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
LOCK = 2026102501
MARKER = "BOAT_V5_STAGE_ONLY_SNAPSHOT_20261025"
GIB = 1024 ** 3


def now():
    return datetime.now(TZ)


def log(*items):
    print(now().isoformat(timespec="seconds"), *items, flush=True)


def remaining_seconds():
    n = now()
    end = n.replace(hour=6, minute=10, second=0, microsecond=0)
    if not ((n.hour == 2 and n.minute >= 50) or 3 <= n.hour < 6 or
            (n.hour == 6 and n.minute < 10)):
        return 0
    return max(0, (end - n).total_seconds())


def scalar(conn, statement, args=()):
    with conn.cursor() as cur:
        cur.execute(statement, args)
        rec = cur.fetchone()
        return rec[0] if rec else None


def relation(schema, name):
    return sql.Identifier(schema, name)


def check_known_collectors_idle():
    # No stop/restart: refuse to compete with still-running scheduled collectors.
    for unit in ("boat-v5-daily@night.service",
                 "boat-v5-midnight-catchup.service",
                 "boat-v5-forward-window.service",
                 "boat-v5-daily@morning.service"):
        result = subprocess.run(
            ["systemctl", "show", unit, "--property=ActiveState", "--value"],
            capture_output=True, text=True, timeout=5, check=True)
        if result.stdout.strip() != "inactive":
            raise RuntimeError("HOLD: collector not idle: " + unit)


def assert_runtime(conn):
    if os.environ.get("V5_STAGE12_COPY_APPROVED") != "YES":
        raise RuntimeError("HOLD: explicit STAGING-ONLY flag absent")
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD: expected local socket railway URL")
    if remaining_seconds() < 120:
        raise RuntimeError("HOLD: outside 02:50-06:10 JST stage-only window")
    if scalar(conn, "SELECT current_database()") != "railway":
        raise RuntimeError("HOLD: incorrect database")
    if scalar(conn, "SELECT current_user") != "postgres":
        raise RuntimeError("HOLD: run as postgres")
    if scalar(conn, "SELECT to_regnamespace('boat_data_stage')") is None:
        raise RuntimeError("HOLD: existing protected boat_data_stage schema absent")
    if scalar(conn, "SELECT to_regclass('boat_data_stage.venues')") is None:
        raise RuntimeError("HOLD: existing venues stage missing")
    if scalar(conn, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
              ("boat_data_stage.venues",)) != "r":
        raise RuntimeError("HOLD: venues stage no longer physical")
    if scalar(conn, "SELECT count(*) FROM boat_data_stage.venues") != 24:
        raise RuntimeError("HOLD: preserved venues stage expected 24 rows")
    check_known_collectors_idle()
    if not scalar(conn, "SELECT pg_try_advisory_lock(%s)", (LOCK,)):
        raise RuntimeError("HOLD: another V5 stage copy is running")
    for src, dst in SOURCES:
        if scalar(conn, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
                  ("public." + src,)) != "r":
            raise RuntimeError("HOLD: source missing/nonphysical: " + src)
        if scalar(conn, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
                  ("boat_data." + dst,)) != "v":
            raise RuntimeError("HOLD: live read VIEW changed: " + dst)
        existing = scalar(conn, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
                          ("boat_data_stage." + dst,))
        if existing not in (None, "r"):
            raise RuntimeError("HOLD: conflicting staging object: " + dst)


def table_stage_status(conn, source, dest):
    stage_name = "boat_data_stage." + dest
    kind = scalar(conn, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
                  (stage_name,))
    if kind is None:
        return "ABSENT"
    if kind != "r":
        raise RuntimeError("HOLD: stage is not a physical table: " + stage_name)
    comment = scalar(conn, "SELECT obj_description(to_regclass(%s), 'pg_class')",
                     (stage_name,))
    expected_prefix = MARKER + " source=public." + source + " "
    if not (isinstance(comment, str) and comment.startswith(expected_prefix)):
        raise RuntimeError("HOLD: existing stage has no matching completion proof: "
                           + stage_name)
    return "COMMITTED_PREVIOUSLY"


def disk_guard(conn, source):
    datadir = scalar(conn, "SHOW data_directory")
    free = shutil.disk_usage(datadir).free
    size = scalar(conn, "SELECT pg_total_relation_size(to_regclass(%s))",
                  ("public." + source,))
    minimum = max(16 * GIB, 3 * int(size) + 6 * GIB)
    log("SPACE_CHECK", source, "free_gib=%.2f" % (free / GIB),
        "min_gib=%.2f" % (minimum / GIB))
    if free < minimum:
        raise RuntimeError("HOLD: insufficient disk/WAL headroom")
    return int(size)


def copy_one(conn, source, dest):
    remain = remaining_seconds()
    if remain < 180:
        raise RuntimeError("HOLD: not enough time before 06:10 stop")
    check_known_collectors_idle()
    size = disk_guard(conn, source)
    timeout = int(min(1800, remain - 90))
    if timeout < 90:
        raise RuntimeError("HOLD: statement timeout too short")
    log("COPY_BEGIN", "public." + source, "=> boat_data_stage." + dest,
        "source_total_mb=" + str(size // 1048576), "statement_seconds=" + str(timeout))
    with conn.transaction():
        with conn.cursor() as c:
            c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            c.execute("SELECT set_config('lock_timeout', '1500ms', true)")
            c.execute("SELECT set_config('statement_timeout', %s, true)",
                      (str(timeout * 1000),))
            c.execute("SELECT set_config('work_mem', '8MB', true)")
            c.execute("SELECT set_config('maintenance_work_mem', '64MB', true)")
            # Do not clone SERIAL/identity/generated defaults or source triggers.
            # Physical stage is a snapshot, never a writer destination.
            c.execute(sql.SQL(
                "CREATE TABLE {} (LIKE {} INCLUDING ALL EXCLUDING DEFAULTS "
                "EXCLUDING IDENTITY EXCLUDING GENERATED)"
            ).format(relation("boat_data_stage", dest), relation("public", source)))
            c.execute(sql.SQL("INSERT INTO {} SELECT * FROM {}").format(
                relation("boat_data_stage", dest), relation("public", source)))
            written = c.rowcount
            c.execute(sql.SQL("SELECT count(*) FROM {}").format(
                relation("public", source)))
            source_count = c.fetchone()[0]
            c.execute(sql.SQL("SELECT count(*) FROM {}").format(
                relation("boat_data_stage", dest)))
            stage_count = c.fetchone()[0]
            if not (written == source_count == stage_count):
                raise RuntimeError("HOLD: transaction row-count mismatch; rollback")
            stamp = now().isoformat(timespec="seconds")
            note = (MARKER + " source=public." + source +
                    " count=" + str(source_count) + " captured_jst=" + stamp +
                    " status=INITIAL_SNAPSHOT_NOT_CDC_NOT_LIVE")
            c.execute(sql.SQL("COMMENT ON TABLE {} IS {}").format(
                relation("boat_data_stage", dest), sql.Literal(note)))
    log("COPY_COMMITTED", dest, "rows=" + str(stage_count),
        "NOTE=INITIAL_SNAPSHOT_ONLY")


def main():
    conn = None
    try:
        if os.environ.get("DATABASE_URL") != "postgresql:///railway":
            raise RuntimeError("HOLD: wrong database endpoint")
        if remaining_seconds() < 120:
            raise RuntimeError("HOLD: run only 02:50-06:10 JST")
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                             connect_timeout=8) as conn:
            assert_runtime(conn)
            pending = []
            done = []
            for source, dest in SOURCES:
                status = table_stage_status(conn, source, dest)
                (done if status != "ABSENT" else pending).append((source, dest))
            # Smallest first to maximize committed families before the deadline.
            pending.sort(key=lambda pair: scalar(
                conn, "SELECT pg_total_relation_size(to_regclass(%s))",
                ("public." + pair[0],)))
            log("STAGE12_PLAN", "already_done=" + str(len(done)),
                "todo=" + str(len(pending)),
                "venues_protected=24")
            for source, dest in pending:
                copy_one(conn, source, dest)
                done.append((source, dest))
            log("STAGE12_INITIAL_COPY_PASS", "families=" + str(len(done)),
                "of_12", "live_routes_unchanged=YES",
                "final_delta=NOT_DONE", "cutover=NO_GO", "BUY=OFF")
        return 0
    except Exception as exc:
        # Never include connection strings or credentials in logs.
        log("STAGE12_HOLD", type(exc).__name__,
            str(exc).split("\n")[0][:250] if not isinstance(exc, psycopg.Error)
            else (exc.diag.sqlstate or "PG_ERROR"))
        log("LEGACY_COLLECTORS_UNTOUCHED", "BUY_OFF",
            "PARTIAL_STAGE_SNAPSHOTS_MAY_BE_COMMITTED",
            "NO_PRODUCTION_CUTOVER")
        return 2


if __name__ == "__main__":
    sys.exit(main())
