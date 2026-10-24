#!/usr/bin/env python3
"""V5 staged, keyset-bounded physical COPY executor; DEFAULT PREVIEW READ ONLY.

Does not create stages, alter sources/views, change writer routes or automate
night cutovers. --copy needs separate explicit authorization, audited stage
schema, proof of source restoration, and a scoped stage-copy gate.
Batch-local repeatable read is NOT CDC. A final quiesced full-key
INSERT/UPDATE/DELETE reconciliation is always required. No BUY code here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from boat_shared_storage_contract import RELATIONS
from deploy.conoha.boat_shared_staging_delta_plan_offline import (
    blockers,
)
from v5.offline_stage_batch_plan import TARGETS
from v5.offline_stage_chunk_copy_sql import StageShape, make_key_select, make_window

ALLOWLIST = {r.legacy: r.canonical for r in RELATIONS}

COPY_GATES = (
    'independent_offsite_backup_restore_test_proven',
    'specific_source_and_stage_copy_scope_approved',
    'stage_pk_schema_defaults_sequences_verified',
    'disk_free_wal_and_statement_budget_verified',
    'online_collection_and_final_consistent_delta_strategy_approved',
    'documented_abort_and_stage_recovery_tested',
)


def _info(cur, qualified: str) -> dict | None:
    cur.execute(
        """SELECT c.oid::int, c.relkind::text,
                  n.nspname, c.relname
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE c.oid=to_regclass(%s)""", (qualified,),
    )
    item = cur.fetchone()
    if item is None:
        return None
    oid, kind, schema, name = item
    cur.execute(
        """SELECT a.attname, a.atttypid::int, a.atttypmod,
                  a.attcollation::int, a.attnotnull, a.attidentity,
                  a.attgenerated,
                  COALESCE(pg_get_expr(d.adbin,d.adrelid),'')
           FROM pg_attribute a LEFT JOIN pg_attrdef d
             ON d.adrelid=a.attrelid AND d.adnum=a.attnum
           WHERE a.attrelid=%s::oid AND a.attnum>0 AND NOT a.attisdropped
           ORDER BY a.attnum""", (oid,),
    )
    cols = cur.fetchall()
    cur.execute(
        """SELECT a.attname
           FROM pg_index i
           JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum,ord)
             ON TRUE
           JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
           WHERE i.indrelid=%s::oid AND i.indisprimary
           ORDER BY k.ord""", (oid,),
    )
    pk = tuple(row[0] for row in cur.fetchall())
    cur.execute(
        """SELECT (SELECT count(*) FROM pg_trigger t
                      WHERE t.tgrelid=%s::oid AND NOT t.tgisinternal),
                  (SELECT count(*) FROM pg_constraint f
                      WHERE f.conrelid=%s::oid AND f.contype='f')""",
        (oid,oid),
    )
    triggers, foreign_keys = cur.fetchone()
    return {
        "oid": oid, "kind": kind, "schema": schema, "name": name,
        "cols": cols, "pk": pk, "user_triggers": triggers,
        "foreign_keys": foreign_keys,
    }


def assess(source: str, old: dict | None, staged: dict | None) -> tuple[StageShape | None, list[str]]:
    if source not in ALLOWLIST or source not in TARGETS:
        raise ValueError("STOP: unknown V5 source")
    target, wave = TARGETS[source]
    if wave == 0:
        return None, ["existing_venues_stage_preserve_only"]
    issues = []
    if old is None or old["kind"] != "r":
        issues.append("source_not_physical")
    if staged is None or staged["kind"] != "r":
        issues.append("stage_missing_or_not_physical")
    if issues:
        return None, issues
    src_cols, dst_cols = old["cols"], staged["cols"]
    source_shape = [(c[0],c[1],c[2],c[3],c[4]) for c in src_cols]
    stage_shape = [(c[0],c[1],c[2],c[3],c[4]) for c in dst_cols]
    same_schema = source_shape == stage_shape and bool(src_cols)
    same_pk = bool(old["pk"]) and old["pk"] == staged["pk"] and len(old["pk"]) <= 4
    # Stage must NEVER share nextval defaults or invoke triggers/FKs.
    no_shared_sequence = not any(
        c[5] or c[6] or "nextval(" in c[7].lower() for c in dst_cols
    )
    if any(c[6] for c in src_cols):
        issues.append("source_generated_column_requires_dedicated_copy")
    if not same_schema:
        issues.append("source_stage_column_type_nullability_mismatch")
    if not same_pk:
        issues.append("source_stage_primary_key_mismatch")
    if not no_shared_sequence:
        issues.append("unsafe_stage_identity_generated_or_serial")
    if staged["user_triggers"] or staged["foreign_keys"]:
        issues.append("stage_side_effect_trigger_or_fk")
    if any(not next((c[4] for c in src_cols if c[0] == p),False) for p in old["pk"]):
        issues.append("source_primary_key_nullable")
    shape = StageShape(
        source=source, staged=target,
        columns=tuple(c[0] for c in src_cols),
        pk=old["pk"],
        stage_is_physical=staged["kind"] == "r",
        schema_same=same_schema,
        primary_key_same=same_pk,
        stage_not_live_writer=staged["schema"] == "boat_data_stage"
            and staged["oid"] != old["oid"]
            and target != ALLOWLIST[source],
        no_shared_serial_defaults=no_shared_sequence,
    )
    return shape, issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--source", choices=sorted(TARGETS))
    selector.add_argument("--all", action="store_true", help="preview all 12 not-yet-copied sources")
    parser.add_argument("--copy", action="store_true",
                        help="only for separately authorized stage COPY, never cutover")
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--max-batches", type=int, default=20)
    parser.add_argument("--approval-file", help="read-only file with independent stage gates")
    args = parser.parse_args(argv)
    if not 1 <= args.batch <= 500 or not 1 <= args.max_batches <= 100:
        raise SystemExit("STOP: batch 1-500 and max-batches 1-100 only")
    if args.all and args.copy:
        raise SystemExit("STOP: bulk --all only supports read-only preview")
    source = args.source
    if source is not None and TARGETS[source][1] == 0:
        raise SystemExit("STOP: existing venues stage is excluded from all copies")

    # No DATABASE_URL needed on ConoHa: run via PostgreSQL unix peer identity.
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("STOP: psycopg not installed in runner environment") from exc

    with psycopg.connect("dbname=railway", autocommit=True,
                         options="-c application_name=v5_stage_preview_or_copy") as conn:
        if args.all:
            result = []
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SET LOCAL statement_timeout='15s'")
                conn.execute("SET LOCAL lock_timeout='700ms'")
                with conn.cursor() as cur:
                    for src,(dest,wave) in TARGETS.items():
                        if wave == 0:
                            continue
                        old = _info(cur,src)
                        staged = _info(cur,dest)
                        _shape, issues = assess(src,old,staged)
                        result.append({
                            "source":src, "stage":dest,
                            "stage_exists":staged is not None,
                            "source_pk":list(old["pk"]) if old else [],
                            "stage_pk":list(staged["pk"]) if staged else [],
                            "issues":issues,
                        })
            print("SOURCE | STAGE | PHYSICAL_EXISTS | PRIMARY_KEY | BLOCKERS")
            for item in result:
                print(" | ".join((
                    item["source"], item["stage"],
                    "YES" if item["stage_exists"] else "NO",
                    ",".join(item["source_pk"]) or "NONE",
                    ",".join(item["issues"]) or "NONE",
                )))
            print(f"STAGE_CANDIDATES={len(result)} COPY_PERFORMED=NO CUTOVER=NO_GO")
            print("V5_STAGE_ALL_12_PREVIEW_READ_ONLY_FINISHED")
            return 0
        destination, wave = TARGETS[source]
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout='6s'")
            conn.execute("SET LOCAL lock_timeout='700ms'")
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                if cur.fetchone()[0] != "railway":
                    raise ValueError("STOP: wrong database")
                old = _info(cur, source)
                staged = _info(cur, destination)
                shape, problems = assess(source, old, staged)
        report = {
            "mode": "COPY_REQUESTED" if args.copy else "READ_ONLY_PREVIEW",
            "source": source, "stage": destination,
            "stage_exists": staged is not None,
            "source_pk": list(old["pk"]) if old else [],
            "stage_pk": list(staged["pk"]) if staged else [],
            "issues": problems,
            "cutover": "NO_GO",
            "actual_collection": "UNCHANGED",
        }
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if not args.copy:
            print("V5_STAGE_PREVIEW_READ_ONLY_NO_COPY")
            return 0
        if shape is None or problems:
            raise ValueError("STOP: stage shape unverified")
        if os.environ.get("V5_ALLOW_STAGE_COPY") != "YES":
            raise ValueError("STOP: explicit stage COPY environment permit absent")
        if not args.approval_file:
            raise ValueError("STOP: no separate copy-gate evidence file")
        evidence = json.loads(open(args.approval_file,encoding="utf-8").read())
        missing = blockers(COPY_GATES,evidence)
        if missing:
            raise ValueError("STOP: staged COPY gate unproven: "+",".join(missing))
        # Evidence booleans alone are not proof: run only after human review,
        # independent restore test and stage DDL approval. No auto-night install.
        after = None
        batches = inserted = 0
        while batches < args.max_batches:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                conn.execute("SET LOCAL statement_timeout='6s'")
                conn.execute("SET LOCAL lock_timeout='700ms'")
                with conn.cursor() as cur:
                    # Read up to 500 ordered source PKs first. Only then
                    # generate its bounded INSERT using the real last key.
                    sql, params = make_key_select(shape, after, args.batch)
                    cur.execute(sql, params)
                    keys = cur.fetchall()
                    if not keys:
                        print("V5_STAGE_COPY_REACHED_CURRENT_SOURCE_END")
                        break
                    last = tuple(keys[-1])
                    # Validate the source PK watermark and generate SQL.
                    window = make_window(shape, after, args.batch, last)
                    cur.execute(window.insert_rows_sql, window.insert_rows_params)
                    written = cur.rowcount
            after = last
            batches += 1
            inserted += max(0,written)
            print(f"STAGE_COPY_BATCH={batches} SELECTED={len(keys)} INSERTED={written}",flush=True)
        print(f"V5_STAGE_COPY_PROVISIONAL rows_inserted={inserted} batches={batches} "
              "DELTA_AND_PARITY_UNVERIFIED=YES CUTOVER=NO_GO",flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
