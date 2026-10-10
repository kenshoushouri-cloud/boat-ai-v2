# -*- coding: utf-8 -*-
"""Offline V5 paper-shadow six-entrant shape gate; NOT official provenance.

Synthetic JSON bytes test only; real official racelist/beforeinfo pages are
HTML and need a separately validated parser. No HTTP, DB, order, or BUY calls.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit

JST = timezone(timedelta(hours=9))
RACE_RE = re.compile(r'(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z')
SHA_RE = re.compile(r'[0-9a-f]{64}\Z')
CONTRACT = 'V5_SYNTHETIC_PAPER_ROSTER_V1'
MAX_BYTES = 65536


@dataclass(frozen=True, slots=True)
class MockFrozenPage:
    kind: str
    requested_url: str
    final_url: str
    raw_bytes: bytes
    raw_sha256: str
    response_completed_at: datetime
    frozen_at: datetime
    first_observed_at: None = None
    first_write_confirmed: bool = False
    actual_source_authenticated: bool = False
    mutable_or_upsert_only: bool = False
    postrace_derived: bool = False


@dataclass(frozen=True, slots=True)
class PaperRosterVerdict:
    status: str
    reason: str
    race_id: str = ''
    paper_shadow_shape_eligible: bool = False
    matched_mock_lanes: int = 0
    no_economic_odds_evidence: bool = field(default=True, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    no_get_no_db_no_write: bool = field(default=True, init=False)


def _aware(t: object) -> bool:
    return type(t) is datetime and t.tzinfo is not None and t.utcoffset() is not None


def _url_matches(url: object, kind: str, race_id: str) -> bool:
    if type(url) is not str:
        return False
    try:
        u = urlsplit(url)
        if (u.scheme != 'https' or u.netloc != 'www.boatrace.jp'
                or u.path != '/owpc/pc/race/' + kind or u.fragment):
            return False
        p = parse_qsl(u.query, keep_blank_values=True, strict_parsing=True)
        if len(p) != 3 or {k for k, _ in p} != {'rno', 'jcd', 'hd'}:
            return False
        q = dict(p)
        return (q['hd'] == race_id[:8] and q['jcd'] == race_id[9:11]
                and bool(re.fullmatch(r'(?:[1-9]|1[0-2])', q['rno']))
                and int(q['rno']) == int(race_id[-2:]))
    except (ValueError, KeyError, TypeError):
        return False


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key')
        result[k] = v
    return result


def _reject_constant(x: str) -> None:
    raise ValueError('nonfinite JSON constant')


def _entries(page: MockFrozenPage, kind: str, race_id: str):
    """Reparse byte-bound synthetic fixtures; never caller-extracted metadata."""
    try:
        payload = json.loads(page.raw_bytes.decode('utf-8', errors='strict'),
                             object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, TypeError):
        return None, 'SYNTHETIC_ORIGINAL_BYTES_UNPARSEABLE'
    if (type(payload) is not dict
            or set(payload) != {'contract', 'kind', 'race_id', 'entries'}
            or payload['contract'] != CONTRACT or payload['kind'] != kind
            or payload['race_id'] != race_id):
        return None, 'MOCK_SOURCE_CONTRACT_OR_RACE_MISMATCH'
    records = payload['entries']
    if type(records) is not list or len(records) != 6:
        return None, 'MISSING_OR_EXTRA_LANES'
    racers = []
    lanes = []
    for entry in records:
        keys = {'lane', 'racer_number'} | ({'exhibition_time', 'withdrawal'} if kind == 'beforeinfo' else set())
        if (type(entry) is not dict or set(entry) != keys
                or type(entry['lane']) is not int or not 1 <= entry['lane'] <= 6
                or type(entry['racer_number']) is not int
                or not 1 <= entry['racer_number'] <= 9999):
            return None, 'MALFORMED_LANE_OR_RACER'
        lanes.append(entry['lane'])
        racers.append(entry['racer_number'])
        if kind == 'beforeinfo':
            if type(entry['withdrawal']) is not bool:
                return None, 'UNVERIFIED_WITHDRAWAL_FIELD'
            if entry['withdrawal']:
                return None, 'DISPLAYED_WITHDRAWAL_OR_CANCELLATION'
            t = entry['exhibition_time']
            if type(t) not in (int, float) or not math.isfinite(t) or not 0 < t < 60:
                return None, 'INCOMPLETE_EXHIBITION'
    if sorted(lanes) != list(range(1, 7)) or len(set(racers)) != 6:
        return None, 'DUPLICATE_OR_MISSING_LANE_RACER'
    return dict(zip(lanes, racers)), ''


def check_offline_paper_roster(
    *, expected_race_id: object, decision_cutoff_at: object,
    racelist: object, beforeinfo: object, enabled: bool = False,
) -> PaperRosterVerdict:
    """Accept only opted-in synthetic paper-shape parity, NEVER live eligibility."""
    def hold(reason: str) -> PaperRosterVerdict:
        return PaperRosterVerdict('SHADOW_INELIGIBLE_DATA_GAP', reason)

    if enabled is not True:
        return hold('PAPER_SHADOW_OPT_IN_REQUIRED')
    if (type(expected_race_id) is not str or RACE_RE.fullmatch(expected_race_id) is None
            or not _aware(decision_cutoff_at)):
        return hold('RACE_OR_CUTOFF_INVALID')
    try:
        day = datetime.strptime(expected_race_id[:8], '%Y%m%d').date()
    except ValueError:
        return hold('RACE_OR_CUTOFF_INVALID')
    if day < date(2025, 7, 1) or decision_cutoff_at.astimezone(JST).date() != day:
        return hold('RACE_OR_CUTOFF_INVALID')
    if type(racelist) is not MockFrozenPage or type(beforeinfo) is not MockFrozenPage:
        return hold('MISSING_SOURCE_PAGE')
    for page, kind in ((racelist, 'racelist'), (beforeinfo, 'beforeinfo')):
        if (page.kind != kind or page.requested_url != page.final_url
                or not _url_matches(page.requested_url, kind, expected_race_id)):
            return hold('OFFICIAL_URL_SHAPE_OR_RACE_MISMATCH')
        if (page.first_observed_at is not None or page.first_write_confirmed is not False
                or page.actual_source_authenticated is not False
                or page.mutable_or_upsert_only is not False
                or page.postrace_derived is not False):
            return hold('FORGED_AUTHORITY_OR_MUTABLE_HISTORY')
        if (type(page.raw_bytes) is not bytes or not 0 < len(page.raw_bytes) <= MAX_BYTES
                or type(page.raw_sha256) is not str or SHA_RE.fullmatch(page.raw_sha256) is None
                or hashlib.sha256(page.raw_bytes).hexdigest() != page.raw_sha256):
            return hold('RAW_BYTES_OR_SHA256_MISMATCH')
        if (not _aware(page.response_completed_at) or not _aware(page.frozen_at)
                or not page.response_completed_at <= page.frozen_at < decision_cutoff_at
                or page.response_completed_at.astimezone(JST).date() != day):
            return hold('SOURCE_NOT_FROZEN_BEFORE_DECISION_CUTOFF')
    if racelist.response_completed_at > beforeinfo.response_completed_at:
        return hold('RACELIST_OBSERVED_AFTER_BEFOREINFO')
    roster, reason = _entries(racelist, 'racelist', expected_race_id)
    if reason:
        return hold('RACELIST_' + reason)
    exhibition, reason = _entries(beforeinfo, 'beforeinfo', expected_race_id)
    if reason:
        return hold('BEFOREINFO_' + reason)
    if roster != exhibition:
        return hold('SIX_LANE_RACER_IDENTITY_CONFLICT')
    return PaperRosterVerdict('MOCK_PAPER_SHADOW_SHAPE_ONLY_HARD_HOLD',
                              'SIX_LISTED_EXHIBITION_OBSERVED_ONLY',
                              expected_race_id, True, 6)
