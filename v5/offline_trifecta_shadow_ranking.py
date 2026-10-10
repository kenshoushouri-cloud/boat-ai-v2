# -*- coding: utf-8 -*-
"""V5 first-place probability -> 3-ren-tan PL shadow ranking, offline ONLY.

The Plackett-Luce 2nd/3rd model is a research ASSUMPTION, not measured
trifecta accuracy, live candidate selection or a purchasing authorization.
No odds, EV, result, stake, account, network, or persistence is accessed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import permutations

from v5.offline_asof_eligibility import RACE_RE
from v5.offline_mainline_inference import OfflineV5InferenceVerdict

EPS = 1e-12
EXPECTED_INFERENCE_REASON = 'SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD'
AUTHORITY = (
    'independently_authenticated_source', 'original_first_observation_verified',
    'six_active_starts_confirmed', 'selection_eligible',
    'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible',
)


@dataclass(frozen=True, slots=True)
class OfflineTrifectaShadowRanking:
    reason: str
    race_id: str = ''
    requested_ticket_count: int = 0
    # Complete 120-ticket normalized distribution, lexical ticket order.
    ticket_distribution: tuple[tuple[str, float], ...] = ()
    # Separately ranked by probability descending, then ticket name ascending.
    top_tickets: tuple[tuple[str, float], ...] = ()
    synthetic_math_consistent: bool = False
    second_third_pl_assumption_unvalidated: bool = field(default=True, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def rank_offline_v5_trifectas(inference: object, *, ticket_count: object) -> OfflineTrifectaShadowRanking:
    """Research-only 120 ticket PL expansion; NEVER predecision BUY evidence.

    Ticket_count is mandatory and has NO hidden V4 TOP2 or TOP6 default.
    Inference must be the synthetic V5 output, with all authority flags FALSE.
    The result is not a 3-ren-tan prediction calibrated on historical tickets.
    """
    def deny(reason: str) -> OfflineTrifectaShadowRanking:
        return OfflineTrifectaShadowRanking(reason)

    if type(ticket_count) is not int or not 1 <= ticket_count <= 120:
        return deny('EXPLICIT_TICKET_COUNT_REQUIRED')
    if (type(inference) is not OfflineV5InferenceVerdict
            or inference.reason != EXPECTED_INFERENCE_REASON
            or inference.synthetic_math_consistent is not True
            or any(getattr(inference, name, None) is not False for name in AUTHORITY)):
        return deny('UNTRUSTED_OR_UNAUTHORIZED_V5_INFERENCE')
    rid = inference.race_id
    if type(rid) is not str or RACE_RE.fullmatch(rid) is None:
        return deny('INVALID_SOURCE_RACE_ID')
    try:
        race_day = datetime.strptime(rid[:8], '%Y%m%d').date()
    except ValueError:
        return deny('INVALID_SOURCE_RACE_ID')
    if race_day < date(2025, 7, 1):
        return deny('INVALID_SOURCE_RACE_ID')
    probs = inference.lane_probabilities
    if (type(probs) is not tuple or len(probs) != 6
            or any(type(p) not in (int, float) or not math.isfinite(p)
                   or not 0 < p < 1 for p in probs)
            or not math.isclose(math.fsum(probs), 1., rel_tol=0., abs_tol=1e-9)):
        return deny('INVALID_SIX_LANE_PROBABILITY_VECTOR')

    # Same PL formula as research/candidate_discovery_v4_contract.py, but NO
    # inheritance of the V4 6-race/day or two-ticket policy.
    raw = {}
    for a, b, c in permutations(range(1, 7), 3):
        pa, pb, pc = probs[a-1], probs[b-1], probs[c-1]
        rem_b = 1. - pa
        rem_c = rem_b - pb
        if not math.isfinite(rem_c) or rem_b <= 0 or rem_c <= 0:
            return deny('PL_NUMERICAL_FAILURE')
        mass = pa * (pb / rem_b) * (pc / rem_c)
        if not math.isfinite(mass):
            return deny('PL_NUMERICAL_FAILURE')
        raw[f'{a}-{b}-{c}'] = max(EPS, mass)
    if len(raw) != 120:
        return deny('INCOMPLETE_TRIFECTA_DISTRIBUTION')
    total = math.fsum(raw.values())
    if not math.isfinite(total) or total <= 0:
        return deny('PL_NUMERICAL_FAILURE')
    normalized = {ticket: mass / total for ticket, mass in raw.items()}
    if (any(not math.isfinite(p) or p <= 0 for p in normalized.values())
            or not math.isclose(math.fsum(normalized.values()), 1., abs_tol=1e-12)):
        return deny('PL_NUMERICAL_FAILURE')
    ranked = tuple(sorted(normalized.items(), key=lambda x: (-x[1], x[0])))
    return OfflineTrifectaShadowRanking(
        'SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD',
        rid, ticket_count, tuple(sorted(normalized.items())),
        ranked[:ticket_count], True,
    )
