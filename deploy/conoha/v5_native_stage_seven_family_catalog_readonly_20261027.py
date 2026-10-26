#!/usr/bin/env python3
"""Audit V5 six realtime snapshot stages + results stage without modifying DB.

Compares real physical PostgreSQL table columns, NOT NULL / default / identity
and unique indexes against exactly what the installed native V5 writers provide.
No website requests, imports of legacy writers, writes, systemd or BUY.
Never declares end-to-end collection success from schema alone.
"""
from __future__ import annotations

import os
import sys
from psycopg import connect

from v5.native_official_realtime_stage_pg import COLUMN_SETS, SNAPSHOT_KEYS
from v5.native_results_catchup_stage import FIELDS as RESULT_FIELDS

FAMILIES = {
    **{
        k: (tuple(fields), tuple(SNAPSHOT_KEYS[k]))
        for k, fields in COLUMN_SETS.items()
    },
    "results": (tuple(RESULT_FIELDS), ("race_id",)),
}

def run() -> int:
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_ONLY_LOCAL_CONOHA_DB")
    print("V5_NATIVE_STAGE_SEVEN_FAMILY_SCHEMA_BEGIN_READ_ONLY", flush=True)
    errors = []
    with connect(os.environ["DATABASE_URL"], connect_timeout=5,
                 autocommit=True) as db:
        with db.transaction():
            with db.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='7000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                for family, (provided, conflict_key) in FAMILIES.items():
                    fullname = "boat_data_stage." + family
                    cur.execute("""SELECT relkind FROM pg_class
                                   WHERE oid=to_regclass(%s)""", (fullname,))
                    relation = cur.fetchone()
                    if not relation or relation[0] not in ("r", "p"):
                        errors.append(f"HOLD_NOT_PHYSICAL_{family}")
                        print(f"TABLE|{family}|HOLD_NOT_PHYSICAL", flush=True)
                        continue
                    cur.execute("""SELECT attname,
                                          format_type(atttypid,atttypmod),
                                          attnotnull, atthasdef,
                                          attidentity, attgenerated
                        FROM pg_attribute WHERE attrelid=to_regclass(%s)
                          AND attnum>0 AND NOT attisdropped
                        ORDER BY attnum""", (fullname,))
                    schema = cur.fetchall()
                    existing = {r[0] for r in schema}
                    unmapped_required = [
                        name for name, _, required, hasdefault, identity, generated in schema
                        if required and not (hasdefault or identity or generated)
                           and name not in provided
                    ]
                    missing_mapped = sorted(set(provided) - existing)
                    # An explicit value can still be NULL at runtime; this
                    # report checks only whether a writer *maps* the column.
                    required_mapped = [
                        name for name, _, required, hasdefault, identity, generated in schema
                        if required and not (hasdefault or identity or generated)
                           and name in provided
                    ]
                    cur.execute("""SELECT array_agg(a.attname ORDER BY x.ord)
                        FROM pg_index i
                        JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(num,ord)
                          ON x.ord<=i.indnkeyatts
                        JOIN pg_attribute a ON a.attrelid=i.indrelid
                                           AND a.attnum=x.num
                        WHERE i.indrelid=to_regclass(%s)
                          AND i.indisunique AND i.indisvalid
                          AND i.indpred IS NULL AND i.indexprs IS NULL
                        GROUP BY i.indexrelid""", (fullname,))
                    indexes = {tuple(a[0]) for a in cur.fetchall()}
                    key_ok = conflict_key in indexes
                    print("TABLE|" + family
                          + "|required_mapped=" + ",".join(required_mapped)
                          + "|unmapped_required=" + (",".join(unmapped_required) or "-")
                          + "|absent_writer_columns=" + (",".join(missing_mapped) or "-")
                          + "|unique_key=" + ",".join(conflict_key)
                          + "|unique_key_valid=" + str(key_ok), flush=True)
                    if "id" in existing and "id" in unmapped_required:
                        print(f"WARNING|{family}|REQUIRES_SAFE_NONCOLLIDING_ID_STRATEGY",
                              flush=True)
                    if "created_at" in unmapped_required:
                        print(f"WARNING|{family}|REQUIRES_EXPLICIT_CREATED_AT",
                              flush=True)
                    if unmapped_required or missing_mapped or not key_ok:
                        errors.append(family)
            db.rollback()
    if errors:
        print("V5_NATIVE_STAGE_SEVEN_FAMILY_SCHEMA_HOLD="
              + ",".join(errors) + "|NO_WRITES", flush=True)
        return 3
    print("V5_NATIVE_STAGE_SEVEN_FAMILY_SCHEMA_COLUMN_KEY_PASS_ONLY_"
          "NOT_RUNTIME_WRITER_PROOF_NO_WRITES", flush=True)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print("V5_NATIVE_STAGE_SCHEMA_AUDIT_HOLD " + type(exc).__name__ +
              ":" + str(exc).splitlines()[0][:160], flush=True)
        raise SystemExit(2)
