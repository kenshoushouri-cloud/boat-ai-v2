# -*- coding: utf-8 -*-
"""Offline race-ID-only join of fake V5 scores and K/as-of coverage reasons.

NEVER score, recompute historical metrics, alter baseline rows, or authorize
selection, first-write, Forward, or BUY. This is not a production scorer.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from v5.offline_asof_eligibility import RACE_RE
from v5.offline_k_asof_batch_integration import KAsOfCoverageReport

MAX_RACES = 500
EXPECTED_REPORT_STATUS = 'OFFLINE_K_ASOF_SYNTHETIC_COUNTS_ALL_HARD_HOLD'
MOCK_JOINT_SHAPE = 'SYNTHETIC_JOINT_SHAPE_HARD_HOLD'
# Accepted denial shapes originate from the offline K/as-of batch adapter.
# Closed statuses from the two existing offline checkers, never caller labels.
K_REASONS = frozenset({
    'RACE_OR_CUTOFF_INVALID', 'RAW_RECEIPT_REQUIRED_LEGACY_CLOCKS_NOT_PROOF',
    'SOURCE_URL_UNVERIFIED', 'ARCHIVE_CALENDAR_INVALID',
    'NOT_FROM_PRIOR_RACE_DAY', 'ORIGINAL_RAW_BYTES_MISSING',
    'FEATURE_SOURCE_KIND_MISMATCH', 'ORIGINAL_LINEAGE_OR_DIGEST_INVALID',
    'UNVERIFIED_CLOCK', 'INVALID_CAPTURE_FREEZE_ORDER',
    'CLAIMED_BEFORE_ARCHIVE_DAY', 'NOT_FROZEN_BEFORE_DECISION_CUTOFF',
    'MUTABLE_OR_POSTRACE_FEATURE', 'INDEPENDENT_MOCK_AUDITOR_MISSING',
    'MOCK_AUDITOR_ANCHOR_MISSING', 'MOCK_WITNESS_INVALID',
})
ASOF_REASONS = frozenset({
    'INVALID_RACE_OR_CUTOFF', 'MISSING_OR_DUPLICATE_FEATURE',
    'NO_INDEPENDENT_MOCK_AUDITOR_ANCHOR',
    'MUTABLE_UNTRUSTED_OR_POSTRACE_FEATURE',
    'FEATURE_SOURCE_KIND_MISMATCH', 'ORIGINAL_LINEAGE_NOT_BOUND',
    'UNVERIFIED_FEATURE_CLOCK', 'INVALID_SOURCE_FREEZE_ORDER',
    'FEATURE_NOT_FROZEN_BEFORE_CUTOFF', 'PRIOR_DAY_K_NOT_PRIOR_DAY',
    'NO_DISTINCT_MOCK_AUDITOR', 'INVALID_MOCK_WITNESS',
})
ALLOWED_REASONS = frozenset({MOCK_JOINT_SHAPE,
    'K_UNEXPECTED_AUTHORITY', 'K_UNRECOGNIZED_VERDICT',
    'K_SNAPSHOT_LINK_MISSING_OR_DUPLICATE', 'K_SNAPSHOT_LINK_MISMATCH',
    'ASOF_UNEXPECTED_AUTHORITY', 'ASOF_UNRECOGNIZED_VERDICT',
}) | frozenset('K_RECEIPT_K_' + x for x in K_REASONS) | frozenset(
    'ASOF_' + x for x in ASOF_REASONS)

AUTHORITY_FLAGS = (
    'original_first_observation_verified', 'independent_source_authenticated',
    'six_active_starts_confirmed', 'selection_eligible',
    'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible',
)


@dataclass(frozen=True, slots=True)
class SyntheticScoredRace:
    race_id: str
    # Payload is intentionally NEVER inspected, rewritten, filtered or copied.
    # Caller owns original immutable/mutable content; this module emits no scores.
    baseline_score_payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class OfflineScoringEvidenceReview:
    status: str
    evaluated_races: int = 0
    mock_joint_shape_races: int = 0
    denied_races: int = 0
    denial_reasons: tuple[tuple[str, int], ...] = ()
    joined_race_reasons: tuple[tuple[str, str], ...] = ()
    # Locked down regardless of result or caller-claimed flags.
    source_authenticated: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _valid_race_id(rid: object) -> bool:
    if type(rid) is not str or RACE_RE.fullmatch(rid) is None:
        return False
    try:
        return datetime.strptime(rid[:8], '%Y%m%d').date() >= date(2025, 7, 1)
    except ValueError:
        return False


def _known_reason(reason: object) -> bool:
    return type(reason) is str and reason in ALLOWED_REASONS


def audit_offline_scoring_evidence(
    score_rows: object, evidence_report: object,
) -> OfflineScoringEvidenceReview:
    """All-or-nothing exact-ID shadow overlay; never an as-of authorization.

    A synthetic positive is only a SHAPE match; all original baseline score
    data and original retrospective cohort are left untouched. Inputs must
    already bear race IDs; no positional, venue or race-day fuzzy matching.
    """
    def deny(reason: str) -> OfflineScoringEvidenceReview:
        return OfflineScoringEvidenceReview(reason)

    if (type(score_rows) not in (tuple, list)
            or not 0 < len(score_rows) <= MAX_RACES
            or any(type(r) is not SyntheticScoredRace
                   or not _valid_race_id(r.race_id)
                   or not isinstance(r.baseline_score_payload, Mapping)
                   or not r.baseline_score_payload for r in score_rows)):
        return deny('INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')
    score_ids = [r.race_id for r in score_rows]
    if len(set(score_ids)) != len(score_ids):
        return deny('DUPLICATE_SCORE_RACE_ID')

    if (type(evidence_report) is not KAsOfCoverageReport
            or evidence_report.status != EXPECTED_REPORT_STATUS
            or any(getattr(evidence_report, key, None) is not False for key in AUTHORITY_FLAGS)
            or type(evidence_report.per_race_reason) is not tuple
            or type(evidence_report.predecision_failure_reasons) is not tuple
            or type(evidence_report.total_races) is not int
            or evidence_report.total_races != len(score_ids)):
        return deny('INVALID_OR_UNTRUSTED_EVIDENCE_REPORT')
    pairs = evidence_report.per_race_reason
    if (len(pairs) != len(score_ids)
            or any(type(x) is not tuple or len(x) != 2
                   or not _valid_race_id(x[0]) or not _known_reason(x[1])
                   for x in pairs)):
        return deny('INVALID_EVIDENCE_RACE_REASON_PAIRS')
    ids = [x[0] for x in pairs]
    if len(set(ids)) != len(ids):
        return deny('DUPLICATE_EVIDENCE_RACE_ID')
    if set(ids) != set(score_ids):
        return deny('MISSING_OR_EXTRA_EVIDENCE_RACE_ID')

    by_id = dict(pairs)
    joined = tuple((rid, by_id[rid]) for rid in score_ids)
    shaped = sum(reason == MOCK_JOINT_SHAPE for _, reason in joined)
    failures = Counter(reason for _, reason in joined if reason != MOCK_JOINT_SHAPE)
    # Refuse a contradictory or tampered summary even when IDs are correct.
    if (type(evidence_report.synthetic_joint_shape_races) is not int
            or evidence_report.synthetic_joint_shape_races != shaped
            or type(evidence_report.synthetic_k_receipt_shape_races) is not int
            or not shaped <= evidence_report.synthetic_k_receipt_shape_races <= len(joined)
            or evidence_report.predecision_failure_reasons != tuple(sorted(failures.items()))):
        return deny('EVIDENCE_AGGREGATES_INCONSISTENT')
    return OfflineScoringEvidenceReview(
        'SYNTHETIC_SCORING_RACE_ID_AUDIT_NO_LIVE_ELIGIBILITY',
        evaluated_races=len(joined), mock_joint_shape_races=shaped,
        denied_races=len(joined) - shaped,
        denial_reasons=tuple(sorted(failures.items())),
        joined_race_reasons=joined,
    )
