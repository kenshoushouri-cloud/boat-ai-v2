#!/usr/bin/env python3
"""OFFLINE venues full-key delta planning. Never connect, copy, synchronize or cut over.

Real ConoHa stage boat_data_stage.venues already exists with 24 copied rows.
Never CREATE, recopy, ALTER, DROP or DML that stage without separate approval.
Only compare complete, consistent, synthetic input snapshots here. Same
snapshot token is an assertion by the caller, NOT proof of PostgreSQL locks.
Even a zero-delta result is not CDC and cannot authorize a write/cutover.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from deploy.conoha.boat_shared_staging_delta_plan_offline import (
    DigestRow, plan_full_key_delta,
)

SOURCE = "public.v2_venues"
STAGE = "boat_data_stage.venues"
VIEW = "boat_data.venues"  # Remains a non-updatable VIEW, not a write target.
FIELDS = ("venue_code", "venue_name", "created_at", "updated_at", "venue_id", "is_active")
REQUIRED_BEFORE_ANY_DELTA_DML = (
    "current_independent_backup_and_restore_proven",
    "source_and_stage_readback_catalog_and_schema_parity_proven",
    "complete_source_stage_snapshots_same_consistent_transaction",
    "active_writer_paths_and_child_jobs_certified",
    "atomic_recheck_and_no_lost_writes_strategy_proven",
    "insert_update_delete_rollback_rehearsed",
    "operation_scoped_separate_explicit_approval",
)
# These guards are NOT enough for real cutover; 13-table global gates also apply.


@dataclass(frozen=True)
class Snapshot:
    relation: str
    rows: tuple[dict, ...]
    capture_token: str
    claimed_row_count: int
    complete_keyspace_proven: bool
    consistent_snapshot_proven: bool


def _normalized_timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("STOP: timestamp must be ISO8601 text with UTC offset")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("STOP: invalid timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("STOP: timezone-less timestamp cannot be compared")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _digest_rows(snapshot: Snapshot, required_relation: str) -> list[DigestRow]:
    if snapshot.relation != required_relation:
        raise ValueError("STOP: wrong source/stage route")
    if (not snapshot.capture_token or
        snapshot.complete_keyspace_proven is not True or
        snapshot.consistent_snapshot_proven is not True):
        raise ValueError("STOP: partial/unproven snapshot")
    if (type(snapshot.claimed_row_count) is not int or
        snapshot.claimed_row_count != len(snapshot.rows)):
        raise ValueError("STOP: row count not proven")
    if not snapshot.rows:
        raise ValueError("STOP: venues snapshot unexpectedly empty")
    out: list[DigestRow] = []
    seen_pk: set[str] = set()
    seen_venue_ids: set[str] = set()
    for row in snapshot.rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError("STOP: missing/extra venues columns")
        key, venue_id = row["venue_code"], row["venue_id"]
        if not isinstance(key, str) or not key or key in seen_pk:
            raise ValueError("STOP: blank/duplicate primary key")
        if venue_id is not None:
            if not isinstance(venue_id, str) or venue_id in seen_venue_ids:
                raise ValueError("STOP: invalid/duplicate venue_id unique key")
            seen_venue_ids.add(venue_id)
        seen_pk.add(key)
        if row["venue_name"] is not None and not isinstance(row["venue_name"], str):
            raise ValueError("STOP: venue_name type mismatch")
        if row["is_active"] is not None and type(row["is_active"]) is not bool:
            raise ValueError("STOP: is_active type mismatch")
        normalized = dict(row)
        for col in ("created_at", "updated_at"):
            normalized[col] = _normalized_timestamp(row[col])
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        out.append(DigestRow((key,), sha256(payload.encode("utf-8")).hexdigest()))
    return sorted(out, key=lambda x: x.key)


def plan(source: Snapshot, stage: Snapshot, evidence: dict | None = None) -> dict:
    """Pure, fail-closed. Never emits executable SQL or changes stage rows."""
    if (not isinstance(source, Snapshot) or not isinstance(stage, Snapshot) or
        source.capture_token != stage.capture_token):
        raise ValueError("STOP: not same validated read transaction")
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict):
        raise ValueError("STOP: evidence must be mapping")
    source_rows = _digest_rows(source, SOURCE)
    stage_rows = _digest_rows(stage, STAGE)
    actions = list(plan_full_key_delta(source_rows, stage_rows))
    counts = {"INSERT": 0, "UPDATE": 0, "DELETE": 0}
    for action in actions:
        counts[action.operation] += 1
    counts["SAME"] = len(source_rows) - counts["INSERT"] - counts["UPDATE"]
    return {
        "marker": "VENUES_FULL_KEY_DELTA_PLAN_ONLY_NO_DB_NO_BUY",
        "source": SOURCE, "stage_already_created": STAGE,
        "live_view_unchanged": VIEW,
        "mode": "SYNTHETIC_CONSISTENT_SNAPSHOT_PLAN_ONLY",
        "decision": "NO_GO",
        "missing_delta_dml_gates": [
            g for g in REQUIRED_BEFORE_ANY_DELTA_DML if evidence.get(g) is not True
        ],
        "counts": counts,
        "actions_preview": [
            {"operation": a.operation, "key": a.key[0]} for a in actions
        ],
        "stage_writes_or_cutover_performed": False,
        "cdc_or_future_changes_proven": False,
    }


def _row(code: str, stamp: str = "2026-10-22T07:00:09+09:00") -> dict:
    return {
        "venue_code": code, "venue_name": "会場" + code,
        "created_at": "2025-07-01T00:00:00+09:00",
        "updated_at": stamp, "venue_id": "ID" + code,
        "is_active": True,
    }


def _snap(rows: list[dict], relation: str, **kwargs) -> Snapshot:
    defaults = {
        "capture_token": "synthetic_txn_1",
        "claimed_row_count": len(rows),
        "complete_keyspace_proven": True,
        "consistent_snapshot_proven": True,
    }
    defaults.update(kwargs)
    return Snapshot(relation, tuple(rows), **defaults)


class OfflineDeltaTests(unittest.TestCase):
    def setUp(self):
        self.base = [_row(f"{n:02}") for n in range(1, 25)]

    def compare(self, src, stg, **kw):
        return plan(_snap(src, SOURCE, **kw), _snap(stg, STAGE, **kw))

    def test_24_unchanged(self):
        p = self.compare(self.base, self.base)
        self.assertEqual(p["counts"], {"INSERT": 0, "UPDATE": 0, "DELETE": 0, "SAME": 24})

    def test_morning_24_timestamp_updates(self):
        newer = [dict(r, updated_at="2026-10-23T07:00:09+09:00") for r in self.base]
        self.assertEqual(self.compare(newer, self.base)["counts"]["UPDATE"], 24)

    def test_inserts_updates_and_deletes(self):
        src = [dict(r) for r in self.base if r["venue_code"] != "01"]
        src[1]["venue_name"] = "新名称"
        src.append(_row("25"))
        p = self.compare(src, self.base)
        self.assertEqual({k: p["counts"][k] for k in ("INSERT", "UPDATE", "DELETE")},
                         {"INSERT": 1, "UPDATE": 1, "DELETE": 1})
        self.assertEqual([(a["operation"], a["key"]) for a in p["actions_preview"]],
                         [("DELETE", "01"), ("UPDATE", "03"), ("INSERT", "25")])

    def test_timezone_equivalence_not_false_update(self):
        src = [dict(r) for r in self.base]
        src[0]["updated_at"] = "2026-10-21T22:00:09+00:00"
        self.assertEqual(self.compare(src, self.base)["counts"]["UPDATE"], 0)

    def test_not_only_updated_at_matters(self):
        src = [dict(r) for r in self.base]
        src[0]["is_active"] = False
        self.assertEqual(self.compare(src, self.base)["counts"]["UPDATE"], 1)

    def test_partial_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, "partial"):
            self.compare(self.base, self.base, complete_keyspace_proven=False)

    def test_inconsistent_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, "partial"):
            self.compare(self.base, self.base, consistent_snapshot_proven=False)

    def test_separate_capture_tokens_rejected(self):
        with self.assertRaisesRegex(ValueError, "same validated"):
            plan(_snap(self.base, SOURCE), _snap(self.base, STAGE, capture_token="other"))

    def test_unproven_count_rejected(self):
        with self.assertRaisesRegex(ValueError, "row count"):
            self.compare(self.base, self.base, claimed_row_count=23)

    def test_duplicate_primary_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "primary key"):
            self.compare(self.base + [dict(self.base[0])], self.base)

    def test_duplicate_unique_id_rejected(self):
        src = [dict(r) for r in self.base]
        src[1]["venue_id"] = src[0]["venue_id"]
        with self.assertRaisesRegex(ValueError, "venue_id"):
            self.compare(src, self.base)

    def test_missing_column_rejected(self):
        src = [dict(r) for r in self.base]
        del src[0]["is_active"]
        with self.assertRaisesRegex(ValueError, "columns"):
            self.compare(src, self.base)

    def test_naive_timestamp_rejected(self):
        src = [dict(r) for r in self.base]
        src[0]["updated_at"] = "2026-10-23T07:00:09"
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.compare(src, self.base)

    def test_empty_source_never_mass_delete(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            self.compare([], self.base)

    def test_no_mutation_even_with_all_gates_true(self):
        before = json.dumps(self.base, sort_keys=True, ensure_ascii=False)
        p = self.compare(self.base, self.base)
        self.assertEqual(p["decision"], "NO_GO")
        self.assertFalse(p["stage_writes_or_cutover_performed"])
        self.assertEqual(before, json.dumps(self.base, sort_keys=True, ensure_ascii=False))
        ev = {g: True for g in REQUIRED_BEFORE_ANY_DELTA_DML}
        self.assertEqual(plan(_snap(self.base, SOURCE), _snap(self.base, STAGE), ev)["decision"],
                         "NO_GO")

    def test_string_true_does_not_pass_evidence(self):
        gate = REQUIRED_BEFORE_ANY_DELTA_DML[0]
        p = plan(_snap(self.base, SOURCE), _snap(self.base, STAGE), {gate: "true"})
        self.assertIn(gate, p["missing_delta_dml_gates"])

    def test_wrong_target_view_not_allowed(self):
        with self.assertRaisesRegex(ValueError, "route"):
            plan(_snap(self.base, SOURCE), _snap(self.base, VIEW))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(OfflineDeltaTests)
        )
        if result.wasSuccessful():
            print("VENUES_FULL_KEY_DELTA_OFFLINE_TESTS_PASS_NO_DB_NO_BUY")
        return 0 if result.wasSuccessful() else 1
    p = plan(_snap([_row("01")], SOURCE), _snap([_row("01")], STAGE))
    print(json.dumps(p, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
