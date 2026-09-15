# -*- coding: utf-8 -*-
"""Research-only archive read-through abstraction.

This module is deliberately storage-format agnostic and is not imported by any
Production PRE/FINAL path.  It provides a fail-closed contract for migrating
historical research consumers away from direct SQL assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Iterable, Mapping, Protocol, Sequence


class MissingEvidenceError(RuntimeError):
    """Raised when no single source can fully satisfy an evidence query."""


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
    sources.  Historical jobs should query bounded partitions (for example one
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
