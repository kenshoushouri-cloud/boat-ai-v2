#!/usr/bin/env python3
"""Venues-only physical-staging safety gate: OFFLINE, NO DB/NETWORK/DDL.

This is NOT a migration or an authorization to migrate. It checks the
documented legacy route and prints a proposed READ-ONLY catalog audit.
It never executes that SQL, opens a DB connection, copies data, or toggles
writers, VIEWs, cron, backups or BUY. Python standard library only.

Do not use CREATE TABLE ... LIKE as proof of complete parity: foreign keys,
triggers, privileges, sequence ownership and dependencies need separate
catalog review. Never overwrite or recopy the existing v5_data.venues stage.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json"
SOURCE = "public.v2_venues"
READ_VIEW = "boat_data.venues"
STAGE = "boat_data_stage.venues"
EXISTING_STAGE = "v5_data.venues"

BEFORE_FIRST_DB_CHANGE = (
    "fresh_conoha_local_backup_generation_verified",
    "limited_restore_into_isolated_target_passed",
    "current_catalog_source_table_and_read_view_verified",
    "stage_absent_and_existing_v5_data_venues_preserved",
    "pk_all_columns_types_defaults_identity_sequences_verified",
    "unique_check_fk_indexes_triggers_rls_and_grants_reviewed",
    "view_and_reader_writer_ddl_dependencies_reviewed",
    "available_disk_wal_and_cpu_ram_budget_verified",
    "repeatable_consistent_snapshot_and_full_key_diff_designed",
    "rollback_without_affecting_legacy_collectors_designed",
    "specific_stage_only_db_change_separately_approved",
)
BEFORE_ANY_CUTOVER = (
    "independent_fresh_backup_and_test_restore_passed",
    "all_writers_readers_children_and_ddl_routes_certified",
    "inserts_updates_deletes_tracked_and_final_full_key_delta_zero",
    "row_counts_keys_and_canonical_content_digests_bidirectional_match",
    "controlled_quiet_window_and_single_writer_switch_tested",
    "dependent_views_permissions_and_rollback_rehearsed",
    "non_buy_canary_success_and_explicit_cutover_approval",
)


def validate_manifest(doc: dict) -> dict:
    """Fail closed on any ambiguous route, evidence or purported migration."""
    if not isinstance(doc, dict) or doc.get("schema_id") != "boat_shared_cutover_route_inventory_v1":
        raise ValueError("STOP: missing/unknown route manifest")
    if doc.get("intent") != "inventory_only_not_operational_instruction":
        raise ValueError("STOP: manifest is not an execution authorization")
    safety = doc.get("safety")
    if not isinstance(safety, dict) or (
        safety.get("cutover_ready") is not False
        or safety.get("unattended_cutover_scheduled") is not False
        or safety.get("active_write_route") != "legacy"
    ):
        raise ValueError("STOP: unsafe runtime state")
    rows = doc.get("tables")
    if not isinstance(rows, list) or len(rows) != 13:
        raise ValueError("STOP: expected exactly 13 documented routes")
    sources = [r.get("legacy_relation") for r in rows if isinstance(r, dict)]
    targets = [r.get("canonical_relation") for r in rows if isinstance(r, dict)]
    if len(sources) != 13 or len(set(sources)) != 13 or len(set(targets)) != 13:
        raise ValueError("STOP: incomplete or duplicate routes")
    matches = [r for r in rows if r.get("legacy_relation") == SOURCE]
    if len(matches) != 1:
        raise ValueError("STOP: missing venues source")
    r = matches[0]
    expected = {
        "canonical_relation": READ_VIEW,
        "source_relation_kind": "physical_table_observed_2026_10_23",
        "target_relation_kind": "view_nonupdatable_observed_2026_10_23",
        "candidate_files_only_not_runtime_proof": True,
        "full_writer_reader_and_ddl_coverage_certified": False,
        "physical_copy_completed": False,
        "ongoing_change_capture_validated": False,
        "production_cutover_approved": False,
    }
    if any(r.get(k) is not v if isinstance(v, bool) else r.get(k) != v
           for k, v in expected.items()):
        raise ValueError("STOP: venues route/evidence changed")
    return r


def missing_gates(required: tuple[str, ...], evidence: dict | None = None) -> list[str]:
    """Only the literal boolean True counts; this cannot confer permission."""
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValueError("STOP: evidence must be a mapping")
    return [g for g in required if evidence.get(g) is not True]


def offline_report(doc: dict, evidence: dict | None = None) -> dict:
    r = validate_manifest(doc)
    return {
        "marker": "VENUES_PILOT_PLAN_ONLY_NO_DB_NO_COPY_NO_BUY",
        "readiness": "NO_GO",
        "source_physical": SOURCE,
        "current_nonupdatable_read_view": READ_VIEW,
        "isolated_stage_proposal_NOT_CREATED": STAGE,
        "existing_separate_stage_PRESERVE": EXISTING_STAGE,
        "past_stage_rows_24_NOT_LIVE_VERIFIED": True,
        "candidate_writers_not_runtime_proof": r.get("candidate_writer_files", []),
        "stage_change_missing_gates": missing_gates(BEFORE_FIRST_DB_CHANGE, evidence),
        "cutover_missing_gates": list(BEFORE_ANY_CUTOVER),
        "ddl_generated_or_executed": False,
        "physical_copy_or_delta_executed": False,
        "live_collectors_modified": False,
        "cutover_scheduled": False,
    }


def catalog_readonly_sql() -> str:
    """Emit for future HUMAN review; does not connect or run SQL."""
    return """-- CATALOG INSPECTION ONLY; no DDL, DML or migration approval.
BEGIN TRANSACTION READ ONLY;
SELECT to_regclass('public.v2_venues') AS source,
       to_regclass('boat_data.venues') AS existing_view,
       to_regclass('boat_data_stage.venues') AS proposed_stage,
       to_regclass('v5_data.venues') AS existing_v5_stage;
SELECT n.nspname, c.relname, c.relkind, c.relrowsecurity,
       pg_get_userbyid(c.relowner) AS owner_name, c.relacl
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE (n.nspname,c.relname) IN
  (('public','v2_venues'),('boat_data','venues'),
   ('boat_data_stage','venues'),('v5_data','venues'));
SELECT a.attrelid::regclass AS relation, a.attnum, a.attname,
       format_type(a.atttypid,a.atttypmod) AS type_name,
       a.attnotnull, a.attidentity, a.attgenerated, a.attcollation,
       pg_get_expr(d.adbin,d.adrelid) AS default_expr
FROM pg_attribute a LEFT JOIN pg_attrdef d
  ON d.adrelid=a.attrelid AND d.adnum=a.attnum
WHERE a.attrelid IN (to_regclass('public.v2_venues'),
                     to_regclass('v5_data.venues'))
  AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2;
SELECT conrelid::regclass AS relation, contype, conname,
       pg_get_constraintdef(oid,true) AS definition
FROM pg_constraint WHERE conrelid IN
  (to_regclass('public.v2_venues'),to_regclass('v5_data.venues'));
SELECT indrelid::regclass AS relation, indexrelid::regclass AS index_name,
       indisprimary, indisunique, pg_get_indexdef(indexrelid) AS definition
FROM pg_index WHERE indrelid IN
  (to_regclass('public.v2_venues'),to_regclass('v5_data.venues'));
SELECT tgrelid::regclass AS relation, tgname, tgenabled,
       pg_get_triggerdef(oid,true) AS definition FROM pg_trigger
WHERE NOT tgisinternal AND tgrelid IN
  (to_regclass('public.v2_venues'),to_regclass('v5_data.venues'));
SELECT pg_get_viewdef('boat_data.venues'::regclass,true) AS active_view_sql;
SELECT pg_describe_object(d.classid,d.objid,d.objsubid) AS dependent,
       pg_describe_object(d.refclassid,d.refobjid,d.refobjsubid) AS referenced
FROM pg_depend d JOIN pg_rewrite rw ON rw.oid=d.objid
WHERE rw.ev_class=to_regclass('boat_data.venues');
ROLLBACK;
"""


class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_valid_manifest_is_always_no_go(self):
        self.assertEqual(offline_report(self.doc)["readiness"], "NO_GO")

    def test_all_gates_default_blocked(self):
        self.assertEqual(missing_gates(BEFORE_FIRST_DB_CHANGE), list(BEFORE_FIRST_DB_CHANGE))

    def test_string_true_cannot_pass_gate(self):
        self.assertIn(BEFORE_FIRST_DB_CHANGE[0],
                      missing_gates(BEFORE_FIRST_DB_CHANGE,
                                    {BEFORE_FIRST_DB_CHANGE[0]: "true"}))

    def test_even_all_true_never_executes_or_authorizes_cutover(self):
        rep = offline_report(self.doc, {g: True for g in BEFORE_FIRST_DB_CHANGE})
        self.assertEqual(rep["readiness"], "NO_GO")
        self.assertFalse(rep["ddl_generated_or_executed"])

    def test_view_route_rewrite_fails_closed(self):
        doc = copy.deepcopy(self.doc)
        next(r for r in doc["tables"] if r["legacy_relation"] == SOURCE)[
            "target_relation_kind"] = "physical_table"
        with self.assertRaises(ValueError):
            offline_report(doc)

    def test_duplicate_route_fails_closed(self):
        doc = copy.deepcopy(self.doc)
        doc["tables"][1] = copy.deepcopy(doc["tables"][0])
        with self.assertRaises(ValueError):
            offline_report(doc)

    def test_catalog_proposal_is_read_only_and_complete(self):
        sql = catalog_readonly_sql().upper()
        self.assertIn("BEGIN TRANSACTION READ ONLY", sql)
        self.assertIn("ROLLBACK", sql)
        for term in ("PG_ATTRIBUTE", "PG_CONSTRAINT", "PG_INDEX",
                     "PG_TRIGGER", "PG_DEPEND", "PG_GET_VIEWDEF", "RELACL"):
            self.assertIn(term, sql)
        for forbidden in ("CREATE TABLE ", "INSERT INTO ", "DELETE FROM ",
                          "UPDATE PUBLIC.", "DROP TABLE ", "ALTER TABLE "):
            self.assertNotIn(forbidden, sql)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--catalog-sql", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args(argv)
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests)
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if result.wasSuccessful():
            print("VENUES_OFFLINE_GATES_PASS_NO_DB_NO_COPY_NO_BUY")
        return 0 if result.wasSuccessful() else 1
    if args.catalog_sql:
        print(catalog_readonly_sql())
    else:
        print(json.dumps(offline_report(json.loads(args.manifest.read_text(
            encoding="utf-8"))), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
