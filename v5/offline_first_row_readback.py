# -*- coding: utf-8 -*-
"""Offline V5 first-row readback *shape* review; NOT a DB or Forward gate.

No DB connection, SQL execution, network, file writes or production integration.
All supplied records are caller-provided synthetic values, never authenticated.
PostgreSQL DEFAULT now() records transaction-start time, NOT insert/commit time.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

RACE_RE = re.compile(r"(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
KINDS = frozenset({"official_racelist", "official_beforeinfo"})
MAX_PAGE_BYTES = 2 * 1024 * 1024
BASE = "https://www.boatrace.jp/owpc/pc/race/"


@dataclass(frozen=True, slots=True)
class OriginalFixture:
    resource_key: str
    source_kind: str
    race_id: str
    source_url: str
    request_started_at: datetime
    response_completed_at: datetime
    raw_bytes: bytes
    raw_sha256: str


@dataclass(frozen=True, slots=True)
class DbFirstRowFixture:
    resource_key: str
    source_kind: str
    race_id: str
    source_url: str
    request_started_at: datetime
    response_completed_at: datetime
    raw_bytes: bytes
    raw_sha256: str
    stored_at: datetime | None
    db_transaction_started_at: datetime
    claimed_postcommit_read_at: datetime


@dataclass(frozen=True, slots=True)
class OfflineReadbackVerdict:
    reason_code: str
    synthetic_shape_consistent: bool = False
    first_observed_at: None = field(default=None, init=False)
    first_write_confirmed: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    db_commit_authenticated: bool = field(default=False, init=False)
    db_role_immutability_verified: bool = field(default=False, init=False)


def _aware(t: Any) -> bool:
    return type(t) is datetime and t.tzinfo is not None and t.utcoffset() is not None


def _canonical_identity(source: OriginalFixture) -> bool:
    if (type(source.source_kind) is not str or source.source_kind not in KINDS
            or type(source.race_id) is not str):
        return False
    m = RACE_RE.fullmatch(source.race_id)
    if m is None:
        return False
    day, venue, race_no = m.groups()
    try:
        if datetime.strptime(day, "%Y%m%d").strftime("%Y%m%d") != day:
            return False
    except ValueError:
        return False
    expected_url = (
        f"{BASE}{source.source_kind.removeprefix('official_')}"
        f"?rno={int(race_no)}&jcd={venue}&hd={day}"
    )
    return (
        type(source.resource_key) is str
        and source.resource_key == f"{source.source_kind}:{source.race_id}"
        and type(source.source_url) is str
        and source.source_url == expected_url
    )


def review_offline_first_row_readback(
    original: object, row: object,
) -> OfflineReadbackVerdict:
    """Compare a frozen sample against a mocked row with explicit stored_at.

    Even an exact match is ONLY a mock *shape* match. Caller-supplied row,
    stored_at, transaction start and read-at timestamps cannot prove DB ACL,
    commit completion, independent origin, first sight, or safe Forward.
    """
    def deny(code: str) -> OfflineReadbackVerdict:
        return OfflineReadbackVerdict(code)

    if type(original) is not OriginalFixture or type(row) is not DbFirstRowFixture:
        return deny("ORIGINAL_OR_ROW_MISSING")
    if not _canonical_identity(original):
        return deny("CANONICAL_RESOURCE_IDENTITY_INVALID")
    if (type(original.raw_bytes) is not bytes
            or not 0 < len(original.raw_bytes) <= MAX_PAGE_BYTES
            or type(original.raw_sha256) is not str
            or SHA_RE.fullmatch(original.raw_sha256) is None
            or hashlib.sha256(original.raw_bytes).hexdigest() != original.raw_sha256):
        return deny("ORIGINAL_BYTES_OR_SHA_INVALID")
    if row.stored_at is None:
        return deny("STORED_AT_NOT_READ_BACK")
    if not _aware(row.stored_at):
        return deny("STORED_AT_INVALID")
    if (type(row.raw_bytes) is not bytes
            or row.resource_key != original.resource_key
            or row.source_kind != original.source_kind
            or row.race_id != original.race_id
            or row.source_url != original.source_url
            or row.request_started_at != original.request_started_at
            or row.response_completed_at != original.response_completed_at
            or row.raw_bytes != original.raw_bytes
            or row.raw_sha256 != original.raw_sha256
            or hashlib.sha256(row.raw_bytes).hexdigest() != row.raw_sha256):
        return deny("FIRST_ROW_MISMATCH_OR_MUTATION")
    if not all(_aware(x) for x in (
        original.request_started_at, original.response_completed_at,
        row.db_transaction_started_at, row.claimed_postcommit_read_at,
    )):
        return deny("CLOCK_PROVENANCE_INVALID")
    # This isolated checker models only DEFAULT now(): it equals the start
    # of the DB transaction, but DOES NOT establish insert or commit time.
    if row.stored_at != row.db_transaction_started_at:
        return deny("PG_NOW_TRANSACTION_START_MISMATCH")
    if row.db_transaction_started_at < original.response_completed_at:
        return deny("TX_STARTED_BEFORE_RESPONSE_COMPLETE")
    if not (original.request_started_at <= original.response_completed_at
            <= row.db_transaction_started_at
            <= row.claimed_postcommit_read_at):
        return deny("CLOCK_ORDER_INVALID")
    return OfflineReadbackVerdict("MOCK_ROW_MATCH_NO_INDEPENDENT_PROVENANCE", True)
