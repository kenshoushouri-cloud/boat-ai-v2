# -*- coding: utf-8 -*-
"""Offline-only V5 strong-core inference; never an authorization to bet.

The fixed research weights and T=1.00 are used for a six-lane mathematical
shadow prediction. Neither six listed racers nor caller-supplied timestamps
prove six ACTUAL active starts or authenticated predeadline source provenance.
This module has no HTTP, DB, model-selection, odds, staking or BUY actions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from collections.abc import Mapping

from v5.offline_asof_eligibility import JST, RACE_RE

FROZEN_WEIGHTS = (
    ('recent_form', .50),
    ('exhibition_rank', 1.00),
    ('racer_course', .75),
    ('opponent', 1.25),
    ('venue_lane', .75),
)
FROZEN_TEMPERATURE = 1.00
EPS = 1e-12
MAX_FACTOR = 1e6


@dataclass(frozen=True, slots=True)
class OfflineV5InferenceInput:
    race_id: str
    decision_cutoff_at: datetime
    lane_racer_numbers: tuple[int, ...]
    base_probabilities: tuple[float, ...]
    factors: Mapping[str, tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class OfflineV5InferenceVerdict:
    reason: str
    race_id: str = ''
    lane_probabilities: tuple[float, ...] = ()
    synthetic_math_consistent: bool = False
    temperature: float = field(default=FROZEN_TEMPERATURE, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _six_numbers(vector: object, upper: float) -> bool:
    return (type(vector) in (tuple, list)
            and len(vector) == 6
            and all(type(x) in (float, int) and math.isfinite(x)
                    and 0 <= x <= upper for x in vector))


def check_offline_v5_inference(candidate: object) -> OfflineV5InferenceVerdict:
    """Compute fixed math on synthetic six-lane fixtures only, always HARD HOLD.

    This is a probability-of-FIRST-place distribution, not 3連単 ticket ranking.
    No score selection or postrace outcome-based race exclusion is permitted.
    """
    def deny(reason: str) -> OfflineV5InferenceVerdict:
        return OfflineV5InferenceVerdict(reason)

    if type(candidate) is not OfflineV5InferenceInput:
        return deny('INVALID_SYNTHETIC_INPUT')
    rid, cutoff = candidate.race_id, candidate.decision_cutoff_at
    if (type(rid) is not str or RACE_RE.fullmatch(rid) is None
            or type(cutoff) is not datetime or cutoff.tzinfo is None
            or cutoff.utcoffset() is None):
        return deny('RACE_ID_OR_CUTOFF_INVALID')
    try:
        race_date = datetime.strptime(rid[:8], '%Y%m%d').date()
    except ValueError:
        return deny('RACE_ID_OR_CUTOFF_INVALID')
    if race_date < date(2025, 7, 1) or cutoff.astimezone(JST).date() != race_date:
        return deny('RACE_ID_OR_CUTOFF_INVALID')

    racers = candidate.lane_racer_numbers
    if (type(racers) is not tuple or len(racers) != 6
            or any(type(n) is not int or not 1 <= n <= 9999 for n in racers)
            or len(set(racers)) != 6):
        return deny('SIX_LANE_RACER_SHAPE_INVALID')
    base = candidate.base_probabilities
    if not _six_numbers(base, 1.):
        return deny('BASE_SIX_PROBABILITIES_INVALID')
    if not math.isclose(sum(base), 1., rel_tol=0., abs_tol=1e-9):
        return deny('BASE_NOT_NORMALIZED')

    factors = candidate.factors
    if not isinstance(factors, Mapping) or set(factors) != {key for key, _ in FROZEN_WEIGHTS}:
        return deny('FIVE_FACTOR_SCHEMA_INVALID')
    if any(not _six_numbers(factors[k], MAX_FACTOR) for k, _ in FROZEN_WEIGHTS):
        return deny('FIVE_FACTOR_VALUES_INVALID')
    try:
        raw = []
        for i in range(6):
            x = max(base[i], EPS)
            for feature, weight in FROZEN_WEIGHTS:
                x *= max(factors[feature][i], EPS) ** weight
            raw.append(max(x, EPS))
        denom = sum(raw)
        probs = [x / denom for x in raw]
        # Same frozen 1.00 temperature transform as strong-core calibration.
        transformed = [max(p, EPS) ** (1. / FROZEN_TEMPERATURE) for p in probs]
        z = sum(transformed)
        result = tuple(p / z for p in transformed)
    except (OverflowError, ValueError, ZeroDivisionError, TypeError):
        return deny('CORE_NUMERICAL_FAILURE')
    if not all(math.isfinite(p) and p > 0 for p in result):
        return deny('CORE_NUMERICAL_FAILURE')
    return OfflineV5InferenceVerdict(
        'SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD',
        race_id=rid, lane_probabilities=result, synthetic_math_consistent=True,
    )
