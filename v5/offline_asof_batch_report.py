# -*- coding: utf-8 -*-
"""Pure V5 synthetic as-of coverage counts. No real source or live authorization.

Counts mocked predecision feature evidence separately from POSTRACE labels/VOID.
No I/O, no DB imports and no result-based cohort selection or exclusion.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from v5.offline_asof_eligibility import (
    FeatureSnapshot, RetrospectiveOutcome, check_offline_asof_eligibility,
)

MAX_SYNTHETIC_RACES = 500
MOCK_SHAPE_REASON = "SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED"


@dataclass(frozen=True, slots=True)
class SyntheticRaceCase:
    race_id: str
    decision_cutoff_at: datetime
    snapshots: tuple[FeatureSnapshot, ...]
    retrospective_outcome: RetrospectiveOutcome | None = None


@dataclass(frozen=True, slots=True)
class OfflineAsOfBatchReport:
    status: str
    total_races: int = 0
    synthetic_shape_consistent_races: int = 0
    predecision_failure_reasons: tuple[tuple[str, int], ...] = ()
    retrospective_label_claims: int = 0
    retrospective_void_claims: int = 0
    retrospective_nonvoid_claims: int = 0
    retrospective_missing: int = 0
    retrospective_invalid: int = 0
    # Offline fake proofs cannot authorize any V5 action.
    independent_source_authenticated: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def summarize_synthetic_asof_batch(
    races: object, *, trusted_mock_audit_keys: object,
) -> OfflineAsOfBatchReport:
    """Report *mock shape* availability only; never actual eligible race counts.

    Duplicate race IDs invalidate the whole batch, preventing double-counting.
    The outcome is intentionally not passed to the as-of checker and never
    changes the predecision reason or denominator.
    """
    if type(races) not in (tuple, list) or not 0 < len(races) <= MAX_SYNTHETIC_RACES:
        return OfflineAsOfBatchReport("BATCH_INPUT_INVALID")
    if any(type(item) is not SyntheticRaceCase for item in races):
        return OfflineAsOfBatchReport("BATCH_INPUT_INVALID")
    ids = [item.race_id for item in races]
    if any(type(rid) is not str for rid in ids) or len(set(ids)) != len(ids):
        return OfflineAsOfBatchReport("DUPLICATE_OR_INVALID_RACE_ID")

    failures: Counter[str] = Counter()
    shaped = 0
    labelled = voids = nonvoids = missing = invalid = 0
    for race in races:
        verdict = check_offline_asof_eligibility(
            race_id=race.race_id,
            decision_cutoff_at=race.decision_cutoff_at,
            snapshots=race.snapshots,
            trusted_mock_audit_keys=trusted_mock_audit_keys,
            retrospective_outcome=None,  # postrace labels never select cohort
        )
        forbidden = (
            "independent_source_authenticated", "original_first_observation_verified",
            "six_active_starts_confirmed", "selection_eligible",
            "beforeinfo_first_write_eligible", "forward_eligible", "buy_eligible",
        )
        if any(getattr(verdict, flag, None) is not False for flag in forbidden):
            failures["UNEXPECTED_CHECKER_AUTHORITY"] += 1
        elif (verdict.reason == MOCK_SHAPE_REASON
              and verdict.synthetic_asof_shape_consistent is True):
            shaped += 1
        elif (type(verdict.reason) is str and verdict.reason
              and len(verdict.reason) <= 100
              and verdict.synthetic_asof_shape_consistent is False):
            failures[verdict.reason] += 1
        else:
            failures["UNRECOGNIZED_CHECKER_VERDICT"] += 1

        outcome = race.retrospective_outcome
        if outcome is None:
            missing += 1
        elif (type(outcome) is not RetrospectiveOutcome
              or type(outcome.label) is not str or not outcome.label.strip()
              or type(outcome.official_void) is not bool
              or type(outcome.known_at) is not datetime
              or outcome.known_at.tzinfo is None
              or outcome.known_at.utcoffset() is None
              or type(race.decision_cutoff_at) is not datetime
              or race.decision_cutoff_at.tzinfo is None
              or race.decision_cutoff_at.utcoffset() is None
              or outcome.known_at <= race.decision_cutoff_at):
            invalid += 1
        else:
            labelled += 1
            if outcome.official_void:
                voids += 1
            else:
                nonvoids += 1

    return OfflineAsOfBatchReport(
        status="SYNTHETIC_BATCH_COUNTS_NO_LIVE_ELIGIBILITY",
        total_races=len(races),
        synthetic_shape_consistent_races=shaped,
        predecision_failure_reasons=tuple(sorted(failures.items())),
        retrospective_label_claims=labelled,
        retrospective_void_claims=voids,
        retrospective_nonvoid_claims=nonvoids,
        retrospective_missing=missing,
        retrospective_invalid=invalid,
    )
