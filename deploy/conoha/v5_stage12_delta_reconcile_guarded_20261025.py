#!/usr/bin/env python3
"""Guarded V5 stage-only incremental reconciliation for 12 copied families.

No public writes, BUY, collector stop, live VIEW replacement or route cutover.
For each table, uses one REPEATABLE READ PostgreSQL transaction with bounded
primary-key windows and INSERT/UPDATE/DELETE + bidirectional row equality
checks. Every transaction either commits that table or rolls back the table.
This is as-of snapshot convergence, not ongoing CDC. Re-run when needed.

Run without --apply for catalog-only preview (no user table scans).
--apply requires V5_STAGE12_DELTA_APPROVED=YES. Only the single small
--table races pilot may run 08:00-22:59 JST; other tables, --remaining
(excludes races, sorts 11 sources smallest-first), and --all remain
03:00-05:44 JST. Stage-only; no production cutover.
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg
from psycopg import sql

TZ = ZoneInfo("Asia/Tokyo")
ROWS = (
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
ADVISORY_LOCK = 2026102503
COPY_MARKER = "BOAT_V5_STAGE_ONLY_SNAPSHOT_20261025"
PAGE = 4000


def now():
    return datetime.now(TZ)


def report(*args):
    print(now().isoformat(timespec="seconds"), *args, flush=True)


def one(cur, query, params=()):
    cur.execute(query, params)
    value = cur.fetchone()
    return value[0] if value else None


def ident(schema, table):
    return sql.Identifier(schema, table)


def col(alias, name):
    return sql.SQL("{}.{}").format(sql.Identifier(alias), sql.Identifier(name))


def pk_expr(alias, keys):
    return sql.SQL("(") + sql.SQL(",").join(col(alias, k) for k in keys) + sql.SQL(")")


def vals(keys):
    return sql.SQL("(") + sql.SQL(",").join(sql.Placeholder() for _ in keys) + sql.SQL(")")


def bounds(alias, keys, previous, last):
    expr = pk_expr(alias, keys)
    terms = []
    params = ()
    if previous is not None:
        terms.append(expr + sql.SQL(" > ") + vals(keys))
        params += tuple(previous)
    if last is not None:
        terms.append(expr + sql.SQL(" <= ") + vals(keys))
        params += tuple(last)
    return (sql.SQL(" AND ").join(terms) if terms else sql.SQL("true")), params


def data_columns(cur, fullname):
    cur.execute(
        "SELECT attname,atttypid::text,atttypmod,attnotnull,attcollation::text "
        "FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attnum>0 "
        "AND NOT attisdropped ORDER BY attnum",
        (fullname,))
    return tuple(cur.fetchall())


def primary_key(cur, fullname):
    cur.execute(
        "SELECT a.attname FROM pg_index i "
        "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) "
        "ON k.ord<=i.indnkeyatts "
        "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum "
        "WHERE i.indrelid=to_regclass(%s) AND i.indisprimary ORDER BY k.ord",
        (fullname,))
    return tuple(row[0] for row in cur.fetchall())


def validate(cur, source, stage, dest):
    if one(cur, "SELECT current_database()") != "railway":
        raise RuntimeError("HOLD_WRONG_DATABASE")
    if one(cur, "SELECT current_user") != "postgres":
        raise RuntimeError("HOLD_WRONG_ROLE")
    for relation, kind in ((source, "r"), (stage, "r"),
                           ("boat_data." + dest, "v")):
        got = one(cur, "SELECT relkind FROM pg_class "
                      "WHERE oid=to_regclass(%s)", (relation,))
        if got != kind:
            raise RuntimeError("HOLD_RELATION_CHANGED_" + relation)
    src_attrs = data_columns(cur, source)
    dst_attrs = data_columns(cur, stage)
    if not src_attrs or src_attrs != dst_attrs:
        raise RuntimeError("HOLD_SCHEMA_MISMATCH_" + dest)
    keys = primary_key(cur, source)
    if not keys or keys != primary_key(cur, stage) or len(keys) > 4:
        raise RuntimeError("HOLD_PRIMARY_KEY_MISMATCH_" + dest)
    fields = tuple(row[0] for row in src_attrs)
    rest = tuple(n for n in fields if n not in keys)
    if not rest:
        raise RuntimeError("HOLD_NO_UPDATE_COLUMNS_" + dest)
    proof = one(cur, "SELECT obj_description(to_regclass(%s), 'pg_class')",
                (stage,))
    if not isinstance(proof, str) or not proof.startswith(
            COPY_MARKER + " source=" + source + " "):
        raise RuntimeError("HOLD_COPY_MARKER_MISSING_" + dest)
    for name in (source, stage):
        if one(cur, "SELECT count(*) FROM pg_trigger "
               "WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal",
               (name,)):
            raise RuntimeError("HOLD_USER_TRIGGER_" + name)
    if one(cur, "SELECT count(*) FROM pg_constraint "
           "WHERE conrelid=to_regclass(%s) AND contype='f'",
           (stage,)):
        raise RuntimeError("HOLD_STAGE_FK_" + stage)
    return fields, keys, rest


def apply_page(cur, source, stage, fields, keys, rest, previous, last):
    src = ident("public", source.split(".", 1)[1])
    dst = ident("boat_data_stage", stage.split(".", 1)[1])
    cond_s, par_s = bounds("s", keys, previous, last)
    cond_d, par_d = bounds("d", keys, previous, last)
    join = sql.SQL(" AND ").join(
        col("d", k) + sql.SQL("=") + col("s", k) for k in keys)
    column_names = sql.SQL(",").join(map(sql.Identifier, fields))
    selected = sql.SQL(",").join(col("s", n) for n in fields)
    set_cols = sql.SQL(",").join(
        sql.SQL("{}={}").format(sql.Identifier(n), col("s", n))
        for n in rest)
    # JSON/JSONB columns must be comparable; PostgreSQL plain json has no
    # built-in row equality operator. Compare canonical to_jsonb records.
    # Only physically UPDATE changed rows (not 8.4m unchanged odds records).
    q_update = sql.SQL(
        "UPDATE {} AS d SET {} FROM {} AS s "
        "WHERE {} AND {} AND to_jsonb(d) IS DISTINCT FROM to_jsonb(s)"
    ).format(dst, set_cols, src, join, cond_s)
    cur.execute(q_update, par_s)
    n_update = cur.rowcount

    q_insert = sql.SQL(
        "INSERT INTO {} ({}) SELECT {} FROM {} AS s WHERE {} "
        "AND NOT EXISTS(SELECT 1 FROM {} AS d WHERE {}) "
        "ON CONFLICT ({}) DO NOTHING"
    ).format(dst, column_names, selected, src, cond_s, dst, join,
             sql.SQL(",").join(map(sql.Identifier, keys)))
    cur.execute(q_insert, par_s)
    n_insert = cur.rowcount

    # Stage-only DELETE must be scoped to this PK range, not whole table.
    q_delete = sql.SQL(
        "DELETE FROM {} AS d WHERE {} AND "
        "NOT EXISTS(SELECT 1 FROM {} AS s WHERE {})"
    ).format(dst, cond_d, src, join)
    cur.execute(q_delete, par_d)
    n_delete = cur.rowcount

    # Verify EVERY source row in this key range, and extra stage-only keys.
    q_missing = sql.SQL(
        "SELECT EXISTS(SELECT 1 FROM {} AS s "
        "LEFT JOIN {} AS d ON {} WHERE {} "
        "AND ({} IS NULL OR to_jsonb(s) IS DISTINCT FROM to_jsonb(d)) LIMIT 1)"
    ).format(src, dst, join, cond_s, col("d", keys[0]))
    cur.execute(q_missing, par_s)
    has_missing_or_changed = cur.fetchone()[0]

    q_extra = sql.SQL(
        "SELECT EXISTS(SELECT 1 FROM {} AS d "
        "LEFT JOIN {} AS s ON {} WHERE {} "
        "AND {} IS NULL LIMIT 1)"
    ).format(dst, src, join, cond_d, col("s", keys[0]))
    cur.execute(q_extra, par_d)
    has_extra = cur.fetchone()[0]
    if has_missing_or_changed or has_extra:
        raise RuntimeError("HOLD_RANGE_PARITY_ROLLBACK_" + stage)
    return n_insert, n_update, n_delete


def sync_table(conn, source_name, dest, daylight_pilot=False):
    source = "public." + source_name
    stage = "boat_data_stage." + dest
    report("BEGIN_DELTA", source, "=>", stage)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cur.execute("SET LOCAL lock_timeout='1200ms'")
            cur.execute("SET LOCAL statement_timeout='120000ms'")
            cur.execute("SET LOCAL work_mem='8MB'")
            if not one(cur, "SELECT pg_try_advisory_xact_lock(%s)",
                       (ADVISORY_LOCK,)):
                raise RuntimeError("HOLD_DELTA_LOCK_BUSY")
            fields, keys, rest = validate(cur, source, stage, dest)
            source_count = one(cur, sql.SQL("SELECT count(*) FROM {}").format(
                ident("public", source_name)))
            if source_count == 0:
                raise RuntimeError("HOLD_EMPTY_SOURCE_NO_MASS_DELETE")
            if daylight_pilot and (dest != "races" or source_count > 100000):
                raise RuntimeError("HOLD_DAYLIGHT_PILOT_NOT_SMALL_RACES")
            past = None
            totals = [0, 0, 0]
            windows = 0
            started = time.monotonic()
            while True:
                n = now()
                daytime_now = daylight_pilot and (8 <= n.hour < 23)
                nighttime_now = (3 <= n.hour < 6 and
                                 not (n.hour == 5 and n.minute >= 45))
                if (not (daytime_now or nighttime_now)
                    or time.monotonic() - started > (120 if daylight_pilot else 1100)):
                    raise RuntimeError("HOLD_TIME_BUDGET_TRANSACTION_ROLLBACK")
                cond, pars = bounds("s", keys, past, None)
                q = sql.SQL("SELECT {} FROM {} AS s WHERE {} "
                            "ORDER BY {} LIMIT {}").format(
                    sql.SQL(",").join(col("s", k) for k in keys),
                    ident("public", source_name), cond,
                    sql.SQL(",").join(col("s", k) for k in keys),
                    sql.Placeholder())
                cur.execute(q, pars + (PAGE,))
                fetched = cur.fetchall()
                if not fetched:
                    break
                last = tuple(fetched[-1])
                changes = apply_page(cur, source, stage, fields, keys,
                                     rest, past, last)
                totals = [a+b for a,b in zip(totals, changes)]
                windows += 1
                past = last
                if windows % 100 == 0:
                    report("DELTA_PROGRESS", dest, "pages=" + str(windows),
                           "changed=" + str(totals))
            # Delete extra stage rows above the source's last PK.
            cond, pars = bounds("d", keys, past, None)
            join = sql.SQL(" AND ").join(
                col("d", k) + sql.SQL("=") + col("s", k) for k in keys)
            q = sql.SQL(
                "DELETE FROM {} AS d WHERE {} AND NOT EXISTS "
                "(SELECT 1 FROM {} AS s WHERE {})"
            ).format(ident("boat_data_stage", dest), cond,
                     ident("public", source_name), join)
            cur.execute(q, pars)
            totals[2] += cur.rowcount
            # Catch any leftover stage keys above final source key.
            q = sql.SQL("SELECT EXISTS(SELECT 1 FROM {} AS d WHERE {} LIMIT 1)"
                        ).format(ident("boat_data_stage", dest), cond)
            if one(cur, q, pars):
                raise RuntimeError("HOLD_STAGE_TAIL_REMAINS")
            stage_count = one(cur, sql.SQL("SELECT count(*) FROM {}").format(
                ident("boat_data_stage", dest)))
            if stage_count != source_count:
                raise RuntimeError("HOLD_FINAL_COUNT_MISMATCH")
            report("DELTA_VERIFIED", dest, "source_rows=" + str(source_count),
                   "stage_rows=" + str(stage_count),
                   "insert_update_delete=" + str(totals),
                   "bounded_windows=" + str(windows))
    report("DELTA_TABLE_COMMITTED", dest, "legacy_untouched=YES",
           "live_view_untouched=YES", "CDC=NO", "cutover=NO_GO", "BUY=OFF")


def preview(conn, selected):
    with conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SET LOCAL statement_timeout='10000ms'")
        for source, dest in selected:
            cols, keys, rest = validate(
                cur, "public." + source, "boat_data_stage." + dest, dest)
            size = one(cur,
                "SELECT pg_total_relation_size(to_regclass(%s))",
                ("public." + source,))
            report("DELTA_PREVIEW_METADATA_PASS", dest,
                   "pk=" + ",".join(keys),
                   "columns=" + str(len(cols)),
                   "source_disk_MB=" + str(int(size) // 1048576),
                   "live_route_untouched=YES")
        conn.rollback()
    report("PREVIEW_COMPLETE", "families=" + str(len(selected)),
           "current_delta_counts=NOT_MEASURED",
           "no_table_scan=YES", "NO_WRITES", "NO_CUTOVER")


def main():
    parser = argparse.ArgumentParser()
    mx = parser.add_mutually_exclusive_group(required=True)
    mx.add_argument("--table", choices=[d for _, d in ROWS])
    mx.add_argument("--all", action="store_true")
    mx.add_argument("--remaining", action="store_true",
                    help="Exclude piloted races; stage-only eleven tables")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_POSTGRES_REQUIRED")
    selected = (
        ROWS if args.all else
        tuple(row for row in ROWS if row[1] != "races") if args.remaining else
        tuple(row for row in ROWS if row[1] == args.table)
    )
    daylight_pilot = bool(
        args.apply and args.table == "races" and 8 <= now().hour < 23)
    if args.apply:
        if os.environ.get("V5_STAGE12_DELTA_APPROVED") != "YES":
            raise RuntimeError("HOLD_EXPLICIT_DELTA_STAGE_APPROVAL_REQUIRED")
        if not daylight_pilot and (
            not (3 <= now().hour < 6) or
            (now().hour == 5 and now().minute >= 45)
        ):
            raise RuntimeError("HOLD_STAGE_DELTA_ONLY_NIGHT_OR_RACES_DAYLIGHT")
    with psycopg.connect(os.environ["DATABASE_URL"],
                         autocommit=True, connect_timeout=8) as conn:
        if not args.apply:
            preview(conn, selected)
            return
        # Stage-only copy was intentionally independent of legacy collectors.
        # Fail closed if source DB disk/WAL headroom is low.
        with conn.cursor() as cur:
            datadir = one(cur, "SHOW data_directory")
            free = shutil.disk_usage(datadir).free
            if free < 16 * 1024 ** 3:
                raise RuntimeError("HOLD_LOW_DISK_OR_WAL_HEADROOM")
        if args.remaining:
            with conn.cursor() as cur:
                selected = tuple(sorted(selected, key=lambda pair: one(
                    cur, "SELECT pg_total_relation_size(to_regclass(%s))",
                    ("public." + pair[0],))))
        report("APPLY_SCOPE", "stage_only", "tables=" + str(len(selected)),
               "free_gib=%.2f" % (free / (1024**3)),
               "order=" + ",".join(dest for _, dest in selected))
        for src, dest in selected:
            sync_table(conn, src, dest, daylight_pilot=daylight_pilot)
        report("STAGE12_DELTA_SNAPSHOT_PASS", "families=" + str(len(selected)),
               "as_of_per_table_not_CDC=YES", "cutover=NO_GO", "BUY=OFF")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        safe = (exc.sqlstate or "PG_ERROR") if isinstance(exc, psycopg.Error) \
            else str(exc).split("\n")[0][:160]
        report("STAGE12_DELTA_HOLD", safe, "LEGACY_COLLECTORS_UNTOUCHED",
               "current_table_rolled_back=YES", "NO_CUTOVER")
        sys.exit(2)
