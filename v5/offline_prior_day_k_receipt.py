"""Offline V5 prior-day K receipt shape; NEVER a live decision permission.

Synthetic HMAC and caller clocks are not independently authenticated evidence.
No actual K downloads, DB writes, publication proof, Forward, or BUY.
"""
from __future__ import annotations
import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, date
from urllib.parse import urlsplit
from v5.offline_asof_eligibility import FeatureSnapshot, JST, RACE_RE, SHA_RE, _aware, _witness_payload

K_PATH = re.compile(r'/od2/K/(20\d{4})/k(\d{6})\.lzh\Z')

@dataclass(frozen=True)
class OfflineKReceipt:
    source_url: str
    original_raw_bytes: bytes
    request_started_at: datetime
    response_completed_at: datetime
    feature_snapshot: FeatureSnapshot

@dataclass(frozen=True)
class OfflineKReceiptVerdict:
    reason: str
    synthetic_k_receipt_shape_consistent: bool = False
    original_first_observation_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    independently_authenticated_auditor: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)

def check_offline_prior_day_k_receipt(*, race_id, decision_cutoff_at, receipt,
                                     trusted_mock_audit_keys, legacy_result_row=None):
    def deny(reason):
        return OfflineKReceiptVerdict(reason)
    if type(race_id) is not str or not RACE_RE.fullmatch(race_id) or not _aware(decision_cutoff_at):
        return deny('K_RACE_OR_CUTOFF_INVALID')
    try:
        race_day = datetime.strptime(race_id[:8], '%Y%m%d').date()
    except ValueError:
        return deny('K_RACE_OR_CUTOFF_INVALID')
    if race_day < date(2025, 7, 1) or decision_cutoff_at.astimezone(JST).date() != race_day:
        return deny('K_RACE_OR_CUTOFF_INVALID')
    # A mutable fetched_at/updated_at result row is NEVER substitute proof.
    if type(receipt) is not OfflineKReceipt:
        return deny('K_RAW_RECEIPT_REQUIRED_LEGACY_CLOCKS_NOT_PROOF')
    try:
        u = urlsplit(receipt.source_url) if type(receipt.source_url) is str else None
        if not u or u.scheme != 'https' or u.netloc != 'www1.mbrace.or.jp' or u.query or u.fragment:
            return deny('K_SOURCE_URL_UNVERIFIED')
    except ValueError:
        return deny('K_SOURCE_URL_UNVERIFIED')
    m = K_PATH.fullmatch(u.path)
    if m is None:
        return deny('K_SOURCE_URL_UNVERIFIED')
    try:
        archive_day = datetime.strptime('20' + m[2], '%Y%m%d').date()
    except ValueError:
        return deny('K_ARCHIVE_CALENDAR_INVALID')
    if archive_day.strftime('%Y%m') != m[1]:
        return deny('K_ARCHIVE_CALENDAR_INVALID')
    if archive_day >= race_day:
        return deny('K_NOT_FROM_PRIOR_RACE_DAY')
    if type(receipt.original_raw_bytes) is not bytes or not 0 < len(receipt.original_raw_bytes) <= 2097152:
        return deny('K_ORIGINAL_RAW_BYTES_MISSING')
    s = receipt.feature_snapshot
    if type(s) is not FeatureSnapshot or s.feature != 'prior_day_k' or s.source_mode != 'immutable_prior_day_k':
        return deny('K_FEATURE_SOURCE_KIND_MISMATCH')
    if (s.original_ref != 'official_k_file:' + m[2] or type(s.original_sha256) is not str
            or not SHA_RE.fullmatch(s.original_sha256)
            or not hmac.compare_digest(s.original_sha256, hashlib.sha256(receipt.original_raw_bytes).hexdigest())):
        return deny('K_ORIGINAL_LINEAGE_OR_DIGEST_INVALID')
    times = (receipt.request_started_at, receipt.response_completed_at, s.source_observed_at,
             s.original_frozen_at, s.feature_observed_at, s.audited_at)
    if not all(_aware(t) for t in times):
        return deny('K_UNVERIFIED_CLOCK')
    if tuple(sorted(times)) != times:
        return deny('K_INVALID_CAPTURE_FREEZE_ORDER')
    if s.source_observed_at.astimezone(JST).date() < archive_day:
        return deny('K_CLAIMED_BEFORE_ARCHIVE_DAY')
    if any(t >= decision_cutoff_at for t in times):
        return deny('K_NOT_FROZEN_BEFORE_DECISION_CUTOFF')
    if (type(s.mutable_or_upsert_only) is not bool or s.mutable_or_upsert_only
            or type(s.postrace_derived) is not bool or s.postrace_derived):
        return deny('K_MUTABLE_OR_POSTRACE_FEATURE')
    if (type(s.collector_id) is not str or not s.collector_id.strip()
            or type(s.auditor_id) is not str or not s.auditor_id.strip() or s.collector_id == s.auditor_id):
        return deny('K_INDEPENDENT_MOCK_AUDITOR_MISSING')
    if (not isinstance(trusted_mock_audit_keys, Mapping)
            or type(trusted_mock_audit_keys.get(s.auditor_id)) is not bytes
            or len(trusted_mock_audit_keys[s.auditor_id]) < 32):
        return deny('K_MOCK_AUDITOR_ANCHOR_MISSING')
    if type(s.witness_hmac) is not str or not SHA_RE.fullmatch(s.witness_hmac):
        return deny('K_MOCK_WITNESS_INVALID')
    sig = hmac.new(trusted_mock_audit_keys[s.auditor_id],
                   _witness_payload(race_id, decision_cutoff_at, s), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(s.witness_hmac, sig):
        return deny('K_MOCK_WITNESS_INVALID')
    return OfflineKReceiptVerdict('SYNTHETIC_K_SHAPE_PASS_NO_AUTHENTICATED_FIRST_OBSERVATION', True)
