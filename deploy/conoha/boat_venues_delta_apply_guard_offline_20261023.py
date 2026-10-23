#!/usr/bin/env python3
"""Venues-only fail-closed delta-apply rehearsal. Pure stdlib, synthetic data.

NO database access, credentials, subprocesses, executable SQL, stage recopy,
writer changes, cron, real transaction, or BUY. The already-created physical
boat_data_stage.venues remains untouched; boat_data.venues remains a VIEW.
Even if every *synthetic* evidence flag is True, production remains NO_GO.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import argparse
import json
import unittest

SOURCE = "public.v2_venues"
STAGE = "boat_data_stage.venues"
LIVE_VIEW = "boat_data.venues"
REQUIRED_PROOFS = (
    "fresh_independent_backup_and_isolated_restore_verified",
    "all_writer_reader_ddl_child_routes_certified",
    "active_writers_quiesced",
    "new_writer_entries_blocked",
    "post_quiesce_single_transaction_snapshot_proven",
    "source_and_stage_schema_keys_and_grants_verified",
    "lock_timeout_wal_cpu_memory_budget_verified",
    "final_full_key_recheck_and_rollback_rehearsed",
    "scoped_delta_dml_separately_approved",
)
DELETE_PROOFS = (
    "each_delete_confirmed_as_real_source_deletion",
    "all_deleted_rows_before_images_preserved",
    "downstream_delete_dependencies_verified",
    "delete_scope_separately_approved",
)


@dataclass(frozen=True)
class Venue:
    venue_code: str
    venue_id: str | None
    venue_name: str
    created_at: str
    updated_at: str
    is_active: bool


@dataclass(frozen=True)
class Snapshot:
    relation: str
    token: str
    all_keys_scanned: bool
    claimed_count: int
    rows: tuple[Venue, ...]


def _index(snapshot: Snapshot, relation: str) -> dict[str, Venue]:
    if not isinstance(snapshot, Snapshot) or snapshot.relation != relation:
        raise ValueError("STOP: source/stage name changed or not a Snapshot")
    if (not isinstance(snapshot.token, str) or not snapshot.token or
        snapshot.all_keys_scanned is not True or
        type(snapshot.claimed_count) is not int or
        snapshot.claimed_count != len(snapshot.rows)):
        raise ValueError("STOP: incomplete or inconsistent full-key snapshot")
    if not snapshot.rows:
        raise ValueError("STOP: unexpectedly empty input; mass-delete unsafe")
    by_code: dict[str, Venue] = {}
    by_venue_id: set[str] = set()
    for row in snapshot.rows:
        if not isinstance(row, Venue):
            raise ValueError("STOP: invalid row shape")
        if (not isinstance(row.venue_code, str) or not row.venue_code
            or row.venue_code in by_code):
            raise ValueError("STOP: duplicate or invalid PRIMARY KEY venue_code")
        if row.venue_id is not None:
            if (not isinstance(row.venue_id, str) or
                row.venue_id in by_venue_id):
                raise ValueError("STOP: duplicate or invalid UNIQUE venue_id")
            by_venue_id.add(row.venue_id)
        if (not isinstance(row.venue_name, str) or
            not isinstance(row.created_at, str) or
            not isinstance(row.updated_at, str) or
            type(row.is_active) is not bool):
            raise ValueError("STOP: invalid venue column type")
        by_code[row.venue_code] = row
    return by_code


def assess(source: Snapshot, stage: Snapshot, evidence: dict | None = None) -> dict:
    """Return a synthetic NO_GO report, never an authorization or DML plan."""
    if not isinstance(source, Snapshot) or not isinstance(stage, Snapshot):
        raise ValueError("STOP: missing snapshots")
    if source.token != stage.token:
        raise ValueError("STOP: snapshots from different points in time")
    src, dst = _index(source, SOURCE), _index(stage, STAGE)
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValueError("STOP: invalid evidence")
    missing = [key for key in REQUIRED_PROOFS if evidence.get(key) is not True]
    deletes = sorted(set(dst) - set(src))
    inserts = sorted(set(src) - set(dst))
    updates = sorted(k for k in set(src) & set(dst) if src[k] != dst[k])
    unchanged = len(set(src) & set(dst)) - len(updates)
    if deletes:
        missing += [key for key in DELETE_PROOFS if evidence.get(key) is not True]
        # Conservative synthetic limit, not an operational threshold.
        if len(deletes) * 10 > len(dst):
            missing.append("unexpected_delete_rate_requires_human_review")
    for key in set(src) & set(dst):
        if src[key].venue_id != dst[key].venue_id:
            missing.append("venue_id_change_or_swap_requires_separate_strategy")
            break
    stage_unique_owners = {
        row.venue_id: code for code, row in dst.items() if row.venue_id is not None
    }
    for key in inserts:
        other_key = stage_unique_owners.get(src[key].venue_id)
        if other_key is not None and other_key != key:
            missing.append("insert_collides_with_existing_unique_venue_id")
            break
    missing = list(dict.fromkeys(missing))
    changes = (
        [("DELETE", k) for k in deletes] +
        [("UPDATE", k) for k in updates] +
        [("INSERT", k) for k in inserts]
    )
    return {
        "marker": "VENUES_DELTA_APPLY_GUARD_SYNTHETIC_NO_DB_NO_BUY",
        "production_decision": "NO_GO",
        "synthetic_rehearsal_eligible_only": not missing,
        "missing_or_blocking_gates": missing,
        "counts": {"SAME": unchanged, "INSERT": len(inserts),
                   "UPDATE": len(updates), "DELETE": len(deletes)},
        "synthetic_changes": changes,
        "real_db_dml_or_cutover_performed": False,
        "real_writer_quiescence_or_restore_proven": False,
        "full_13_table_cutover_ready": False,
    }


def simulate_in_memory(source: Snapshot, stage: Snapshot, report: dict,
                       fail_after: int | None = None) -> dict:
    """Only synthetic copies; injected failure must roll back the working copy."""
    if report.get("synthetic_rehearsal_eligible_only") is not True:
        raise ValueError("STOP: blocked simulation")
    src = _index(source, SOURCE)
    original = _index(stage, STAGE)
    if source.token != stage.token:
        raise ValueError("STOP: inconsistent snapshot")
    work = original.copy()
    changes = report["synthetic_changes"]
    try:
        for i, (op, key) in enumerate(changes, 1):
            if op == "DELETE":
                work.pop(key)
            elif op in ("INSERT", "UPDATE"):
                work[key] = src[key]
            else:
                raise ValueError("STOP: unknown mutation")
            if fail_after == i:
                raise RuntimeError("synthetic injected failure")
        if work != src:
            raise ValueError("STOP: final full-key parity failure")
        return {
            "synthetic_commit": True, "synthetic_rollback": False,
            "result": work.copy(), "stage_original_unchanged": original == _index(stage, STAGE),
        }
    except (RuntimeError, ValueError, KeyError):
        work = original.copy()
        return {
            "synthetic_commit": False, "synthetic_rollback": True,
            "result": work.copy(), "stage_original_unchanged": original == _index(stage, STAGE),
        }


def row(code: str) -> Venue:
    return Venue(code, "ID" + code, "Venue " + code,
                 "2025-07-01T00:00:00+09:00", "2026-10-23T07:00:00+09:00", True)


def snap(rows: list[Venue], relation: str, **kwargs) -> Snapshot:
    args = {"token": "simulated_shared_point_1", "all_keys_scanned": True,
            "claimed_count": len(rows)}
    args.update(kwargs)
    return Snapshot(relation, args["token"], args["all_keys_scanned"],
                    args["claimed_count"], tuple(rows))


class FailClosedRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.base = [row(f"{k:02}") for k in range(1, 25)]
        self.proofs = {p: True for p in REQUIRED_PROOFS + DELETE_PROOFS}

    def check(self, source=None, stage=None, proof=None):
        return assess(snap(self.base if source is None else source, SOURCE),
                      snap(self.base if stage is None else stage, STAGE),
                      self.proofs if proof is None else proof)

    def test_all_missing_gates_are_no_go(self):
        p = self.check(proof={})
        self.assertEqual(p["production_decision"], "NO_GO")
        self.assertEqual(len(p["missing_or_blocking_gates"]), len(REQUIRED_PROOFS))

    def test_string_true_not_accepted(self):
        p = self.check(proof={p: "true" for p in REQUIRED_PROOFS})
        self.assertFalse(p["synthetic_rehearsal_eligible_only"])

    def test_all_synthetic_proofs_never_authorize_production(self):
        p = self.check()
        self.assertTrue(p["synthetic_rehearsal_eligible_only"])
        self.assertEqual(p["production_decision"], "NO_GO")
        self.assertFalse(p["real_db_dml_or_cutover_performed"])

    def test_writer_not_quiesced_blocks(self):
        e = dict(self.proofs, active_writers_quiesced=False)
        self.assertIn("active_writers_quiesced", self.check(proof=e)["missing_or_blocking_gates"])

    def test_child_writer_not_certified_blocks(self):
        e = dict(self.proofs, all_writer_reader_ddl_child_routes_certified=False)
        self.assertFalse(self.check(proof=e)["synthetic_rehearsal_eligible_only"])

    def test_new_writer_entry_not_blocked(self):
        e = dict(self.proofs, new_writer_entries_blocked=False)
        self.assertFalse(self.check(proof=e)["synthetic_rehearsal_eligible_only"])

    def test_independent_backup_restore_unverified_blocks(self):
        e = dict(self.proofs, fresh_independent_backup_and_isolated_restore_verified=False)
        self.assertFalse(self.check(proof=e)["synthetic_rehearsal_eligible_only"])

    def test_snapshot_proof_missing_blocks(self):
        e = dict(self.proofs, post_quiesce_single_transaction_snapshot_proven=False)
        self.assertFalse(self.check(proof=e)["synthetic_rehearsal_eligible_only"])

    def test_separate_user_approval_missing_blocks(self):
        e = dict(self.proofs, scoped_delta_dml_separately_approved=False)
        self.assertFalse(self.check(proof=e)["synthetic_rehearsal_eligible_only"])

    def test_mismatched_capture_token_rejected(self):
        with self.assertRaisesRegex(ValueError, "different points"):
            assess(snap(self.base, SOURCE),
                   snap(self.base, STAGE, token="different"), self.proofs)

    def test_incomplete_key_scan_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            assess(snap(self.base, SOURCE, all_keys_scanned=False),
                   snap(self.base, STAGE), self.proofs)

    def test_wrong_row_count_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            assess(snap(self.base, SOURCE, claimed_count=23),
                   snap(self.base, STAGE), self.proofs)

    def test_empty_source_mass_delete_rejected(self):
        with self.assertRaisesRegex(ValueError, "mass-delete"):
            self.check(source=[])

    def test_duplicate_pk_rejected(self):
        with self.assertRaisesRegex(ValueError, "PRIMARY KEY"):
            self.check(source=self.base + [self.base[0]])

    def test_duplicate_venue_id_rejected(self):
        changed = self.base.copy()
        changed[1] = replace(changed[1], venue_id=changed[0].venue_id)
        with self.assertRaisesRegex(ValueError, "UNIQUE"):
            self.check(source=changed)

    def test_venue_id_swap_blocks(self):
        changed = self.base.copy()
        changed[0] = replace(changed[0], venue_id="ID02")
        changed[1] = replace(changed[1], venue_id="ID01")
        self.assertIn("venue_id_change_or_swap_requires_separate_strategy",
                      self.check(source=changed)["missing_or_blocking_gates"])

    def test_insert_clashes_with_stage_unique(self):
        source = [v for v in self.base if v.venue_code != "01"]
        source.append(replace(row("25"), venue_id="ID01"))
        p = self.check(source=source)
        self.assertIn("insert_collides_with_existing_unique_venue_id",
                      p["missing_or_blocking_gates"])

    def test_delete_without_proofs_blocks(self):
        proof = {k: True for k in REQUIRED_PROOFS}
        p = self.check(source=self.base[1:], proof=proof)
        self.assertIn("each_delete_confirmed_as_real_source_deletion",
                      p["missing_or_blocking_gates"])

    def test_unexpected_delete_rate_blocks_even_with_proofs(self):
        p = self.check(source=self.base[4:])
        self.assertIn("unexpected_delete_rate_requires_human_review",
                      p["missing_or_blocking_gates"])

    def test_one_proven_delete_is_only_synthetic(self):
        p = self.check(source=self.base[1:])
        self.assertEqual(p["counts"]["DELETE"], 1)
        self.assertTrue(p["synthetic_rehearsal_eligible_only"])
        self.assertEqual(p["production_decision"], "NO_GO")

    def test_in_memory_fault_rolls_back(self):
        source = self.base.copy()
        source[0] = replace(source[0], updated_at="2026-10-24T07:00:00+09:00")
        p = self.check(source=source)
        r = simulate_in_memory(snap(source, SOURCE), snap(self.base, STAGE), p, fail_after=1)
        self.assertTrue(r["synthetic_rollback"])
        self.assertFalse(r["synthetic_commit"])
        self.assertEqual(r["result"]["01"], self.base[0])
        self.assertTrue(r["stage_original_unchanged"])

    def test_in_memory_parity_without_mutating_input(self):
        source = self.base.copy()
        source[0] = replace(source[0], is_active=False)
        p = self.check(source=source)
        r = simulate_in_memory(snap(source, SOURCE), snap(self.base, STAGE), p)
        self.assertTrue(r["synthetic_commit"])
        self.assertEqual(r["result"]["01"], source[0])
        self.assertEqual(self.base[0].is_active, True)
        self.assertTrue(r["stage_original_unchanged"])

    def test_blocked_report_cannot_rehearse(self):
        p = self.check(proof={})
        with self.assertRaisesRegex(ValueError, "blocked simulation"):
            simulate_in_memory(snap(self.base, SOURCE), snap(self.base, STAGE), p)

    def test_wrong_relation_rejected(self):
        with self.assertRaisesRegex(ValueError, "name changed"):
            assess(snap(self.base, SOURCE), snap(self.base, LIVE_VIEW), self.proofs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        r = unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(FailClosedRehearsalTests)
        )
        if r.wasSuccessful():
            print("VENUES_DELTA_APPLY_FAIL_CLOSED_OFFLINE_PASS_NO_DB_NO_BUY")
        return 0 if r.wasSuccessful() else 1
    sample = assess(snap([row("01")], SOURCE), snap([row("01")], STAGE))
    print(json.dumps(sample, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
