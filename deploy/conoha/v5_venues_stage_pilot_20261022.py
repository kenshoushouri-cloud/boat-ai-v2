"""Guarded, tiny V5 venues staging pilot (no route/service changes).

PREVIEW is read-only by default. APPLY requires explicit two-factor opt-in:
--apply and CONFIRM_V5_VENUES_PILOT=YES. No source writes or deletes.
A successful staged table is NOT cutover-ready or automatically in sync.
"""
from __future__ import annotations

import argparse
import os
import sys
import psycopg

SRC = "public.v2_venues"
DST = "v5_data.venues"
CAP = 1000


def one(cur, sql, params=()):
    cur.execute(sql, params)
    result = cur.fetchone()
    return result[0] if result else None


def audit(cur):
    if one(cur, "SELECT to_regclass(%s)", (SRC,)) is None:
        raise RuntimeError("STOP: source venues relation missing")
    if one(cur, "SELECT to_regclass(%s)", (DST,)) is not None:
        raise RuntimeError("STOP: destination exists; do not overwrite")
    if one(cur, "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (SRC,)) != "r":
        raise RuntimeError("STOP: venues source is not a plain physical table")
    if one(cur, "SELECT COUNT(*) FROM pg_namespace WHERE nspname='v5_data'") != 1:
        raise RuntimeError("STOP: v5_data schema missing")
    total = one(cur, "SELECT COUNT(*) FROM public.v2_venues")
    print(f"VENUES_SOURCE_ROWS={total}", flush=True)
    if not (0 < total <= CAP):
        raise RuntimeError("STOP: source row count outside small-pilot bounds")
    fk_out = one(cur, "SELECT COUNT(*) FROM pg_constraint WHERE conrelid=to_regclass(%s) AND contype='f'", (SRC,))
    fk_in = one(cur, "SELECT COUNT(*) FROM pg_constraint WHERE confrelid=to_regclass(%s) AND contype='f'", (SRC,))
    triggers = one(cur, "SELECT COUNT(*) FROM pg_trigger WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal", (SRC,))
    print(f"VENUES_FK_OUT={fk_out} FK_IN={fk_in} USER_TRIGGERS={triggers}", flush=True)
    unusual = one(cur, """
        SELECT COUNT(*) FROM pg_attribute a
        WHERE a.attrelid=to_regclass(%s) AND a.attnum > 0 AND NOT a.attisdropped
          AND (a.attgenerated <> '' OR a.attidentity <> '')
        """, (SRC,))
    serial_defaults = one(cur, """
        SELECT COUNT(*) FROM pg_attrdef d WHERE d.adrelid=to_regclass(%s)
        AND pg_get_expr(d.adbin,d.adrelid) LIKE 'nextval(%%'
        """, (SRC,))
    print(f"VENUES_IDENTITY_OR_GENERATED={unusual} SERIAL_DEFAULTS={serial_defaults}", flush=True)
    if unusual or serial_defaults:
        raise RuntimeError("STOP: identity/generated/serial default needs dedicated clone plan")
    if fk_out or fk_in or triggers:
        raise RuntimeError("STOP: FK/trigger dependencies require a dedicated venues staging plan")
    col_count = one(cur, """
        SELECT COUNT(*) FROM pg_attribute WHERE attrelid=to_regclass(%s)
        AND attnum>0 AND NOT attisdropped
        """, (SRC,))
    source_indexes = one(cur, "SELECT COUNT(*) FROM pg_index WHERE indrelid=to_regclass(%s)", (SRC,))
    print(f"VENUES_COLUMNS={col_count} INDEXES={source_indexes}", flush=True)
    return total, col_count, source_indexes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and os.environ.get("CONFIRM_V5_VENUES_PILOT") != "YES":
        parser.error("--apply requires CONFIRM_V5_VENUES_PILOT=YES")
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL is required; ConoHa local database only")
    print("V5_VENUES_STAGE_MODE=" + ("APPLY" if args.apply else "PREVIEW"), flush=True)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            if not args.apply:
                cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '10000ms'")
            cur.execute("SET LOCAL lock_timeout = '1500ms'")
            total, cols, indexes = audit(cur)
            if not args.apply:
                print("V5_VENUES_STAGE_PREVIEW_PASS_NO_DB_WRITES=1", flush=True)
                return
            # Short, atomic small-table operation. Do not modify legacy.
            cur.execute("CREATE TABLE v5_data.venues (LIKE public.v2_venues INCLUDING ALL)")
            cur.execute("INSERT INTO v5_data.venues SELECT * FROM public.v2_venues")
            if cur.rowcount != total:
                raise RuntimeError("STOP: copied row count differs; rolling back")
            target_total = one(cur, "SELECT COUNT(*) FROM v5_data.venues")
            target_cols = one(cur, """
                SELECT COUNT(*) FROM pg_attribute WHERE attrelid=to_regclass(%s)
                AND attnum>0 AND NOT attisdropped
                """, (DST,))
            target_indexes = one(cur, "SELECT COUNT(*) FROM pg_index WHERE indrelid=to_regclass(%s)", (DST,))
            differences = one(cur, """
                SELECT COUNT(*) FROM (
                   (SELECT * FROM public.v2_venues EXCEPT ALL SELECT * FROM v5_data.venues)
                   UNION ALL
                   (SELECT * FROM v5_data.venues EXCEPT ALL SELECT * FROM public.v2_venues)
                ) d
                """)
            if (target_total, target_cols, target_indexes, differences) != (total, cols, indexes, 0):
                raise RuntimeError("STOP: copy integrity mismatch; rolling back")
            print(f"V5_VENUES_STAGED_VERIFIED={target_total} DIFFERENCES={differences}", flush=True)
        # Connection context commits on clean exit.
    print("V5_VENUES_STAGING_PILOT_COMPLETE_LEGACY_UNCHANGED", flush=True)
    print("NOTE: no writer/read routing, grants or trigger/FK equivalence certified; do not enable V5 profile")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"V5_VENUES_STAGE_STOP={type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
