# -*- coding: utf-8 -*-
"""Pure fail-closed gate for a future non-Production fresh-restore rehearsal.

This module validates only caller-supplied manifest data. It has no database,
network, Railway, filesystem mutation, archive upload, or Production path.
"""
from __future__ import annotations

import re
from typing import Any

CONTRACT = "v4_fresh_restore_rehearsal_manifest_v1"
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_RETENTION_MODES = {"keep_all", "bounded"}
CONSERVATIVE_HOBBY_LIMIT_BYTES = 5_000_000_000


class FreshRestoreRehearsalManifestError(ValueError):
    pass


def _sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise FreshRestoreRehearsalManifestError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return value


def evaluate_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FreshRestoreRehearsalManifestError("manifest must be an object")
    if data.get("contract") != CONTRACT:
        raise FreshRestoreRehearsalManifestError("unexpected manifest contract")

    source = data.get("source")
    if not isinstance(source, dict):
        raise FreshRestoreRehearsalManifestError("source missing")
    main_sha = source.get("main_sha")
    if not isinstance(main_sha, str) or SHA40_RE.fullmatch(main_sha) is None:
        raise FreshRestoreRehearsalManifestError("source main_sha must be lowercase 40-hex")
    if source.get("production_read_only") is not True:
        raise FreshRestoreRehearsalManifestError("source must be production read-only")
    if source.get("destructive_operations") is not False:
        raise FreshRestoreRehearsalManifestError("source destructive operations must be false")

    target = data.get("target")
    if not isinstance(target, dict):
        raise FreshRestoreRehearsalManifestError("target missing")
    if target.get("production") is not False:
        raise FreshRestoreRehearsalManifestError("rehearsal target must be non-Production")
    if target.get("ephemeral") is not True:
        raise FreshRestoreRehearsalManifestError("rehearsal target must be ephemeral")
    postgres_major = target.get("postgres_major")
    if (
        not isinstance(postgres_major, int)
        or isinstance(postgres_major, bool)
        or postgres_major < 14
    ):
        raise FreshRestoreRehearsalManifestError("target postgres_major must be >= 14")

    retention = data.get("online_retention")
    if not isinstance(retention, dict) or retention.get("frozen") is not True:
        raise FreshRestoreRehearsalManifestError("online retention policy must be frozen")
    tables = retention.get("tables")
    if not isinstance(tables, list) or not tables:
        raise FreshRestoreRehearsalManifestError("online retention tables must be non-empty")

    seen_tables: set[str] = set()
    bounded_count = 0
    for row in tables:
        if not isinstance(row, dict):
            raise FreshRestoreRehearsalManifestError("retention table row must be an object")
        table = row.get("table")
        mode = row.get("mode")
        if not isinstance(table, str) or not table:
            raise FreshRestoreRehearsalManifestError("retention table name missing")
        if table in seen_tables:
            raise FreshRestoreRehearsalManifestError(f"duplicate retention table: {table}")
        seen_tables.add(table)
        if mode not in ALLOWED_RETENTION_MODES:
            raise FreshRestoreRehearsalManifestError(
                f"unknown retention mode for {table}: {mode!r}"
            )
        if mode == "bounded":
            bounded_count += 1
            boundary = row.get("boundary")
            if not isinstance(boundary, str) or not boundary.strip():
                raise FreshRestoreRehearsalManifestError(
                    f"bounded retention boundary missing: {table}"
                )
            _sha256(row.get("boundary_sha256"), field=f"{table} boundary_sha256")

    protected = retention.get("protected_evidence_tables")
    if not isinstance(protected, list) or not protected:
        raise FreshRestoreRehearsalManifestError(
            "protected_evidence_tables must be non-empty"
        )
    if any(not isinstance(x, str) or not x for x in protected):
        raise FreshRestoreRehearsalManifestError("invalid protected evidence table")
    missing_protected = sorted(set(protected) - seen_tables)
    if missing_protected:
        raise FreshRestoreRehearsalManifestError(
            "protected evidence table absent from retention manifest: "
            + ",".join(missing_protected)
        )

    archive = data.get("archive_recovery")
    if not isinstance(archive, dict):
        raise FreshRestoreRehearsalManifestError("archive_recovery missing")
    if archive.get("primary_archive_verified") is not True:
        raise FreshRestoreRehearsalManifestError("primary archive must be verified")
    if archive.get("second_recovery_layer_verified") is not True:
        raise FreshRestoreRehearsalManifestError(
            "independent second recovery layer must be verified"
        )
    excluded = archive.get("excluded_partitions")
    if not isinstance(excluded, list):
        raise FreshRestoreRehearsalManifestError("excluded_partitions must be a list")
    for idx, row in enumerate(excluded):
        if not isinstance(row, dict):
            raise FreshRestoreRehearsalManifestError("excluded partition must be an object")
        if not isinstance(row.get("partition_id"), str) or not row["partition_id"]:
            raise FreshRestoreRehearsalManifestError("excluded partition_id missing")
        _sha256(
            row.get("manifest_sha256"),
            field=f"excluded_partitions[{idx}] manifest_sha256",
        )

    schema = data.get("schema")
    if not isinstance(schema, dict):
        raise FreshRestoreRehearsalManifestError("schema identity missing")
    _sha256(schema.get("schema_sha256"), field="schema_sha256")
    _sha256(schema.get("migration_script_sha256"), field="migration_script_sha256")
    if schema.get("indexes_constraints_extensions_frozen") is not True:
        raise FreshRestoreRehearsalManifestError(
            "indexes/constraints/extensions must be frozen"
        )

    headroom = data.get("headroom_policy")
    if not isinstance(headroom, dict) or headroom.get("frozen") is not True:
        raise FreshRestoreRehearsalManifestError("headroom policy must be frozen")
    limit = headroom.get("volume_limit_bytes")
    reserve = headroom.get("required_reserve_bytes")
    daily_growth = headroom.get("measured_daily_growth_bytes")
    growth_days = headroom.get("growth_horizon_days")
    for name, value in (
        ("volume_limit_bytes", limit),
        ("required_reserve_bytes", reserve),
        ("measured_daily_growth_bytes", daily_growth),
        ("growth_horizon_days", growth_days),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise FreshRestoreRehearsalManifestError(f"{name} must be an integer")
    if limit != CONSERVATIVE_HOBBY_LIMIT_BYTES:
        raise FreshRestoreRehearsalManifestError(
            "Hobby volume_limit_bytes must use conservative 5,000,000,000-byte cap"
        )
    if reserve <= 0:
        raise FreshRestoreRehearsalManifestError("required_reserve_bytes must be positive")
    if daily_growth < 0:
        raise FreshRestoreRehearsalManifestError("measured_daily_growth_bytes cannot be negative")
    if growth_days <= 0:
        raise FreshRestoreRehearsalManifestError("growth_horizon_days must be positive")
    if reserve < daily_growth * growth_days:
        raise FreshRestoreRehearsalManifestError(
            "required reserve is below measured growth horizon"
        )

    approvals = data.get("approvals")
    if not isinstance(approvals, dict):
        raise FreshRestoreRehearsalManifestError("approvals missing")
    if approvals.get("non_production_rehearsal_allowed") is not True:
        raise FreshRestoreRehearsalManifestError(
            "non-Production rehearsal is not authorized by manifest"
        )
    if approvals.get("production_migration_authorized") is not False:
        raise FreshRestoreRehearsalManifestError(
            "manifest must not authorize Production migration"
        )

    return {
        "contract": "v4_fresh_restore_rehearsal_gate_v1",
        "source_main_sha": main_sha,
        "retention_table_count": len(tables),
        "bounded_retention_table_count": bounded_count,
        "protected_evidence_table_count": len(protected),
        "excluded_archive_partition_count": len(excluded),
        "volume_limit_bytes": limit,
        "required_reserve_bytes": reserve,
        "growth_horizon_bytes": daily_growth * growth_days,
        "rehearsal_allowed": True,
        "target_production": False,
        "source_production_read_only": True,
        "production_migration_authorized": False,
        "purchase_action": False,
        "decision": "PASS_NON_PRODUCTION_REHEARSAL_PREREQUISITES",
    }
