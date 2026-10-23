"""Offline V5/V6 13-table staging and complete-key delta *planning* only.

NEVER connects to ConoHa, reads credentials, writes databases, copies rows,
modifies views, turns on timers, or invokes the BUY system. In particular,
boat_data.* are 13 read-only VIEWs, NOT destinations for direct INSERT.
This module has NO --apply. Run under Python stdlib only from repository root.

Full-key digest reconciliation is designed for a quiesced, consistent source
and target snapshot. It cannot infer changes safely from a race_date cursor,
and it is NOT change-data capture (CDC). A caller must prove completeness,
locks and transaction consistency before treating results as applicable.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Iterable, Iterator

from boat_shared_storage_contract import RELATIONS, assert_contract

STAGE_SCHEMA = "boat_data_stage"
DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json"
)
STAGE_GATES = (
    "fresh_local_backup_and_restore_test",
    "free_space_wal_and_peak_copy_budget_verified",
    "original_source_physical_and_stage_absent_in_live_catalog",
    "table_schema_primary_keys_defaults_indexes_privileges_audited",
    "staging_never_used_as_live_writer",
    "snapshot_isolation_and_final_delta_strategy_reviewed",
    "named_table_and_operation_explicitly_approved",
)
CUTOVER_GATES = (
    "all_runtime_writers_readers_child_jobs_and_ddl_certified",
    "all_13_physical_stage_tables_parity_verified",
    "all_inserts_updates_deletes_reconciled_from_consistent_snapshots",
    "all_db_writers_quiesced_and_new_writes_blocked",
    "current_independent_backup_and_restore_passed",
    "final_bidirectional_keys_rows_and_content_digests_match",
    "all_reader_writer_and_view_dependencies_switched_atomically",
    "rollback_without_split_writes_rehearsed",
    "non_buy_canary_and_resumption_verified",
    "night_window_and_named_scope_explicitly_approved",
)
HEX256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class TablePlan:
    source: str
    existing_read_view: str
    isolated_staging_relation: str
    source_runtime_writers_proven: bool = False
    stage_ready_for_write: bool = False
    cutover_ready: bool = False


@dataclass(frozen=True)
class DigestRow:
    # Stable, complete physical PK (not a row offset or partial date).
    key: tuple[str, ...]
    digest: str  # Canonical row content SHA256, all mutation-relevant columns.


@dataclass(frozen=True)
class DeltaAction:
    operation: str  # INSERT, UPDATE or DELETE; PLAN ONLY, no SQL execution.
    key: tuple[str, ...]
    source_digest: str | None


def blockers(required: tuple[str, ...], evidence: dict) -> tuple[str, ...]:
    """A missing key, string 'true', 1, or stale unknown proof blocks GO."""
    if not isinstance(evidence, dict):
        raise ValueError("STOP: evidence must be an explicit mapping")
    return tuple(name for name in required if evidence.get(name) is not True)


def inspect_manifest(document: dict) -> tuple[TablePlan, ...]:
    """Only the exact, documented 13 source/view identities are permitted."""
    if not isinstance(document, dict):
        raise ValueError("STOP: invalid migration manifest")
    assert_contract()
    if document.get("schema_id") != "boat_shared_cutover_route_inventory_v1":
        raise ValueError("STOP: wrong manifest version")
    if document.get("intent") != "inventory_only_not_operational_instruction":
        raise ValueError("STOP: manifest cannot authorize execution")
    safety = document.get("safety") or {}
    if (
        safety.get("cutover_ready") is not False
        or safety.get("unattended_cutover_scheduled") is not False
        or safety.get("active_write_route") != "legacy"
    ):
        raise ValueError("STOP: manifest safety state changed")
    rows = document.get("tables")
    expected = {row.legacy: row.canonical for row in RELATIONS}
    if not isinstance(rows, list) or len(rows) != len(expected) or len(expected) != 13:
        raise ValueError("STOP: expected exactly 13 source relations")
    seen: set[str] = set()
    plans = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("STOP: malformed table record")
        src, canonical = row.get("legacy_relation"), row.get("canonical_relation")
        if src not in expected or canonical != expected[src] or src in seen:
            raise ValueError("STOP: unapproved or duplicate relation mapping")
        if (
            row.get("target_relation_kind") != "view_nonupdatable_observed_2026_10_23"
            or row.get("source_relation_kind") != "physical_table_observed_2026_10_23"
            or row.get("candidate_files_only_not_runtime_proof") is not True
            or row.get("full_writer_reader_and_ddl_coverage_certified") is not False
            or row.get("physical_copy_completed") is not False
            or row.get("production_cutover_approved") is not False
        ):
            raise ValueError("STOP: source/view or cutover status not proven")
        view_name = canonical.split(".", 1)[1]
        stage = STAGE_SCHEMA + "." + view_name
        if stage == canonical or stage == src or src.startswith("boat_data."):
            raise ValueError("STOP: staging conflicts with live source/view")
        plans.append(TablePlan(src, canonical, stage))
        seen.add(src)
    return tuple(sorted(plans, key=lambda item: item.source))


def _checked(rows: Iterable[DigestRow]) -> Iterator[DigestRow]:
    """Ensure complete PK order and unique keys; never silently deduplicate."""
    previous: tuple[str, ...] | None = None
    for row in rows:
        if not isinstance(row, DigestRow):
            raise ValueError("STOP: expected DigestRow")
        if (
            not row.key
            or not isinstance(row.key, tuple)
            or any(not isinstance(k, str) or not k for k in row.key)
            or not isinstance(row.digest, str)
            or HEX256.fullmatch(row.digest) is None
        ):
            raise ValueError("STOP: invalid PK or row digest")
        if previous is not None and row.key <= previous:
            raise ValueError("STOP: unsorted or duplicate key")
        previous = row.key
        yield row


def plan_full_key_delta(
    source: Iterable[DigestRow], staged: Iterable[DigestRow]
) -> Iterator[DeltaAction]:
    """Stream a *hypothetical* INSERT/UPDATE/DELETE diff without modifying data.

    Caller must guarantee each iterator covers every key and every relevant
    column at one consistent post-quiesce point. An unscanned date range can
    produce dangerous false DELETEs: never turn this iterator into SQL DML.
    """
    a, b = iter(_checked(source)), iter(_checked(staged))
    x, y = next(a, None), next(b, None)
    while x is not None or y is not None:
        if y is None or (x is not None and x.key < y.key):
            yield DeltaAction("INSERT", x.key, x.digest)
            x = next(a, None)
        elif x is None or y.key < x.key:
            yield DeltaAction("DELETE", y.key, None)
            y = next(b, None)
        else:
            if x.digest != y.digest:
                yield DeltaAction("UPDATE", x.key, x.digest)
            x, y = next(a, None), next(b, None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    plans = inspect_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    print(json.dumps({
        "mode": "OFFLINE_PLAN_ONLY_NO_DB_NO_NETWORK_NO_DDL",
        "source_view_count": len(plans),
        "staging_schema_proposal_not_created": STAGE_SCHEMA,
        "readiness": "NO_GO",
        "stage_missing_gates": list(blockers(STAGE_GATES, {})),
        "cutover_missing_gates": list(blockers(CUTOVER_GATES, {})),
        "relations": [asdict(p) for p in plans],
        "cutover_or_copy_scheduled": False,
        "live_collection_unchanged": True,
        "buy_enabled": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
