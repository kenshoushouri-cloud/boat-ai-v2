#!/usr/bin/env python3
"""K six-lane detail repair pilot: read-only by default, no scheduling.

Safely prepares a single verified K-file day. Writes to BOTH old source and
physical V5 stage in ONE transaction only when all offsite restore gates have
been independently proven. It NEVER updates public.v2_results, payouts,
legacy VIEWs, collectors, timers, roles or BUY. No DDL and no routing changes.

Do not use --apply until a current-generation offsite backup was RESTORED AND
VERIFIED on a genuinely separate PostgreSQL instance. Existing Oct 19 Drive
backups and Oct 23-24 VPS-local dumps do NOT satisfy that condition.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from importlib import import_module

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from v5.k_detail_backfill_gate_20261026 import EXPECTED_RACES, validate_day

JST = timezone(timedelta(hours=9))
SOURCE = "public.v2_result_entries"
STAGE = "boat_data_stage.racer_results"
DAY_COLUMNS = (
    "race_id", "lane", "racer_number", "racer_name",
    "finish_position", "finish_status", "motor_no", "boat_no",
    "exhibition_time", "start_course", "start_timing", "start_status",
    "is_flying", "is_late", "race_time", "source", "raw",
    "fetched_at", "updated_at",
)
LOCK = 2026102611


def log(*parts):
    print(datetime.now(JST).isoformat(timespec="seconds"), *parts, flush=True)


def one(cur, q, args=()):
    cur.execute(q, args)
    row = cur.fetchone()
    return row[0] if row else None


def guard_relations(cur):
    if one(cur, "SELECT current_database()") != "railway":
        raise RuntimeError("HOLD_WRONG_DATABASE")
    if one(cur, "SELECT current_user") != "postgres":
        raise RuntimeError("HOLD_WRONG_ROLE")
    for name, kind in ((SOURCE, "r"), (STAGE, "r"),
                       ("boat_data.racer_results", "v")):
        if one(cur, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
               (name,)) != kind:
            raise RuntimeError("HOLD_RELATION_SHAPE_CHANGED")
    if one(cur, "SELECT to_regclass('v5_data.raw_racer_results')") is not None:
        raise RuntimeError("HOLD_PHYSICAL_K_ROUTE_EXISTS")
    live_def = one(cur,
        "SELECT pg_get_viewdef(to_regclass('boat_data.racer_results'), true)")
    if not isinstance(live_def, str) or "v2_result_entries" not in live_def:
        raise RuntimeError("HOLD_LIVE_K_VIEW_NO_LONGER_LEGACY")
    cur.execute(
        "SELECT attname,atttypid::text,atttypmod,attnotnull,"
        "attcollation::text,attidentity,attgenerated "
        "FROM pg_attribute WHERE attrelid=to_regclass(%s) "
        "AND attnum>0 AND NOT attisdropped ORDER BY attnum", (SOURCE,))
    source_signature = cur.fetchall()
    cur.execute(
        "SELECT attname,atttypid::text,atttypmod,attnotnull,"
        "attcollation::text,attidentity,attgenerated "
        "FROM pg_attribute WHERE attrelid=to_regclass(%s) "
        "AND attnum>0 AND NOT attisdropped ORDER BY attnum", (STAGE,))
    stage_signature = cur.fetchall()
    if source_signature != stage_signature:
        raise RuntimeError("HOLD_COLUMN_TYPES_OR_CONSTRAINTS_DIFFER")
    if tuple(r[0] for r in source_signature) != DAY_COLUMNS:
        raise RuntimeError("HOLD_UNEXPECTED_COLUMN_LAYOUT")
    for relation in (SOURCE, STAGE):
        cur.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(attnum,ord) "
            "ON x.ord<=i.indnkeyatts "
            "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=x.attnum "
            "WHERE i.indrelid=to_regclass(%s) AND i.indisprimary "
            "ORDER BY x.ord", (relation,))
        if tuple(x[0] for x in cur.fetchall()) != ("race_id", "lane"):
            raise RuntimeError("HOLD_PRIMARY_KEY_CHANGED")
        if one(cur, "SELECT count(*) FROM pg_trigger "
               "WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal",
               (relation,)) != 0:
            raise RuntimeError("HOLD_UNEXPECTED_TRIGGER")
        if one(cur, "SELECT count(*) FROM pg_constraint "
               "WHERE conrelid=to_regclass(%s) AND contype='f'",
               (relation,)) != 0:
            raise RuntimeError("HOLD_UNEXPECTED_FOREIGN_KEY")


def current_known(cur, date):
    cur.execute(
        "SELECT r.race_id,rs.result_status,rs.trifecta_ticket,"
        "rs.trifecta_payout_yen "
        "FROM public.v2_races r "
        "LEFT JOIN public.v2_results rs ON rs.race_id=r.race_id "
        "WHERE r.race_date=%s ORDER BY r.race_id", (date,))
    return {
        str(rid): {
            "result_status": status,
            "trifecta_ticket": ticket,
            "trifecta_payout_yen": payout,
        }
        for rid, status, ticket, payout in cur.fetchall()
    }


def assert_empty_detail(cur, date):
    prefix = date.replace("-", "") + "_%"
    for relation in (SOURCE, STAGE):
        if one(cur,
            sql.SQL("SELECT count(*) FROM {} WHERE race_id LIKE %s").format(
                sql.Identifier(*relation.split("."))), (prefix,)) != 0:
            raise RuntimeError("HOLD_DAY_ALREADY_HAS_DETAIL_NO_OVERWRITE")


def require_current_offsite_recovery(manifest_path):
    """Administrative gate: never infer recovery from local dump existence."""
    if (os.environ.get("V5_K_BACKFILL_APPROVED") != "YES" or
            os.environ.get("V5_CURRENT_OFFSITE_RESTORE_VERIFIED") != "YES"):
        raise RuntimeError("HOLD_REQUIRES_BACKFILL_AND_OFFSITE_RESTORE_GATES")
    if not manifest_path:
        raise RuntimeError("HOLD_MISSING_RECOVERY_MANIFEST")
    p = Path(manifest_path)
    if not p.is_file() or p.is_symlink() or p.stat().st_mode & 0o077:
        raise RuntimeError("HOLD_RECOVERY_MANIFEST_MUST_BE_LOCAL_PRIVATE_FILE")
    evidence = json.loads(p.read_text(encoding="utf8"))
    if evidence.get("verdict") != "CURRENT_GENERATION_RECOVERY_PASS":
        raise RuntimeError("HOLD_INDEPENDENT_RESTORE_NOT_PROVEN")
    if evidence.get("source_database") != "railway":
        raise RuntimeError("HOLD_WRONG_RECOVERED_DATABASE")
    other_host = str(evidence.get("independent_restore_host", ""))
    if not other_host or other_host.lower() in (
            socket.gethostname().lower(), "localhost", "127.0.0.1"):
        raise RuntimeError("HOLD_RESTORE_NOT_INDEPENDENT")
    sha = str(evidence.get("current_backup_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise RuntimeError("HOLD_CURRENT_BACKUP_SHA_MISSING")
    raw_date = evidence.get("restore_verified_utc", "")
    try:
        checked = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise RuntimeError("HOLD_RESTORE_DATE_INVALID")
    if checked.tzinfo is None:
        raise RuntimeError("HOLD_RESTORE_DATE_NO_TIMEZONE")
    age = datetime.now(timezone.utc) - checked.astimezone(timezone.utc)
    if age < timedelta(0) or age > timedelta(hours=72):
        raise RuntimeError("HOLD_RESTORE_EVIDENCE_STALE")
    # A manifest is an administrative record, NOT cryptographic proof.
    # The operator must verify it corresponds to an actual separate DB restore.


def build_values(races):
    for race in races:
        rid = str(race["race_id"])
        for e in race["entries"]:
            yield (
                rid, int(e["lane"]), e.get("racer_number"),
                e.get("racer_name"), e.get("finish_position"),
                e.get("finish_status"), e.get("motor_no"), e.get("boat_no"),
                e.get("exhibition_time"), e.get("start_course"),
                e.get("start_timing"), e.get("start_status"),
                e.get("is_flying"), e.get("is_late"), e.get("race_time"),
                "official_k_file", Jsonb(dict(e))
            )


def insert_details(cur, values, table):
    # Explicit columns, no DDL, never UPSERT old details or summary payouts.
    cols = sql.SQL(",").join(sql.Identifier(x) for x in DAY_COLUMNS[:17])
    statement = sql.SQL(
        "INSERT INTO {} ({}) VALUES ({})"
    ).format(
        sql.Identifier(*table.split(".")), cols,
        sql.SQL(",").join(sql.Placeholder() for _ in DAY_COLUMNS[:17])
    )
    # Fetch timestamps are set to the same transaction timestamp in both
    # tables by their existing default values (verified schema layout).
    for v in values:
        cur.execute(statement, v)


def verify_same_rows(cur, date, required_rows):
    like = date.replace("-", "") + "_%"
    for table in (SOURCE, STAGE):
        n = one(cur, sql.SQL(
            "SELECT count(*) FROM {} WHERE race_id LIKE %s"
        ).format(sql.Identifier(*table.split("."))), (like,))
        if n != required_rows:
            raise RuntimeError("HOLD_POSTWRITE_DAY_COUNT_MISMATCH")
    cur.execute(
        "SELECT "
        "NOT EXISTS (SELECT race_id,lane,racer_number,racer_name,"
        "finish_position,finish_status,motor_no,boat_no,exhibition_time,"
        "start_course,start_timing,start_status,is_flying,is_late,"
        "race_time,source,raw FROM public.v2_result_entries "
        "WHERE race_id LIKE %s "
        "EXCEPT ALL SELECT race_id,lane,racer_number,racer_name,"
        "finish_position,finish_status,motor_no,boat_no,exhibition_time,"
        "start_course,start_timing,start_status,is_flying,is_late,"
        "race_time,source,raw FROM boat_data_stage.racer_results "
        "WHERE race_id LIKE %s), "
        "NOT EXISTS (SELECT race_id,lane,racer_number,racer_name,"
        "finish_position,finish_status,motor_no,boat_no,exhibition_time,"
        "start_course,start_timing,start_status,is_flying,is_late,"
        "race_time,source,raw FROM boat_data_stage.racer_results "
        "WHERE race_id LIKE %s "
        "EXCEPT ALL SELECT race_id,lane,racer_number,racer_name,"
        "finish_position,finish_status,motor_no,boat_no,exhibition_time,"
        "start_course,start_timing,start_status,is_flying,is_late,"
        "race_time,source,raw FROM public.v2_result_entries "
        "WHERE race_id LIKE %s)",
        (like, like, like, like))
    if cur.fetchone() != (True, True):
        raise RuntimeError("HOLD_BIDIRECTIONAL_DETAIL_PARITY_FAILED")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", choices=sorted(EXPECTED_RACES), required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--recovery-manifest")
    args = p.parse_args()
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_PG_URL_REQUIRED")
    if os.environ.get("V5_DAILY_WRITE_ROUTE_PROFILE", "legacy") != "legacy":
        raise RuntimeError("HOLD_LEGACY_K_WRITER_ROUTE_CHANGED")
    if args.apply:
        require_current_offsite_recovery(args.recovery_manifest)
        n = datetime.now(JST)
        if not (n.hour >= 3 and n.hour < 6):
            raise RuntimeError("HOLD_APPLY_ONLY_03_00_TO_05_59_JST")
    # Exactly one official K GET; do not retry failures.
    ka = import_module("audit_k_day_all_pg")
    ka.TIMEOUT = 15
    ka.TARGET_DATE = args.date
    body = ka.get_k_text(args.date)
    races = [r for sec in ka.split_venue_sections(body.splitlines())
             for r in ka.parse_section(sec)]
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8,
                         autocommit=False) as conn:
        with conn.cursor() as cur:
            if args.apply:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            else:
                cur.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout='120000ms'")
            cur.execute("SET LOCAL lock_timeout='1200ms'")
            cur.execute("SET LOCAL work_mem='8MB'")
            if not one(cur, "SELECT pg_try_advisory_xact_lock(%s)", (LOCK,)):
                raise RuntimeError("HOLD_BACKFILL_LOCK_BUSY")
            guard_relations(cur)
            known = current_known(cur, args.date)
            day_gate = validate_day(args.date, known, races)
            assert_empty_detail(cur, args.date)
            log("K_DETAIL_ONE_DAY_VALIDATED",
                "date="+args.date, "races="+str(day_gate.k_races),
                "expected_lanes="+str(day_gate.expected_lanes),
                "cancelled="+str(len(day_gate.cancelled_race_ids)))
            if not args.apply:
                conn.rollback()
                log("K_DETAIL_PREVIEW_PASS_NO_DB_WRITES_NO_ROUTE_CHANGES")
                return
            # Source and stage are modified atomically; neither old v2_results
            # nor the active VIEWs are ever modified.
            values = list(build_values(races))
            if len(values) != day_gate.expected_lanes:
                raise RuntimeError("HOLD_EXPECTED_LANE_COUNT_CHANGED")
            for table in (SOURCE, STAGE):
                insert_details(cur, values, table)
            verify_same_rows(cur, args.date, day_gate.expected_lanes)
        conn.commit()
    log("K_DETAIL_DUAL_TARGET_COMMIT", "date="+args.date,
        "rows_per_table="+str(day_gate.expected_lanes),
        "summary_results_unchanged=YES", "cutover=NO_GO", "BUY=OFF")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        if isinstance(ex, psycopg.Error):
            text = ex.sqlstate or "POSTGRES_ERROR"
        else:
            text = str(ex).splitlines()[0][:180]
        log("K_DETAIL_BACKFILL_HOLD", text,
            "NO_AUTOMATIC_RETRY", "NO_CUTOVER", "BUY=OFF")
        sys.exit(2)
