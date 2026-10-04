# -*- coding: utf-8 -*-
"""Research-only archive read-through abstraction.

This module is deliberately storage-format isolated and is not imported by any
Production PRE/FINAL path. It provides a fail-closed contract for migrating
historical research consumers away from direct SQL assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence


class MissingEvidenceError(RuntimeError):
    """Raised when no single source can fully satisfy an evidence query."""


class ArchiveIntegrityError(RuntimeError):
    """Raised when an archive manifest or payload fails verification."""


@dataclass(frozen=True)
class EvidenceQuery:
    table: str
    start_date: str | None = None
    end_date: str | None = None
    race_ids: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.table.strip():
            raise ValueError("table is required")
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if any(not str(x).strip() for x in self.race_ids):
            raise ValueError("race_ids must not contain empty values")
        if any(not str(x).strip() for x in self.labels):
            raise ValueError("labels must not contain empty values")


@dataclass(frozen=True)
class EvidenceBatch:
    rows: tuple[Mapping[str, Any], ...]
    source_name: str
    query: EvidenceQuery


class HistoricalDataSource(Protocol):
    """A source must explicitly declare full-query coverage before reading."""

    @property
    def name(self) -> str:
        ...

    def covers(self, query: EvidenceQuery) -> bool:
        ...

    def fetch(self, query: EvidenceQuery) -> Sequence[Mapping[str, Any]]:
        ...


class ReadThroughStore:
    """Prefer online data, otherwise use verified archive data.

    This first contract intentionally does not merge partial results from two
    sources. Historical jobs should query bounded partitions (for example one
    calendar month) so coverage is explicit and reproducible.
    """

    def __init__(self, online: HistoricalDataSource, archive: HistoricalDataSource):
        self.online = online
        self.archive = archive

    def fetch(self, query: EvidenceQuery) -> EvidenceBatch:
        if self.online.covers(query):
            return EvidenceBatch(tuple(self.online.fetch(query)), self.online.name, query)
        if self.archive.covers(query):
            return EvidenceBatch(tuple(self.archive.fetch(query)), self.archive.name, query)
        raise MissingEvidenceError(
            "required evidence is not fully covered by online or archive source: "
            f"table={query.table} start={query.start_date} end={query.end_date} "
            f"race_ids={len(query.race_ids)} labels={query.labels}"
        )


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _safe_archive_path(manifest_path: Path, archive_file: str) -> Path:
    if not archive_file or Path(archive_file).name != archive_file:
        raise ArchiveIntegrityError("manifest archive_file must be a basename")
    return manifest_path.parent / archive_file


def _restore_scalar(value: Any, data_type: str, udt_name: str) -> Any:
    """Restore JSON-safe archive scalars to PostgreSQL-like Python values.

    The exporter serializes Decimal/date/datetime values into stable strings so
    JSON does not lose precision. The manifest preserves the original schema;
    read-through uses that schema to reconstruct the value types seen by
    psycopg research consumers. Unknown types remain unchanged and null always
    remains null.
    """
    if value is None:
        return None
    dt = (data_type or "").lower()
    udt = (udt_name or "").lower()
    try:
        if dt in {"numeric", "decimal"} or udt == "numeric":
            return Decimal(str(value))
        if dt in {"smallint", "integer", "bigint"} or udt in {"int2", "int4", "int8"}:
            return int(value)
        if dt in {"real", "double precision"} or udt in {"float4", "float8"}:
            return float(value)
        if dt == "boolean" or udt == "bool":
            if isinstance(value, bool):
                return value
            raw = str(value).strip().lower()
            if raw in {"true", "t", "1"}:
                return True
            if raw in {"false", "f", "0"}:
                return False
            raise ValueError(f"invalid boolean value: {value!r}")
        if dt == "date" or udt == "date":
            return date.fromisoformat(str(value))
        if "timestamp" in dt or udt in {"timestamp", "timestamptz"}:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ArchiveIntegrityError(
            f"cannot restore archive scalar type data_type={data_type!r} "
            f"udt_name={udt_name!r} value={value!r}"
        ) from exc
    return value


def _schema_type_map(manifest: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    raw_schema = manifest.get("schema")
    if not isinstance(raw_schema, list) or not raw_schema:
        raise ArchiveIntegrityError("manifest schema is missing or empty")
    out: dict[str, tuple[str, str]] = {}
    for item in raw_schema:
        if not isinstance(item, Mapping):
            raise ArchiveIntegrityError("manifest schema entry is invalid")
        name = str(item.get("column_name") or "").strip()
        if not name:
            raise ArchiveIntegrityError("manifest schema column_name is missing")
        if name in out:
            raise ArchiveIntegrityError(f"manifest schema has duplicate column: {name}")
        out[name] = (str(item.get("data_type") or ""), str(item.get("udt_name") or ""))
    return out


def _restore_row_types(
    row: Mapping[str, Any], schema_types: Mapping[str, tuple[str, str]]
) -> dict[str, Any]:
    unknown = set(row) - set(schema_types)
    if unknown:
        raise ArchiveIntegrityError(
            f"archive row contains columns not present in manifest schema: {sorted(unknown)}"
        )
    return {
        key: _restore_scalar(value, *schema_types[key]) if key in schema_types else value
        for key, value in row.items()
    }


class JsonlGzipPartitionSource:
    """Verified single-partition archive source for research jobs.

    V1 intentionally requires the query's date range to exactly match the
    manifest partition. This avoids silent partial coverage or cross-partition
    stitching while the migration contract is being established.
    """

    def __init__(self, manifest_path: str | Path):
        self.manifest_path = Path(manifest_path)
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ArchiveIntegrityError(f"cannot read manifest: {self.manifest_path}") from exc
        if int(self.manifest.get("archive_contract_version", 0)) != 1:
            raise ArchiveIntegrityError("unsupported archive contract version")
        if not self.manifest.get("readback_verified"):
            raise ArchiveIntegrityError("manifest is not readback-verified")
        if self.manifest.get("source_rows_deleted") is not False:
            raise ArchiveIntegrityError("pilot manifest must assert source_rows_deleted=false")
        self.schema_types = _schema_type_map(self.manifest)
        self.archive_path = _safe_archive_path(
            self.manifest_path, str(self.manifest.get("archive_file") or "")
        )
        if not self.archive_path.is_file():
            raise ArchiveIntegrityError(f"archive file is missing: {self.archive_path}")

    @property
    def name(self) -> str:
        return f"archive:{self.manifest_path.name}"

    def covers(self, query: EvidenceQuery) -> bool:
        if query.table != self.manifest.get("table"):
            return False
        if query.start_date is None or query.end_date is None:
            return False
        if query.start_date != self.manifest.get("start_date"):
            return False
        if query.end_date != self.manifest.get("end_date"):
            return False
        manifest_label = self.manifest.get("label")
        if query.labels:
            return len(query.labels) == 1 and query.labels[0] == manifest_label
        return manifest_label is None

    def _verified_rows(self) -> list[dict[str, Any]]:
        expected_file_sha = str(self.manifest.get("archive_file_sha256") or "")
        actual_file_sha = _sha256_file(self.archive_path)
        if not expected_file_sha or actual_file_sha != expected_file_sha:
            raise ArchiveIntegrityError(
                f"archive file SHA mismatch: expected={expected_file_sha} actual={actual_file_sha}"
            )

        expected_rows = int(self.manifest.get("row_count", -1))
        expected_payload_sha = str(self.manifest.get("canonical_payload_sha256") or "")
        expected_payload_bytes = int(self.manifest.get("canonical_payload_bytes", -1))
        payload_sha = hashlib.sha256()
        payload_bytes = 0
        raw_rows: list[dict[str, Any]] = []
        with gzip.open(self.archive_path, "rb") as fh:
            for raw_line in fh:
                payload_sha.update(raw_line)
                payload_bytes += len(raw_line)
                try:
                    row = json.loads(raw_line.decode("utf-8"))
                except Exception as exc:
                    raise ArchiveIntegrityError("archive contains invalid JSONL") from exc
                if not isinstance(row, dict):
                    raise ArchiveIntegrityError("archive row is not a JSON object")
                raw_rows.append(row)

        actual_payload_sha = payload_sha.hexdigest()
        if len(raw_rows) != expected_rows:
            raise ArchiveIntegrityError(
                f"archive row-count mismatch: expected={expected_rows} actual={len(raw_rows)}"
            )
        if payload_bytes != expected_payload_bytes:
            raise ArchiveIntegrityError(
                "archive payload-size mismatch: "
                f"expected={expected_payload_bytes} actual={payload_bytes}"
            )
        if not expected_payload_sha or actual_payload_sha != expected_payload_sha:
            raise ArchiveIntegrityError(
                "archive payload SHA mismatch: "
                f"expected={expected_payload_sha} actual={actual_payload_sha}"
            )
        return [_restore_row_types(row, self.schema_types) for row in raw_rows]

    def fetch(self, query: EvidenceQuery) -> Sequence[Mapping[str, Any]]:
        if not self.covers(query):
            raise MissingEvidenceError(
                f"archive partition does not fully cover query: {self.manifest_path}"
            )
        rows = self._verified_rows()
        race_ids = set(query.race_ids)
        if race_ids:
            rows = [r for r in rows if str(r.get("race_id") or "") in race_ids]
        if query.labels:
            labels = set(query.labels)
            rows = [r for r in rows if str(r.get("snapshot_label") or "") in labels]
        return rows


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def canonical_rows_digest(
    rows: Iterable[Mapping[str, Any]],
    *,
    key_fields: Sequence[str],
    fields: Sequence[str] | None = None,
) -> tuple[int, str]:
    """Return deterministic row count + SHA-256 for equality audits.

    The digest is for research equivalence checks; it is not a database backup.
    Rows are sorted by the declared logical key and encoded as canonical JSONL.
    """
    materialized = [dict(r) for r in rows]
    if not key_fields:
        raise ValueError("key_fields is required")

    def key(row: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(json.dumps(_jsonable(row.get(k)), ensure_ascii=False, sort_keys=True) for k in key_fields)

    materialized.sort(key=key)
    sha = hashlib.sha256()
    for row in materialized:
        selected = row if fields is None else {f: row.get(f) for f in fields}
        payload = json.dumps(
            _jsonable(selected),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        sha.update(payload)
        sha.update(b"\n")
    return len(materialized), sha.hexdigest()


def assert_equivalent(
    left: Iterable[Mapping[str, Any]],
    right: Iterable[Mapping[str, Any]],
    *,
    key_fields: Sequence[str],
    fields: Sequence[str] | None = None,
) -> tuple[int, str]:
    """Fail closed unless two rowsets have the exact same canonical digest."""
    left_count, left_sha = canonical_rows_digest(left, key_fields=key_fields, fields=fields)
    right_count, right_sha = canonical_rows_digest(right, key_fields=key_fields, fields=fields)
    if left_count != right_count or left_sha != right_sha:
        raise AssertionError(
            "archive equivalence failed: "
            f"left_count={left_count} right_count={right_count} "
            f"left_sha={left_sha} right_sha={right_sha}"
        )
    return left_count, left_sha
