# -*- coding: utf-8 -*-
"""Fake-only K receipt / seven-feature as-of / retrospective cohort bridge.

A mock K receipt PASS is NOT an authenticated first observation. No I/O, SQL,
real official GET, live selection, first-write, Forward or purchase authority.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from v5.offline_asof_eligibility import FeatureSnapshot, check_offline_asof_eligibility
from v5.offline_asof_batch_report import (
    MAX_SYNTHETIC_RACES, MOCK_SHAPE_REASON, SyntheticRaceCase,
    summarize_synthetic_asof_batch,
)
from v5.offline_prior_day_k_receipt import (
    OfflineKReceipt, check_offline_prior_day_k_receipt,
)

K_MOCK_PASS = 'SYNTHETIC_K_SHAPE_PASS_NO_AUTHENTICATED_FIRST_OBSERVATION'
BATCH_MOCK_PASS = 'SYNTHETIC_BATCH_COUNTS_NO_LIVE_ELIGIBILITY'
FORBIDDEN_ASOF_FLAGS = (
    'independent_source_authenticated', 'original_first_observation_verified',
    'six_active_starts_confirmed', 'selection_eligible',
    'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible',
)
FORBIDDEN_K_FLAGS = (
    'independently_authenticated_source', 'original_first_observation_verified',
    'independently_authenticated_auditor', 'six_active_starts_confirmed',
    'selection_eligible', 'beforeinfo_first_write_eligible',
    'forward_eligible', 'buy_eligible',
)


@dataclass(frozen=True, slots=True)
class KBoundSyntheticRace:
    race: SyntheticRaceCase
    k_receipt: OfflineKReceipt | None = None


@dataclass(frozen=True, slots=True)
class KAsOfCoverageReport:
    status: str
    total_races: int = 0
    synthetic_k_receipt_shape_races: int = 0
    synthetic_joint_shape_races: int = 0
    predecision_failure_reasons: tuple[tuple[str, int], ...] = ()
    per_race_reason: tuple[tuple[str, str], ...] = ()
    retrospective_label_claims: int = 0
    retrospective_void_claims: int = 0
    retrospective_nonvoid_claims: int = 0
    retrospective_missing: int = 0
    retrospective_invalid: int = 0
    original_first_observation_verified: bool = field(default=False, init=False)
    independent_source_authenticated: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _all_denied(value: object, fields: tuple[str, ...]) -> bool:
    return all(getattr(value, name, None) is False for name in fields)


def summarize_offline_k_asof_batch(
    cases: object, *, trusted_mock_audit_keys: object,
) -> KAsOfCoverageReport:
    """One primary failure reason per synthetic race; never postrace-filter.

    The batch adapter deliberately never converts a mock PASS into permission.
    K denial takes priority over otherwise good seven-feature HMAC fixtures.
    K snapshot must equal the exact signed prior_day_k in the seven features.
    """
    if (type(cases) not in (tuple, list)
            or not 0 < len(cases) <= MAX_SYNTHETIC_RACES
            or any(type(item) is not KBoundSyntheticRace
                   or type(item.race) is not SyntheticRaceCase for item in cases)):
        return KAsOfCoverageReport('BATCH_INPUT_INVALID')
    race_ids = [item.race.race_id for item in cases]
    if any(type(x) is not str for x in race_ids) or len(set(race_ids)) != len(race_ids):
        return KAsOfCoverageReport('DUPLICATE_OR_INVALID_RACE_ID')
    baseline = summarize_synthetic_asof_batch(
        [item.race for item in cases],
        trusted_mock_audit_keys=trusted_mock_audit_keys,
    )
    if baseline.status != BATCH_MOCK_PASS or not _all_denied(baseline, FORBIDDEN_ASOF_FLAGS):
        return KAsOfCoverageReport('UNTRUSTED_BATCH_VERDICT_HARD_HOLD')

    failures: Counter[str] = Counter()
    per_race: list[tuple[str, str]] = []
    k_shapes = joint_shapes = 0
    for item in cases:
        race = item.race
        k = check_offline_prior_day_k_receipt(
            race_id=race.race_id, decision_cutoff_at=race.decision_cutoff_at,
            receipt=item.k_receipt, trusted_mock_audit_keys=trusted_mock_audit_keys,
        )
        if not _all_denied(k, FORBIDDEN_K_FLAGS):
            reason = 'K_UNEXPECTED_AUTHORITY'
        elif k.reason != K_MOCK_PASS or k.synthetic_k_receipt_shape_consistent is not True:
            # Only known, non-user-supplied reason tokens may enter reports.
            reason = ('K_RECEIPT_' + k.reason if type(k.reason) is str
                      and k.reason.startswith('K_') and len(k.reason) <= 96
                      else 'K_UNRECOGNIZED_VERDICT')
        else:
            k_shapes += 1
            shots = race.snapshots
            matches = ([s for s in shots if type(s) is FeatureSnapshot
                        and s.feature == 'prior_day_k']
                       if type(shots) in (tuple, list) else [])
            if len(matches) != 1:
                reason = 'K_SNAPSHOT_LINK_MISSING_OR_DUPLICATE'
            elif matches[0] != item.k_receipt.feature_snapshot:
                reason = 'K_SNAPSHOT_LINK_MISMATCH'
            else:
                seven = check_offline_asof_eligibility(
                    race_id=race.race_id,
                    decision_cutoff_at=race.decision_cutoff_at,
                    snapshots=race.snapshots,
                    trusted_mock_audit_keys=trusted_mock_audit_keys,
                    retrospective_outcome=None,
                )
                if not _all_denied(seven, FORBIDDEN_ASOF_FLAGS):
                    reason = 'ASOF_UNEXPECTED_AUTHORITY'
                elif seven.reason == MOCK_SHAPE_REASON and seven.synthetic_asof_shape_consistent is True:
                    reason = 'SYNTHETIC_JOINT_SHAPE_HARD_HOLD'
                    joint_shapes += 1
                elif type(seven.reason) is str and seven.reason.isupper() and len(seven.reason) <= 96:
                    reason = 'ASOF_' + seven.reason
                else:
                    reason = 'ASOF_UNRECOGNIZED_VERDICT'
        if reason != 'SYNTHETIC_JOINT_SHAPE_HARD_HOLD':
            failures[reason] += 1
        per_race.append((race.race_id, reason))

    return KAsOfCoverageReport(
        status='OFFLINE_K_ASOF_SYNTHETIC_COUNTS_ALL_HARD_HOLD',
        total_races=len(cases),
        synthetic_k_receipt_shape_races=k_shapes,
        synthetic_joint_shape_races=joint_shapes,
        predecision_failure_reasons=tuple(sorted(failures.items())),
        per_race_reason=tuple(per_race),
        retrospective_label_claims=baseline.retrospective_label_claims,
        retrospective_void_claims=baseline.retrospective_void_claims,
        retrospective_nonvoid_claims=baseline.retrospective_nonvoid_claims,
        retrospective_missing=baseline.retrospective_missing,
        retrospective_invalid=baseline.retrospective_invalid,
    )
