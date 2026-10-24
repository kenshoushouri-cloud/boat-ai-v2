#!/usr/bin/env python3
"""One-table VENUES stage-only delta pilot: read-only preview, or guarded APPLY.

This program never writes public.v2_venues, boat_data live VIEW, BUY, or timers.
It reconciles INSERT/UPDATE/DELETE in boat_data_stage.venues against a single
REPEATABLE READ source snapshot. It is NOT continuous CDC and is NOT cutover.
Apply requires explicit env flag + --apply + bounded window + source/stage proof.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql

SOURCE = "public.v2_venues"
STAGE = "boat_data_stage.venues"
VIEW = "boat_data.venues"
TZ = ZoneInfo("Asia/Tokyo")
LOCK = 2026102502

# The approved physical source/stage have identical columns (10/25 catalog).
# Record-key, not a synthetic incremental timestamp.
COLUMNS = ("venue_code", "venue_name", "created_at", "updated_at",
           "venue_id", "is_active")
PK = ("venue_code",)


def now():
    return datetime.now(TZ)


def show(*msg):
    print(now().isoformat(timespec="seconds"), *msg, flush=True)


def scalar(cur, statement, values=()):
    cur.execute(statement, values)
    row = cur.fetchone()
    return row[0] if row else None


def columns(cur, qualified):
    cur.execute(
        "SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(%s) "
        "AND attnum>0 AND NOT attisdropped ORDER BY attnum", (qualified,))
    return tuple(row[0] for row in cur.fetchall())


def signature(cur, qualified):
    cur.execute(
        "SELECT attname, atttypid::text, atttypmod, attnotnull, "
        "attcollation::text, attidentity, attgenerated "
        "FROM pg_attribute WHERE attrelid=to_regclass(%s) "
        "AND attnum>0 AND NOT attisdropped ORDER BY attnum", (qualified,))
    return tuple(cur.fetchall())


def pk(cur, qualified):
    cur.execute(
        "SELECT a.attname FROM pg_index i "
        "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum, ord) "
        "ON k.ord<=i.indnkeyatts "
        "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum "
        "WHERE i.indrelid=to_regclass(%s) AND i.indisprimary ORDER BY k.ord",
        (qualified,))
    return tuple(row[0] for row in cur.fetchall())


def validate(cur):
    if scalar(cur, "SELECT current_database()") != "railway" or (
        scalar(cur, "SELECT current_user") != "postgres"
    ):
        raise RuntimeError("HOLD_WRONG_DB_OR_ROLE")
    for relation, kind in ((SOURCE, "r"), (STAGE, "r"), (VIEW, "v")):
        found = scalar(cur,
            "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
            (relation,))
        if found != kind:
            raise RuntimeError("HOLD_RELATION_KIND_" + relation)
    if signature(cur, SOURCE) != signature(cur, STAGE):
        raise RuntimeError("HOLD_SCHEMA_SIGNATURE_MISMATCH")
    for relation in (SOURCE, STAGE):
        if columns(cur, relation) != COLUMNS:
            raise RuntimeError("HOLD_COLUMN_SHAPE_" + relation)
        if pk(cur, relation) != PK:
            raise RuntimeError("HOLD_PK_SHAPE_" + relation)
    for relation in (SOURCE, STAGE):
        if scalar(cur,
            "SELECT count(*) FROM pg_trigger WHERE tgrelid=to_regclass(%s) "
            "AND NOT tgisinternal", (relation,)):
            raise RuntimeError("HOLD_TRIGGER_" + relation)
    if scalar(cur,
        "SELECT count(*) FROM pg_constraint "
        "WHERE conrelid=to_regclass(%s) AND contype='f'", (STAGE,)):
        raise RuntimeError("HOLD_STAGE_FOREIGN_KEY")
    if scalar(cur, "SELECT count(*) FROM " + SOURCE) != 24:
        raise RuntimeError("HOLD_SOURCE_VENUES_NOT_24")
    if scalar(cur, "SELECT count(*) FROM " + STAGE) != 24:
        raise RuntimeError("HOLD_STAGE_VENUES_NOT_24")
    show("VENUES_SOURCE_AND_STAGE_VERIFIED", "rows=24")


def preview_delta(cur):
    cur.execute(
        "SELECT "
        "count(*) FILTER (WHERE s.venue_code IS NOT NULL AND t.venue_code IS NULL), "
        "count(*) FILTER (WHERE s.venue_code IS NULL AND t.venue_code IS NOT NULL), "
        "count(*) FILTER (WHERE s.venue_code IS NOT NULL AND t.venue_code IS NOT NULL "
        "AND to_jsonb(s) IS DISTINCT FROM to_jsonb(t)), "
        "count(*) FILTER (WHERE s.venue_code IS NOT NULL AND t.venue_code IS NOT NULL "
        "AND s.updated_at IS DISTINCT FROM t.updated_at "
        "AND ROW(s.venue_name,s.created_at,s.venue_id,s.is_active) "
        "IS NOT DISTINCT FROM "
        "ROW(t.venue_name,t.created_at,t.venue_id,t.is_active)) "
        "FROM public.v2_venues s FULL OUTER JOIN boat_data_stage.venues t "
        "USING (venue_code)"
    )
    inserted, deleted, updated, only_updated_at = cur.fetchone()
    show("VENUES_STAGE_DELTA_PREVIEW_READONLY",
         "insert=" + str(inserted), "update=" + str(updated),
         "delete=" + str(deleted),
         "updated_at_only=" + str(only_updated_at),
         "other_column_changes=" + str(updated - only_updated_at),
         "total_delta=" + str(inserted + updated + deleted),
         "snapshot_consistent=YES", "NO_DB_WRITES", "NO_CUTOVER")
    return inserted, updated, deleted


def sync(cur):
    # One transaction-level snapshot ensures all three operations see the same
    # source even if its legacy writer continues running.
    col_list = sql.SQL(",").join(map(sql.Identifier, COLUMNS))
    updates = sql.SQL(",").join(
        sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
        for c in COLUMNS if c not in PK
    )
    update_columns = tuple(c for c in COLUMNS if c not in PK)
    compare_dst = sql.SQL(",").join(
        sql.SQL("dst.{}").format(sql.Identifier(c)) for c in update_columns)
    compare_new = sql.SQL(",").join(
        sql.SQL("EXCLUDED.{}").format(sql.Identifier(c)) for c in update_columns)
    # SELECT WHERE true removes the PostgreSQL parser ambiguity between
    # JOIN ... ON and INSERT ... ON CONFLICT.
    upsert = sql.SQL(
        "INSERT INTO {} AS dst ({}) SELECT {} FROM {} WHERE true "
        "ON CONFLICT ({}) DO UPDATE SET {} "
        "WHERE ROW({}) IS DISTINCT FROM ROW({})"
    ).format(
        sql.Identifier("boat_data_stage", "venues"), col_list, col_list,
        sql.Identifier("public", "v2_venues"), sql.Identifier("venue_code"),
        updates, compare_dst, compare_new
    )
    cur.execute(upsert)
    inserted_or_updated = cur.rowcount

    cur.execute(
        "DELETE FROM boat_data_stage.venues s WHERE NOT EXISTS "
        "(SELECT 1 FROM public.v2_venues o WHERE o.venue_code=s.venue_code)"
    )
    deleted = cur.rowcount

    # Bidirectional full-row equality, checked in the SAME snapshot/transaction.
    # jsonb normalizes JSON column types if any are introduced in future.
    cur.execute(
        "SELECT "
        "NOT EXISTS (SELECT to_jsonb(x) FROM public.v2_venues x "
        "EXCEPT ALL SELECT to_jsonb(y) FROM boat_data_stage.venues y), "
        "NOT EXISTS (SELECT to_jsonb(y) FROM boat_data_stage.venues y "
        "EXCEPT ALL SELECT to_jsonb(x) FROM public.v2_venues x)"
    )
    forward, reverse = cur.fetchone()
    if not (forward and reverse):
        raise RuntimeError("HOLD_VENUES_BIDIRECTIONAL_MISMATCH_ROLLBACK")
    show("VENUES_STAGE_DELTA_TRANSACTION_PASS",
         "upserted=" + str(inserted_or_updated),
         "deleted=" + str(deleted),
         "bidirectional_equal_in_transaction=YES",
         "legacy_source_untouched=YES", "live_view_untouched=YES",
         "continuous_cdc=NO", "cutover=NO_GO", "BUY=OFF")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--apply", action="store_true")
    options = args.parse_args()
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_PG_URL_REQUIRED")
    if options.apply:
        if os.environ.get("V5_VENUES_STAGE_DELTA_APPROVED") != "YES":
            raise RuntimeError("HOLD_EXPLICIT_STAGING_APPROVAL_REQUIRED")
        n = now()
        # The venues pilot updates only an isolated 24-row staging table.
        # It may run in daylight; legacy collectors and live views are untouched.
        if not ((3 <= n.hour < 6) or (8 <= n.hour < 23)):
            raise RuntimeError("HOLD_APPLY_OUTSIDE_SAFE_VENUES_WINDOWS")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8,
                         autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cur.execute("SET LOCAL statement_timeout='12000ms'")
            cur.execute("SET LOCAL lock_timeout='1500ms'")
            cur.execute("SET LOCAL work_mem='8MB'")
            if not scalar(cur, "SELECT pg_try_advisory_xact_lock(%s)", (LOCK,)):
                raise RuntimeError("HOLD_STAGE_RECONCILE_LOCK_BUSY")
            validate(cur)
            if options.apply:
                sync(cur)
            else:
                preview_delta(cur)
                show("VENUES_STAGE_DELTA_PREVIEW_PASS_NO_WRITES",
                     "on_apply=source_to_stage_insert_update_delete",
                     "cutover=NO_GO", "BUY=OFF")
        if options.apply:
            conn.commit()
            show("VENUES_STAGE_ONLY_DELTA_COMMITTED_NOT_CDC_NOT_LIVE")
        else:
            conn.rollback()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        name = str(exc).split("\n", 1)[0]
        if isinstance(exc, psycopg.Error):
            name = exc.sqlstate or "PG_ERROR"
        show("VENUES_STAGE_DELTA_HOLD", name[:150],
             "SOURCE_WRITER_UNTOUCHED", "NO_CUTOVER")
        sys.exit(2)
