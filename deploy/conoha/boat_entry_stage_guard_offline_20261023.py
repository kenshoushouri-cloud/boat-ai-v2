#!/usr/bin/env python3
"""Synthetic entry_snapshots stage gates. No database, network, subprocess or SQL.

E01-E12 correspond to docs/BOAT_ENTRY_SNAPSHOTS_ISOLATED_STAGE_DESIGN_20261023.md.
All inputs are synthetic and "approved"/"backed up" flags are NOT real evidence.
This module can NEVER authorize a live copy, DML, cutover, or BUY.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
import unittest

SOURCE = "public.v2_realtime_entry_snapshots"
STAGE = "boat_data_stage.entry_snapshots"
VIEW = "boat_data.entry_snapshots"
OLD_SEQUENCE = "v2_realtime_entry_snapshots_id_seq"
KEY = ("race_id", "snapshot_label", "lane")
COLUMNS = (
    "id", "race_id", "race_date", "venue_id", "venue_code", "race_no",
    "snapshot_label", "snapshot_at", "source", "lane", "racer_number",
    "racer_name", "racer_class", "original_course", "exhibition_course",
    "is_course_changed", "motor_no", "boat_no", "tilt", "raw", "updated_at",
)
REQUIRED_EVIDENCE = (
    "independent_fresh_backup_restored",
    "all_writers_readers_ddl_audited",
    "concurrent_writes_tracked_without_gaps",
    "disk_wal_lock_cpu_limits_reviewed",
    "new_stage_and_copy_separately_approved",
)
ERROR_PREFIX = "STOP: "


@dataclass(frozen=True)
class Contract:
    source: str = SOURCE
    target: str = STAGE
    columns: tuple[str, ...] = COLUMNS
    primary_key: tuple[str, ...] = ("id",)
    unique_key: tuple[str, ...] = KEY
    required_not_null: tuple[str, ...] = KEY
    stage_exists: bool = False
    stage_id_default: str | None = None
    old_sequence_dependency: bool = False
    recopy_venues: bool = False


@dataclass(frozen=True)
class Snapshot:
    relation: str
    token: str
    rows: tuple[dict, ...]
    full_key_scan: bool = True
    exact_count: int | None = None
    count_is_estimate: bool = False


def validate_contract(contract: Contract) -> None:
    """A modeled schema gate, NOT verification of live PostgreSQL metadata."""
    if not isinstance(contract, Contract):
        raise ValueError(ERROR_PREFIX + "missing contract")
    if (contract.source != SOURCE or contract.target != STAGE or
        contract.columns != COLUMNS or contract.primary_key != ("id",) or
        contract.unique_key != KEY or not set(KEY).issubset(contract.required_not_null)):
        raise ValueError(ERROR_PREFIX + "schema or target mismatch")
    if contract.stage_exists or contract.recopy_venues:
        raise ValueError(ERROR_PREFIX + "stage exists or forbidden venues recopy")
    if contract.stage_id_default not in (None, "") or contract.old_sequence_dependency:
        raise ValueError(ERROR_PREFIX + "inherited ID sequence/default forbidden")


def _snapshot_map(snap: Snapshot, relation: str) -> tuple[dict, dict]:
    if not isinstance(snap, Snapshot) or snap.relation != relation:
        raise ValueError(ERROR_PREFIX + "snapshot route mismatch")
    if (not isinstance(snap.token, str) or not snap.token or
        snap.full_key_scan is not True or snap.count_is_estimate is not False or
        type(snap.exact_count) is not int or snap.exact_count != len(snap.rows)):
        raise ValueError(ERROR_PREFIX + "incomplete/estimated snapshot")
    if not snap.rows:
        raise ValueError(ERROR_PREFIX + "empty source or stage is unsafe")
    by_key: dict[tuple, dict] = {}
    by_id: dict[int, tuple] = {}
    for row in snap.rows:
        if not isinstance(row, dict) or set(row) != set(COLUMNS):
            raise ValueError(ERROR_PREFIX + "21-column mismatch")
        key = tuple(row[col] for col in KEY)
        if (any(v is None or v == "" for v in key) or
            type(row["id"]) is not int or row["id"] <= 0):
            raise ValueError(ERROR_PREFIX + "null natural key or invalid ID")
        if key in by_key or row["id"] in by_id:
            raise ValueError(ERROR_PREFIX + "duplicate natural key / ID")
        by_key[key] = row
        by_id[row["id"]] = key
    return by_key, by_id


def snap(rows: list[dict] | tuple[dict, ...], relation: str, **kwargs) -> Snapshot:
    token = kwargs.pop("token", "synthetic_mvcc_1")
    exact_count = kwargs.pop("exact_count", len(rows))
    return Snapshot(relation, token, tuple(deepcopy(rows)), exact_count=exact_count, **kwargs)


def assess(source: Snapshot, stage: Snapshot, *,
           evidence: dict | None = None) -> dict:
    """Full natural-key AND ID comparison; never emits a write plan."""
    if source.token != stage.token:
        raise ValueError(ERROR_PREFIX + "mixed MVCC snapshots")
    src, src_ids = _snapshot_map(source, SOURCE)
    dst, dst_ids = _snapshot_map(stage, STAGE)
    for shared_key in src.keys() & dst.keys():
        if src[shared_key]["id"] != dst[shared_key]["id"]:
            raise ValueError(ERROR_PREFIX + "changed ID on natural key")
    for shared_id in src_ids.keys() & dst_ids.keys():
        if src_ids[shared_id] != dst_ids[shared_id]:
            raise ValueError(ERROR_PREFIX + "changed natural key for same ID")
    inserted = src.keys() - dst.keys()
    deleted = dst.keys() - src.keys()
    updated = {k for k in src.keys() & dst.keys() if src[k] != dst[k]}
    if len(deleted) * 10 > len(dst):
        raise ValueError(ERROR_PREFIX + "unusually high DELETE ratio")
    proof = {} if evidence is None else evidence
    if not isinstance(proof, dict):
        raise ValueError(ERROR_PREFIX + "evidence not mapping")
    missing = [g for g in REQUIRED_EVIDENCE if proof.get(g) is not True]
    return {
        "counts": {
            "SAME": len(src.keys() & dst.keys()) - len(updated),
            "INSERT": len(inserted), "UPDATE": len(updated), "DELETE": len(deleted)
        },
        "initial_snapshot_parity": not (inserted or updated or deleted),
        "missing_synthetic_proofs": missing,
        "safely_detected_all_full_keys_in_synthetic_snapshot": True,
        "future_changes_or_cdc_verified": False,
        "production_decision": "NO_GO",
        "live_db_write_or_cutover": False,
        "marker": "ENTRY_STAGE_GUARD_SYNTHETIC_NO_DB_NO_BUY",
    }


def in_memory_initial_copy(source: Snapshot, contract: Contract,
                           *, fail_after: int | None = None) -> dict:
    """An in-memory imitation of atomic DDL+COPY. Never invokes a database."""
    validate_contract(contract)
    original = deepcopy(source.rows)
    _snapshot_map(source, SOURCE)
    staged: list[dict] = []
    try:
        for i, row in enumerate(source.rows, 1):
            staged.append(deepcopy(row))   # explicitly preserves the original ID
            if fail_after == i:
                raise RuntimeError("synthetic COPY/timeout/disk error")
        stage = snap(staged, STAGE, token=source.token)
        result = assess(source, stage)
        if not result["initial_snapshot_parity"]:
            raise RuntimeError("synthetic parity check failed")
        return {
            "initial_parity": True, "synthetic_rollback": False,
            "stage_rows": stage.rows, "original_source_unchanged": original == source.rows,
            "future_sync_proven": False, "production_decision": "NO_GO",
        }
    except RuntimeError:
        staged.clear()  # simulated atomic rollback
        return {
            "initial_parity": False, "synthetic_rollback": True,
            "stage_rows": (), "original_source_unchanged": original == source.rows,
            "future_sync_proven": False, "production_decision": "NO_GO",
        }


def make_row(n: int) -> dict:
    """21 synthetic columns. Values do not represent live race data."""
    return {
        "id": n, "race_id": f"synthetic_{n // 6}", "race_date": "2026-10-23",
        "venue_id": "V01", "venue_code": "01", "race_no": 1,
        "snapshot_label": "offline", "snapshot_at": "2026-10-23T07:00:00+09:00",
        "source": "synthetic", "lane": n, "racer_number": str(n),
        "racer_name": f"Synthetic {n}", "racer_class": "A1",
        "original_course": n, "exhibition_course": n,
        "is_course_changed": False, "motor_no": n, "boat_no": n,
        "tilt": "0", "raw": {"synthetic": n},
        "updated_at": "2026-10-23T07:00:00+09:00",
    }


class EntryStageOfflineTests(unittest.TestCase):
    def setUp(self):
        # 24 keys allow single DELETE below the conservative 10% test gate.
        self.base = [make_row(n) for n in range(1, 25)]

    def test_E01_column_pk_unique_and_notnull_contract_rejected(self):
        for changed in (
            replace(Contract(), columns=COLUMNS[:-1]),
            replace(Contract(), primary_key=("race_id",)),
            replace(Contract(), unique_key=("id",)),
            replace(Contract(), required_not_null=("race_id", "lane")),
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, "schema"):
                    validate_contract(changed)

    def test_E02_old_serial_default_or_sequence_dependency_stops(self):
        for changed in (
            replace(Contract(), stage_id_default=f"nextval('{OLD_SEQUENCE}'::regclass)"),
            replace(Contract(), old_sequence_dependency=True),
        ):
            with self.assertRaisesRegex(ValueError, "sequence"):
                validate_contract(changed)

    def test_E03_no_default_and_explicit_id_copy_only_synthetic(self):
        source = snap(self.base, SOURCE)
        result = in_memory_initial_copy(source, Contract())
        self.assertTrue(result["initial_parity"])
        self.assertEqual([r["id"] for r in result["stage_rows"]],
                         [r["id"] for r in self.base])
        self.assertEqual(result["production_decision"], "NO_GO")
        self.assertFalse(result["future_sync_proven"])

    def test_E04_existing_stage_wrong_route_or_venues_recopy_blocked(self):
        for changed in (
            replace(Contract(), stage_exists=True),
            replace(Contract(), target="v5_data.raw_entry_snapshots"),
            replace(Contract(), recopy_venues=True),
        ):
            with self.assertRaises(ValueError):
                validate_contract(changed)

    def test_E05_all_columns_bidirectional_same_snapshot(self):
        s = snap(self.base, SOURCE)
        t = snap(self.base, STAGE)
        p = assess(s, t)
        self.assertEqual(p["counts"], {"SAME": 24, "INSERT": 0, "UPDATE": 0, "DELETE": 0})
        self.assertTrue(p["initial_snapshot_parity"])
        changed = deepcopy(self.base)
        changed[0]["raw"] = {"synthetic": "changed"}
        q = assess(snap(changed, SOURCE), t)
        self.assertEqual(q["counts"]["UPDATE"], 1)

    def test_E06_mixed_incomplete_or_estimated_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, "mixed"):
            assess(snap(self.base, SOURCE), snap(self.base, STAGE, token="other"))
        for altered in ({"full_key_scan": False}, {"count_is_estimate": True},
                        {"exact_count": 124631}):
            with self.subTest(altered=altered):
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    assess(snap(self.base, SOURCE, **altered), snap(self.base, STAGE))

    def test_E07_full_key_insert_update_delete_even_without_time_change(self):
        src = deepcopy(self.base[1:])
        src[0]["racer_name"] = "changed without updating updated_at"
        src.append(make_row(25))
        result = assess(snap(src, SOURCE), snap(self.base, STAGE))
        self.assertEqual(result["counts"],
                         {"SAME": 22, "INSERT": 1, "UPDATE": 1, "DELETE": 1})

    def test_E08_id_key_swap_or_collision_stops(self):
        changed = deepcopy(self.base)
        changed[0]["id"] = 100
        with self.assertRaisesRegex(ValueError, "changed ID"):
            assess(snap(changed, SOURCE), snap(self.base, STAGE))
        changed = deepcopy(self.base)
        changed[0]["lane"] = 100
        with self.assertRaisesRegex(ValueError, "changed natural key"):
            assess(snap(changed, SOURCE), snap(self.base, STAGE))
        changed = deepcopy(self.base)
        changed[0]["id"] = changed[1]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            assess(snap(changed, SOURCE), snap(self.base, STAGE))

    def test_E09_empty_partial_or_mass_delete_stops(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            assess(snap([], SOURCE), snap(self.base, STAGE))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            assess(snap(self.base[:20], SOURCE, full_key_scan=False),
                   snap(self.base, STAGE))
        with self.assertRaisesRegex(ValueError, "DELETE"):
            assess(snap(self.base[4:], SOURCE), snap(self.base, STAGE))

    def test_E10_concurrent_new_snapshot_not_mistaken_for_cdc(self):
        first = in_memory_initial_copy(snap(self.base, SOURCE), Contract())
        self.assertTrue(first["initial_parity"])
        self.assertFalse(first["future_sync_proven"])
        newer = deepcopy(self.base)
        newer[0]["racer_name"] = "writer changed row later"
        with self.assertRaisesRegex(ValueError, "mixed"):
            assess(snap(newer, SOURCE, token="next_mvcc"),
                   snap(list(first["stage_rows"]), STAGE, token="original_mvcc"))

    def test_E11_injected_failure_rolls_back_synthetic_copy(self):
        original = deepcopy(self.base)
        for fail_after in (1, 13, 24):
            with self.subTest(fail_after=fail_after):
                r = in_memory_initial_copy(snap(self.base, SOURCE), Contract(),
                                           fail_after=fail_after)
                self.assertTrue(r["synthetic_rollback"])
                self.assertEqual(r["stage_rows"], ())
                self.assertEqual(self.base, original)
                self.assertTrue(r["original_source_unchanged"])

    def test_E12_missing_proofs_or_even_mock_approval_cannot_go_live(self):
        base = snap(self.base, SOURCE)
        stage = snap(self.base, STAGE)
        p = assess(base, stage)
        self.assertEqual(set(p["missing_synthetic_proofs"]), set(REQUIRED_EVIDENCE))
        proofs = {name: True for name in REQUIRED_EVIDENCE}
        p2 = assess(base, stage, evidence=proofs)
        self.assertEqual(p2["missing_synthetic_proofs"], [])
        self.assertEqual(p2["production_decision"], "NO_GO")
        self.assertFalse(p2["live_db_write_or_cutover"])
        self.assertFalse(p2["future_changes_or_cdc_verified"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        outcome = unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(EntryStageOfflineTests)
        )
        if outcome.wasSuccessful():
            print("ENTRY_STAGE_FAIL_CLOSED_OFFLINE_12_PASS_NO_DB_NO_BUY")
        return 0 if outcome.wasSuccessful() else 1
    print("ENTRY_STAGE_GUARD_DESIGN_ONLY_NO_DB_NO_BUY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
