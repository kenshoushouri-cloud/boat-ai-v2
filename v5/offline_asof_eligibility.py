# -*- coding: utf-8 -*-
"""Pure V5 mock as-of audit. No DB/network and NEVER a Forward/BUY permission.

A test HMAC verifies only that a test witness matches a supplied trust key.
It cannot authenticate the original official source, DB owner, first sight,
commit time, race-day active starters, or actual predecision availability.
Trusted key configuration MUST be independently controlled outside a record.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RACE_RE = re.compile(r"(20\d{6})_(0[1-9]|1\d|2[0-4])_(0[1-9]|1[0-2])\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_FEATURES = frozenset({
    "lane_class", "recent_form", "exhibition_rank", "racer_course",
    "opponent", "venue_lane", "prior_day_k",
})
ALLOWED_SOURCES = frozenset({
    "immutable_original_capture", "immutable_derived_snapshot", "immutable_prior_day_k",
})


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    feature: str
    source_mode: str
    original_ref: str
    original_sha256: str
    source_observed_at: datetime
    original_frozen_at: datetime
    feature_observed_at: datetime
    audited_at: datetime
    collector_id: str
    auditor_id: str
    witness_hmac: str
    mutable_or_upsert_only: bool = False
    postrace_derived: bool = False


@dataclass(frozen=True, slots=True)
class RetrospectiveOutcome:
    """Postrace label/incident/VOID metadata; never part of eligibility."""
    label: str
    official_void: bool
    known_at: datetime


@dataclass(frozen=True, slots=True)
class AsOfMockVerdict:
    reason: str
    synthetic_asof_shape_consistent: bool = False
    retrospective_outcome_supplied: bool = False
    # These are deliberately impossible to promote using mock-only evidence.
    original_first_observation_verified: bool = field(default=False, init=False)
    independent_source_authenticated: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(t: object) -> bool:
    return type(t) is datetime and t.tzinfo is not None and t.utcoffset() is not None


def _witness_payload(race_id: str, cutoff: datetime, s: FeatureSnapshot) -> bytes:
    """Deterministic test witness bound to source, times, race and cutoff."""
    to_utc = lambda t: t.astimezone(timezone.utc).isoformat()
    fields = [
        "V5_OFFLINE_ASOF_MOCK_V1", race_id, to_utc(cutoff), s.feature,
        s.source_mode, s.original_ref, s.original_sha256,
        to_utc(s.source_observed_at), to_utc(s.original_frozen_at),
        to_utc(s.feature_observed_at), to_utc(s.audited_at),
        s.collector_id, s.auditor_id, s.mutable_or_upsert_only,
        s.postrace_derived,
    ]
    return json.dumps(fields, separators=(",", ":")).encode("ascii")


def check_offline_asof_eligibility(
    *, race_id: object, decision_cutoff_at: object,
    snapshots: object, trusted_mock_audit_keys: object,
    retrospective_outcome: object = None,
) -> AsOfMockVerdict:
    """Check fixed fake evidence only; structural PASS is NOT live eligibility.

    Caller-controlled witness keys are not independently authoritative: a
    positive mock result remains HARD HOLD by construction.
    """
    outcome_flag = type(retrospective_outcome) is RetrospectiveOutcome

    def deny(reason: str) -> AsOfMockVerdict:
        return AsOfMockVerdict(reason, retrospective_outcome_supplied=outcome_flag)

    if type(race_id) is not str or not RACE_RE.fullmatch(race_id) or not _aware(decision_cutoff_at):
        return deny("INVALID_RACE_OR_CUTOFF")
    try:
        day = datetime.strptime(race_id[:8], "%Y%m%d").date()
    except ValueError:
        return deny("INVALID_RACE_OR_CUTOFF")
    if day < date(2025, 7, 1) or decision_cutoff_at.astimezone(JST).date() != day:
        return deny("INVALID_RACE_OR_CUTOFF")
    if type(snapshots) not in (tuple, list) or len(snapshots) != len(REQUIRED_FEATURES):
        return deny("MISSING_OR_DUPLICATE_FEATURE")
    if any(type(s) is not FeatureSnapshot for s in snapshots):
        return deny("MISSING_OR_DUPLICATE_FEATURE")
    if {s.feature for s in snapshots} != REQUIRED_FEATURES:
        return deny("MISSING_OR_DUPLICATE_FEATURE")
    if not isinstance(trusted_mock_audit_keys, Mapping) or not trusted_mock_audit_keys:
        return deny("NO_INDEPENDENT_MOCK_AUDITOR_ANCHOR")

    for s in snapshots:
        if (s.source_mode not in ALLOWED_SOURCES
                or type(s.mutable_or_upsert_only) is not bool
                or s.mutable_or_upsert_only
                or type(s.postrace_derived) is not bool
                or s.postrace_derived):
            return deny("MUTABLE_UNTRUSTED_OR_POSTRACE_FEATURE")
        if (s.feature == "prior_day_k") != (s.source_mode == "immutable_prior_day_k"):
            return deny("FEATURE_SOURCE_KIND_MISMATCH")
        if (type(s.original_ref) is not str or not s.original_ref.strip()
                or len(s.original_ref) > 256
                or type(s.original_sha256) is not str
                or not SHA_RE.fullmatch(s.original_sha256)):
            return deny("ORIGINAL_LINEAGE_NOT_BOUND")
        if not all(_aware(t) for t in (
            s.source_observed_at, s.original_frozen_at,
            s.feature_observed_at, s.audited_at,
        )):
            return deny("UNVERIFIED_FEATURE_CLOCK")
        if not (s.source_observed_at <= s.original_frozen_at
                <= s.feature_observed_at <= s.audited_at):
            return deny("INVALID_SOURCE_FREEZE_ORDER")
        if not (s.source_observed_at < decision_cutoff_at
                and s.original_frozen_at < decision_cutoff_at
                and s.feature_observed_at < decision_cutoff_at
                and s.audited_at < decision_cutoff_at):
            return deny("FEATURE_NOT_FROZEN_BEFORE_CUTOFF")
        if (s.feature == "prior_day_k"
                and s.source_observed_at.astimezone(JST).date() >= day):
            return deny("PRIOR_DAY_K_NOT_PRIOR_DAY")
        if (type(s.collector_id) is not str or not s.collector_id.strip()
                or type(s.auditor_id) is not str or not s.auditor_id.strip()
                or s.collector_id == s.auditor_id):
            return deny("NO_DISTINCT_MOCK_AUDITOR")
        key = trusted_mock_audit_keys.get(s.auditor_id)
        if type(key) is not bytes or len(key) < 32:
            return deny("NO_INDEPENDENT_MOCK_AUDITOR_ANCHOR")
        if type(s.witness_hmac) is not str or not SHA_RE.fullmatch(s.witness_hmac):
            return deny("INVALID_MOCK_WITNESS")
        expected = hmac.new(key, _witness_payload(race_id, decision_cutoff_at, s), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(s.witness_hmac, expected):
            return deny("INVALID_MOCK_WITNESS")

    return AsOfMockVerdict(
        "SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED",
        synthetic_asof_shape_consistent=True,
        retrospective_outcome_supplied=outcome_flag,
    )
