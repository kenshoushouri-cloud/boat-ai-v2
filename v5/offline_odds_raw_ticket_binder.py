# -*- coding: utf-8 -*-
"""Offline-only V5 3-ren-tan raw HTML -> ticket/odds parity binder.

Never certifies a real HTTP request, publisher, first-observed timestamp,
immutability, six-active-starts, Forward or BUY. No I/O or external services.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlsplit

from official_odds3t_parser import CANONICAL_SET, parse_official_odds3t

JST = timezone(timedelta(hours=9))
RACE_RE = re.compile(r'(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')
EXPLICIT_TICKET_RE = re.compile(r'(?<!\d)([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+(?:\d+(?:\.\d+)?)')
MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MockRawOddsCapture:
    source: str
    requested_url: str
    final_url: str
    http_status: int
    raw_bytes: bytes
    raw_sha256: str
    readback_sha256: str
    request_started_at: datetime
    response_completed_at: datetime
    first_observed_at: datetime
    committed_at: datetime
    readback_at: datetime
    cutoff_at: datetime
    receipt_ref: str
    write_mode: str
    odds_selection_source: str


@dataclass(frozen=True, slots=True)
class OfflineOddsTicketParityVerdict:
    reason: str
    race_id: str = ''
    mock_raw_ticket_parity: bool = False
    checked_ticket_count: int = 0
    original_official_http_verified: bool = field(default=False, init=False)
    independently_authenticated_receipt: bool = field(default=False, init=False)
    real_first_observed_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(t: object) -> bool:
    return type(t) is datetime and t.tzinfo is not None and t.utcoffset() is not None


def _strict_url_race_id(url: object) -> str | None:
    if type(url) is not str:
        return None
    try:
        u = urlsplit(url)
        if (u.scheme != 'https' or u.netloc != 'www.boatrace.jp'
                or u.path != '/owpc/pc/race/odds3t' or u.fragment):
            return None
        params = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
        if len(params) != 3 or set(k for k, _ in params) != {'rno', 'jcd', 'hd'}:
            return None
        q = dict(params)
        if not (re.fullmatch(r'(?:[1-9]|1[0-2])', q['rno'])
                and re.fullmatch(r'(?:0[1-9]|1\d|2[0-4])', q['jcd'])
                and re.fullmatch(r'20\d{6}', q['hd'])):
            return None
        d = datetime.strptime(q['hd'], '%Y%m%d').date()
        if d < date(2025, 7, 1):
            return None
        return f"{q['hd']}_{q['jcd']}_{int(q['rno']):02d}"
    except (ValueError, KeyError, TypeError):
        return None


def bind_offline_odds_raw_tickets(
    expected_race_id: object,
    capture: object,
    claimed_ticket_odds: object,
) -> OfflineOddsTicketParityVerdict:
    """Reparse exactly the digest-bound original raw bytes, never a fallback.

    A passing *fictional* receipt proves only local shape/parity, NOT that the
    bytes came from the URL or were witnessed before the deadline.
    """
    def deny(reason: str) -> OfflineOddsTicketParityVerdict:
        return OfflineOddsTicketParityVerdict(reason)

    if type(expected_race_id) is not str or RACE_RE.fullmatch(expected_race_id) is None:
        return deny('EXPECTED_RACE_ID_INVALID')
    try:
        race_day = datetime.strptime(expected_race_id[:8], '%Y%m%d').date()
    except ValueError:
        return deny('EXPECTED_RACE_ID_INVALID')
    if race_day < date(2025, 7, 1):
        return deny('EXPECTED_RACE_ID_INVALID')
    if type(capture) is not MockRawOddsCapture:
        return deny('ORIGINAL_RECEIPT_SHAPE_MISSING')
    url_race = _strict_url_race_id(capture.requested_url)
    if url_race != expected_race_id or capture.final_url != capture.requested_url:
        return deny('OFFICIAL_ODDS_URL_RACE_ID_MISMATCH')
    if (capture.source != 'official_odds3t' or capture.odds_selection_source != 'official_odds3t'
            or capture.http_status != 200 or type(capture.http_status) is not int):
        return deny('UNVERIFIED_OR_FALLBACK_SOURCE')
    if capture.write_mode != 'IMMUTABLE_FIRST_WRITE' or not (type(capture.receipt_ref) is str and capture.receipt_ref.strip()):
        return deny('ORIGINAL_FIRST_WRITE_RECEIPT_MISSING')
    if (type(capture.raw_bytes) is not bytes or not 0 < len(capture.raw_bytes) <= MAX_BYTES
            or type(capture.raw_sha256) is not str
            or SHA_RE.fullmatch(capture.raw_sha256) is None
            or type(capture.readback_sha256) is not str
            or capture.readback_sha256 != capture.raw_sha256
            or hashlib.sha256(capture.raw_bytes).hexdigest() != capture.raw_sha256):
        return deny('RAW_OR_READBACK_SHA256_MISMATCH')
    clocks = (capture.request_started_at, capture.response_completed_at,
              capture.first_observed_at, capture.committed_at, capture.readback_at,
              capture.cutoff_at)
    if (not all(_aware(x) for x in clocks)
            or not (capture.request_started_at <= capture.response_completed_at
                    == capture.first_observed_at <= capture.committed_at
                    <= capture.readback_at < capture.cutoff_at)
            or capture.cutoff_at.astimezone(JST).date() != race_day
            or capture.response_completed_at.astimezone(JST).date() != race_day):
        return deny('UNPROVEN_PREDEADLINE_FIRST_OBSERVATION_CLOCK')
    if (not isinstance(claimed_ticket_odds, Mapping)
            or len(claimed_ticket_odds) != 120
            or set(claimed_ticket_odds) != CANONICAL_SET
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                   for v in claimed_ticket_odds.values())):
        return deny('INVALID_OR_INCOMPLETE_CLAIMED_TICKET_SET')
    try:
        original_html = capture.raw_bytes.decode('utf-8', errors='strict')
    except UnicodeError:
        return deny('ORIGINAL_HTML_DECODE_FAILED')
    # The original parser's legacy text path overwrites duplicates. Reject
    # ambiguous explicit duplicate ticket quotations before parsing the bytes.
    seen = [f'{a}-{b}-{c}' for a,b,c in EXPLICIT_TICKET_RE.findall(original_html)]
    if len(seen) != len(set(seen)):
        return deny('AMBIGUOUS_DUPLICATE_TICKET_IN_ORIGINAL')
    parsed = parse_official_odds3t(original_html)
    if not (type(parsed) is dict and len(parsed) == 120 and set(parsed) == CANONICAL_SET):
        return deny('PARTIAL_OR_UNPARSEABLE_ORIGINAL_ODDS')
    if any(parsed[t] != claimed_ticket_odds[t] for t in CANONICAL_SET):
        return deny('CLAIMED_ODDS_DO_NOT_MATCH_ORIGINAL')
    return OfflineOddsTicketParityVerdict(
        'MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD', expected_race_id, True, 120,
    )
