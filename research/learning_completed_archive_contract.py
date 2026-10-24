# -*- coding: utf-8 -*-
"""Pure contract for a future completed-learning cold archive.

Research only. This module performs no database, filesystem, network, Railway,
LINE, subprocess, or archive writes. It only validates immutable manifest data
that a separately reviewed archive/restore implementation would have to prove.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Iterable, Tuple

CONTRACT_VERSION = "learning-completed-cold-archive-v1"
SOURCE_LABEL = "learning_all"
ARCHIVE_FORMAT = "pg-copy-csv-explicit-columns-v1"
COMPRESSION_FORMAT = "gzip-mtime0-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

TABLE_IDENTITIES: dict[str, Tuple[str, ...]] = {
    "v2_realtime_odds_snapshots": ("race_id", "snapshot_label", "ticket"),
    "v2_realtime_weather_snapshots": ("race_id", "snapshot_label"),
    "v2_realtime_exhibition_snapshots": ("race_id", "snapshot_label", "lane"),
    "v2_realtime_entry_snapshots": ("race_id", "snapshot_label", "lane"),
    "v2_realtime_race_condition_snapshots": ("race_id", "snapshot_label"),
    "v2_realtime_racer_condition_snapshots": ("race_id", "snapshot_label", "lane"),
}

REQUIRED_COMMON_COLUMNS = ("race_id", "race_date", "snapshot_label", "snapshot_at")


class ArchiveContractError(ValueError):
    """Raised when a manifest cannot satisfy the frozen archive contract."""


@dataclass(frozen=True)
class ArchiveManifest:
    contract_version: str
    table_name: str
    source_label: str
    archive_format: str
    compression_format: str
    start_date: date
    end_date: date
    source_row_count: int
    restored_row_count: int
    column_names: Tuple[str, ...]
    column_type_names: Tuple[str, ...]
    identity_columns: Tuple[str, ...]
    schema_sha256: str
    source_content_sha256: str
    restored_content_sha256: str
    archive_file_sha256: str


def _require_sha(value: str, field: str) -> None:
    if not SHA256_RE.fullmatch(value or ""):
        raise ArchiveContractError(f"{field} must be lowercase SHA-256 hex")


def validate_manifest(manifest: ArchiveManifest, *, today: date) -> None:
    """Fail closed unless one archive unit proves deterministic restore identity.

    `today` is passed explicitly so the function is deterministic and performs no
    clock access. Archive units may contain completed dates only: end_date < today.
    """
    if manifest.contract_version != CONTRACT_VERSION:
        raise ArchiveContractError("contract version mismatch")
    if manifest.table_name not in TABLE_IDENTITIES:
        raise ArchiveContractError("table is outside the six-table learning contract")
    if manifest.source_label != SOURCE_LABEL:
        raise ArchiveContractError("only learning_all may be archived by this contract")
    if manifest.archive_format != ARCHIVE_FORMAT:
        raise ArchiveContractError("archive format mismatch")
    if manifest.compression_format != COMPRESSION_FORMAT:
        raise ArchiveContractError("compression format mismatch")
    if manifest.start_date > manifest.end_date:
        raise ArchiveContractError("invalid date range")
    if manifest.end_date >= today:
        raise ArchiveContractError("current/future dates are never archive-eligible")
    if manifest.source_row_count <= 0:
        raise ArchiveContractError("empty archive units are not deletion evidence")
    if manifest.restored_row_count != manifest.source_row_count:
        raise ArchiveContractError("restore row count differs from source")

    if not manifest.column_names or len(manifest.column_names) != len(manifest.column_type_names):
        raise ArchiveContractError("column/type metadata must be complete")
    if len(set(manifest.column_names)) != len(manifest.column_names):
        raise ArchiveContractError("duplicate column name")
    if any(not name for name in manifest.column_names):
        raise ArchiveContractError("blank column name")
    if any(not typ for typ in manifest.column_type_names):
        raise ArchiveContractError("blank PostgreSQL type name")

    expected_identity = TABLE_IDENTITIES[manifest.table_name]
    if manifest.identity_columns != expected_identity:
        raise ArchiveContractError("identity columns differ from frozen table contract")
    missing = [c for c in (*REQUIRED_COMMON_COLUMNS, *expected_identity) if c not in manifest.column_names]
    if missing:
        raise ArchiveContractError(f"required columns missing: {sorted(set(missing))}")

    for field, value in (
        ("schema_sha256", manifest.schema_sha256),
        ("source_content_sha256", manifest.source_content_sha256),
        ("restored_content_sha256", manifest.restored_content_sha256),
        ("archive_file_sha256", manifest.archive_file_sha256),
    ):
        _require_sha(value, field)

    if manifest.restored_content_sha256 != manifest.source_content_sha256:
        raise ArchiveContractError("restored content checksum differs from source")


def validate_archive_set(manifests: Iterable[ArchiveManifest], *, today: date) -> None:
    """Validate a set and reject overlapping units for the same table/date range."""
    items = tuple(manifests)
    if not items:
        raise ArchiveContractError("archive set must not be empty")
    for item in items:
        validate_manifest(item, today=today)

    by_table: dict[str, list[ArchiveManifest]] = {}
    for item in items:
        by_table.setdefault(item.table_name, []).append(item)
    for table, rows in by_table.items():
        ordered = sorted(rows, key=lambda x: (x.start_date, x.end_date))
        previous_end: date | None = None
        for item in ordered:
            if previous_end is not None and item.start_date <= previous_end:
                raise ArchiveContractError(f"overlapping archive units for {table}")
            previous_end = item.end_date


def deletion_gate(manifests: Iterable[ArchiveManifest], *, today: date) -> str:
    """Return only research readiness; never authorization to mutate Production."""
    validate_archive_set(manifests, today=today)
    return "ARCHIVE_RESTORE_EVIDENCE_COMPLETE_BUT_PRODUCTION_DELETE_REQUIRES_SEPARATE_APPROVAL"
