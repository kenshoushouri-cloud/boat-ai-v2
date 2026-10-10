# -*- coding: utf-8 -*-
"""Fake-only odds first-observation shape checks; never authenticate real odds.

A mutable historical snapshot or caller-asserted receipt cannot prove that
specific odds were visible before a real race's purchase deadline. No IO/BUY.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlsplit

JST = timezone(timedelta(hours=9))
RACE_RE = re.compile(r'(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z')
TICKET_RE = re.compile(r'([1-6])-([1-6])-([1-6])\Z')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')
MAX_BYTES = 2_097_152


@dataclass(frozen=True, slots=True)
class LegacyOddsSnapshot:
    race_id: str
    ticket: str
    odds: float
    snapshot_label: str
    snapshot_at: datetime
    source: str
    raw: object
    write_mode: str  # Existing actual pipeline uses mutable UPSERT.


@dataclass(frozen=True, slots=True)
class MockImmutableOddsReceipt:
    race_id: str
    ticket: str
    cutoff_at: datetime
    official_url: str
    original_bytes: bytes
    original_sha256: str
    published_at: datetime
    first_observed_at: datetime
    committed_at: datetime
    readback_at: datetime
    readback_sha256: str
    independent_owner_receipt_ref: str


@dataclass(frozen=True, slots=True)
class OfflineOddsProvenanceVerdict:
    reason: str
    mock_original_receipt_shape_consistent: bool = False
    # Even passing mock receipts do NOT authenticate the publisher or DB owner.
    parsed_odds_bound_to_original_bytes: bool = field(default=False, init=False)
    official_publisher_verified: bool = field(default=False, init=False)
    immutable_first_observation_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    real_predeadline_odds_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _official_url(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and u.netloc == 'www.boatrace.jp'
                and u.path.startswith('/owpc/pc/race/odds3t')
                and not u.username and not u.password and not u.fragment)
    except ValueError:
        return False


def classify_offline_odds_source(
    snapshot: object, *, receipt: object = None,
) -> OfflineOddsProvenanceVerdict:
    """Fail closed on legacy update/fallback/empty raw and timing/source gaps.

    A mock-shape PASS is always hard HOLD: no network, DB attestation, actual
    first-write witness or independent raw HTML odds parser is used.
    """
    def hold(reason: str) -> OfflineOddsProvenanceVerdict:
        return OfflineOddsProvenanceVerdict(reason)

    if type(snapshot) is not LegacyOddsSnapshot:
        return hold('ODDS_SNAPSHOT_INVALID')
    rid, ticket = snapshot.race_id, snapshot.ticket
    m = RACE_RE.fullmatch(rid) if type(rid) is str else None
    n = TICKET_RE.fullmatch(ticket) if type(ticket) is str else None
    if m is None or n is None or len(set(n.groups())) != 3:
        return hold('RACE_OR_TICKET_INVALID')
    try:
        race_day = datetime.strptime(m[1], '%Y%m%d').date()
    except ValueError:
        return hold('RACE_OR_TICKET_INVALID')
    if race_day < date(2025, 7, 1):
        return hold('RACE_OR_TICKET_INVALID')
    if (type(snapshot.odds) not in (int, float) or not math.isfinite(snapshot.odds)
            or snapshot.odds <= 0 or type(snapshot.snapshot_label) is not str
            or not snapshot.snapshot_label.strip() or not _aware(snapshot.snapshot_at)):
        return hold('ODDS_OR_SNAPSHOT_CLOCK_INVALID')
    if snapshot.snapshot_at.astimezone(JST).date() != race_day:
        return hold('ODDS_OR_SNAPSHOT_CLOCK_INVALID')
    if snapshot.source != 'OFFICIAL_HTTP_DIRECT':
        return hold('FALLBACK_OR_UNVERIFIED_ODDS_SOURCE')
    if snapshot.write_mode != 'IMMUTABLE_FIRST_WRITE':
        return hold('MUTABLE_UPSERT_NOT_ORIGINAL_FIRST_WRITE')
    # Live v21 collector raw={} cannot become original evidence through a label.
    if (type(snapshot.raw) is not dict or set(snapshot.raw) !=
            {'race_id', 'ticket', 'odds', 'original_sha256'}):
        return hold('EMPTY_OR_UNBOUND_SNAPSHOT_RAW')
    if (snapshot.raw['race_id'] != rid or snapshot.raw['ticket'] != ticket
            or type(snapshot.raw['odds']) not in (int, float)
            or snapshot.raw['odds'] != snapshot.odds):
        return hold('SNAPSHOT_RAW_VALUE_MISMATCH')
    if type(receipt) is not MockImmutableOddsReceipt:
        return hold('MISSING_INDEPENDENT_ORIGINAL_RECEIPT')
    if (receipt.race_id != rid or receipt.ticket != ticket
            or not _official_url(receipt.official_url)):
        return hold('RECEIPT_SOURCE_OR_IDENTITY_MISMATCH')
    if (type(receipt.original_bytes) is not bytes
            or not 0 < len(receipt.original_bytes) <= MAX_BYTES
            or type(receipt.original_sha256) is not str
            or SHA_RE.fullmatch(receipt.original_sha256) is None
            or hashlib.sha256(receipt.original_bytes).hexdigest() != receipt.original_sha256
            or snapshot.raw['original_sha256'] != receipt.original_sha256
            or type(receipt.readback_sha256) is not str
            or receipt.readback_sha256 != receipt.original_sha256):
        return hold('ORIGINAL_RAW_OR_READBACK_SHA_MISMATCH')
    if (not all(_aware(t) for t in (receipt.published_at,
                                   receipt.first_observed_at,
                                   receipt.committed_at, receipt.readback_at,
                                   receipt.cutoff_at))
            or not (receipt.published_at <= receipt.first_observed_at
                    <= snapshot.snapshot_at <= receipt.committed_at
                    <= receipt.readback_at < receipt.cutoff_at)
            or receipt.cutoff_at.astimezone(JST).date() != race_day):
        return hold('UNVERIFIED_FIRST_SEEN_PUBLICATION_OR_CUTOFF_ORDER')
    if (type(receipt.independent_owner_receipt_ref) is not str
            or not receipt.independent_owner_receipt_ref.strip()):
        return hold('INDEPENDENT_OWNER_RECEIPT_MISSING')
    return OfflineOddsProvenanceVerdict('MOCK_ORIGINAL_ODDS_SHAPE_ONLY_HARD_HOLD', True)
