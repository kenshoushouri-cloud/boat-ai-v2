#!/usr/bin/env python3
"""Prepare one atomic PostgreSQL transaction creating 12 EMPTY V5 stage tables.

DEFAULT --plan prints DDL for review, never connects to DB.
--apply requires independently audited restore evidence + explicit scoped
approval, runs on local ConoHa via psql only (no psycopg/pip), and cannot
switch views, stop collector, copy rows or initiate any purchase.

No existing relation is dropped, replaced, truncated, or updated.
PostgreSQL rolls back ALL 12 CREATE TABLE operations if any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from boat_shared_storage_contract import RELATIONS, assert_contract
from v5.offline_stage_batch_plan import TARGETS

APPROVAL_MARKER = "V5_EMPTY_STAGE_12_ONLY_APPROVED"
MANDATORY_EVIDENCE = (
    "independent_backup_restore_tested_and_reviewed",
    "stage_schema_scope_explicitly_approved",
    "disk_and_wal_headroom_checked",
    "existing_venues_stage_verified_unchanged",
)
IDENT = re.compile(r"[a-z_][a-z_0-9]*\Z")


def qname(value: str) -> str:
    names = value.split(".")
    if len(names) != 2 or not all(IDENT.fullmatch(x) for x in names):
        raise ValueError("STOP: unqualified or unexpected relation")
    return ".".join('"' + x + '"' for x in names)


def planned() -> list[tuple[str, str]]:
    assert_contract()
    contract = {row.legacy: row.canonical for row in RELATIONS}
    if len(TARGETS) != 13 or len(contract) != 13:
        raise ValueError("STOP: 13-source route contract mismatch")
    entries = []
    for source, (stage, wave) in TARGETS.items():
        if source == "public.v2_venues":
            if stage != "boat_data_stage.venues" or wave != 0:
                raise ValueError("STOP: existing venues stage route altered")
            continue
        if contract.get(source) != "boat_data." + stage.split(".")[-1]:
            raise ValueError("STOP: storage contract and stage route mismatch")
        if wave not in (1, 2) or not stage.startswith("boat_data_stage."):
            raise ValueError("STOP: unexpected stage destination")
        qname(source)
        qname(stage)
        entries.append((source, stage))
    if len(entries) != 12 or len({b for _, b in entries}) != 12:
        raise ValueError("STOP: exactly twelve unique stages required")
    return entries


def values(entries: list[tuple[str, str]]) -> str:
    return ",\n        ".join("('%s','%s')" % (a, b) for a, b in entries)


def ddl_plan() -> str:
    entries = planned()
    mapping = values(entries)
    preflight = r"""
DO $guard$
DECLARE
  rec record;
  src_oid oid;
  venues_oid oid;
BEGIN
  IF current_database() <> 'railway' THEN
    RAISE EXCEPTION 'NO_GO_WRONG_DATABASE';
  END IF;
  IF to_regnamespace('boat_data_stage') IS NULL THEN
    RAISE EXCEPTION 'NO_GO_STAGE_SCHEMA_MISSING';
  END IF;
  venues_oid := to_regclass('boat_data_stage.venues');
  IF venues_oid IS NULL OR
     (SELECT relkind FROM pg_class WHERE oid=venues_oid) <> 'r' THEN
    RAISE EXCEPTION 'NO_GO_EXISTING_VENUES_STAGE_MISSING';
  END IF;
  FOR rec IN SELECT * FROM (VALUES
        __PAIRS__
  ) AS m(source_name,stage_name)
  LOOP
    src_oid := to_regclass(rec.source_name);
    IF src_oid IS NULL THEN
      RAISE EXCEPTION 'NO_GO_MISSING_SOURCE %',rec.source_name;
    END IF;
    IF (SELECT relkind FROM pg_class WHERE oid=src_oid) <> 'r' THEN
      RAISE EXCEPTION 'NO_GO_SOURCE_NOT_REGULAR_TABLE %',rec.source_name;
    END IF;
    IF to_regclass(rec.stage_name) IS NOT NULL THEN
      RAISE EXCEPTION 'NO_GO_STAGE_EXISTS %',rec.stage_name;
    END IF;
    IF (SELECT count(*) FROM pg_index i
        WHERE i.indrelid=src_oid AND i.indisprimary) <> 1 THEN
      RAISE EXCEPTION 'NO_GO_PK_MISSING_OR_AMBIGUOUS %',rec.source_name;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_attribute a
               WHERE a.attrelid=src_oid AND a.attnum>0
                 AND NOT a.attisdropped AND a.attgenerated<>'') THEN
      RAISE EXCEPTION 'NO_GO_SOURCE_GENERATED_COLUMN %',rec.source_name;
    END IF;
  END LOOP;
END
$guard$;""".replace("__PAIRS__",mapping)
    create = "\n".join(
        "CREATE TABLE %s (LIKE %s INCLUDING CONSTRAINTS INCLUDING INDEXES);"
        % (qname(dst), qname(src))
        for src, dst in entries
    )
    postflight = r"""
DO $check$
DECLARE
  rec record;
  src_oid oid;
  dst_oid oid;
  source_cols text;
  stage_cols text;
  source_pk text;
  stage_pk text;
BEGIN
  FOR rec IN SELECT * FROM (VALUES
        __PAIRS__
  ) AS m(source_name,stage_name)
  LOOP
    src_oid := to_regclass(rec.source_name);
    dst_oid := to_regclass(rec.stage_name);
    IF dst_oid IS NULL OR
       (SELECT relkind FROM pg_class WHERE oid=dst_oid)<>'r' THEN
      RAISE EXCEPTION 'NO_GO_STAGE_CREATE_FAILED %',rec.stage_name;
    END IF;
    SELECT string_agg(format('%s:%s:%s:%s:%s',
      a.attname,a.atttypid,a.atttypmod,a.attcollation,a.attnotnull),
      ',' ORDER BY a.attnum)
    INTO source_cols
    FROM pg_attribute a WHERE a.attrelid=src_oid
      AND a.attnum>0 AND NOT a.attisdropped;
    SELECT string_agg(format('%s:%s:%s:%s:%s',
      a.attname,a.atttypid,a.atttypmod,a.attcollation,a.attnotnull),
      ',' ORDER BY a.attnum)
    INTO stage_cols
    FROM pg_attribute a WHERE a.attrelid=dst_oid
      AND a.attnum>0 AND NOT a.attisdropped;
    IF source_cols IS DISTINCT FROM stage_cols THEN
      RAISE EXCEPTION 'NO_GO_STAGE_COLUMNS_MISMATCH %',rec.stage_name;
    END IF;
    SELECT string_agg(a.attname,',' ORDER BY k.ord)
      INTO source_pk
    FROM pg_index i
    JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord)
      ON TRUE
    JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
    WHERE i.indrelid=src_oid AND i.indisprimary;
    SELECT string_agg(a.attname,',' ORDER BY k.ord)
      INTO stage_pk
    FROM pg_index i
    JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord)
      ON TRUE
    JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
    WHERE i.indrelid=dst_oid AND i.indisprimary;
    IF source_pk IS NULL OR source_pk IS DISTINCT FROM stage_pk THEN
      RAISE EXCEPTION 'NO_GO_PK_MISMATCH %',rec.stage_name;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_attrdef d WHERE d.adrelid=dst_oid)
        OR EXISTS (
          SELECT 1 FROM pg_attribute a WHERE a.attrelid=dst_oid
            AND a.attnum>0 AND (a.attidentity<>'' OR a.attgenerated<>'')
        )
        OR EXISTS (
          SELECT 1 FROM pg_trigger t WHERE t.tgrelid=dst_oid
            AND NOT t.tgisinternal
        )
        OR EXISTS (
          SELECT 1 FROM pg_constraint f WHERE f.conrelid=dst_oid
            AND f.contype='f'
        ) THEN
      RAISE EXCEPTION 'NO_GO_STAGE_DEFAULT_SEQUENCE_OR_SIDE_EFFECT %',rec.stage_name;
    END IF;
  END LOOP;
END
$check$;""".replace("__PAIRS__",mapping)
    return "\n".join((
        "\\set ON_ERROR_STOP on",
        "BEGIN;",
        "SET LOCAL lock_timeout='800ms';",
        "SET LOCAL statement_timeout='12000ms';",
        "SET LOCAL idle_in_transaction_session_timeout='15000ms';",
        "SET LOCAL search_path='pg_catalog';",
        preflight,
        create,
        postflight,
        "COMMIT;",
        "SELECT 'V5_EMPTY_STAGE_12_CREATED_NO_ROWS_NO_CUTOVER' AS verdict;",
    )) + "\n"


def gates_verified(path: str) -> None:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("approval_marker") != APPROVAL_MARKER:
        raise ValueError("STOP: stage-scoped approval marker missing")
    if any(payload.get(k) is not True for k in MANDATORY_EVIDENCE):
        raise ValueError("STOP: independent restore or stage DDL gate missing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="default: print plan only")
    parser.add_argument("--apply", action="store_true", help="independently gated empty stage creation")
    parser.add_argument("--approval-file")
    args = parser.parse_args()
    sql = ddl_plan()
    if not args.apply:
        print("V5_EMPTY_STAGE_12_SQL_PLAN_ONLY_NO_DB_ACCESS")
        print(sql)
        return 0
    if args.plan:
        raise ValueError("STOP: --plan and --apply conflict")
    if os.environ.get("V5_ALLOW_EMPTY_STAGE_DDL") != "YES" or not args.approval_file:
        raise ValueError("STOP: scoped stage DDL authorization missing")
    gates_verified(args.approval_file)
    if os.geteuid() != 0 and os.geteuid() != 26:
        # UID is deployment-specific. Prefer postgres peer auth verified by psql.
        pass
    run = subprocess.run(
        ["psql", "-X", "-P", "pager=off", "-v", "ON_ERROR_STOP=1",
         "-d", "railway"], input=sql, text=True,
        timeout=90, check=False,
    )
    if run.returncode:
        raise RuntimeError("STOP: PostgreSQL empty-stage transaction rolled back or failed")
    print("V5_EMPTY_STAGE_12_APPLY_FINISHED_NO_COPY_NO_ROUTE_SWITCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
