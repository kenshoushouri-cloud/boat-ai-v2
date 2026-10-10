"""V5 mainline: one offline race-day path from frozen score inputs to cash shapes.

Never observes official websites, accesses DB/LINE, makes a wager, verifies
source provenance or authorizes Forward/BUY. All results are synthetic-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from v5.offline_mainline_inference import (
    OfflineV5InferenceInput, check_offline_v5_inference,
)
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas
from v5.offline_trifecta_cash_ledger import (
    MAX_RACES, PredeadlineMockRace, PostraceMockResult,
)
from v5.offline_trifecta_cash_bridge import audit_offline_shadow_cash_bridge


@dataclass(frozen=True, slots=True)
class OfflineV5DayInput:
    candidates: tuple[OfflineV5InferenceInput, ...]
    requested_ticket_counts: tuple[int, ...]
    predecision: tuple[PredeadlineMockRace, ...]
    postrace: tuple[PostraceMockResult, ...]


@dataclass(frozen=True, slots=True)
class OfflineV5DayVerdict:
    reason: str
    mock_complete: bool = False
    candidate_races: int = 0
    simulated_tickets: int = 0
    synthetic_paid_yen: int = 0
    synthetic_return_yen: int = 0
    synthetic_net_yen: int = 0
    synthetic_roi_pct: float | None = None
    independently_authenticated_source: bool = field(default=False, init=False)
    actual_purchase_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def evaluate_offline_v5_day(data: object) -> OfflineV5DayVerdict:
    """Run a complete mock day only with equal race and freeze cohorts.

    1. Recompute fixed V5 six-lane first-place probabilities.
    2. Rank ALL 120 synthetic 3-ren-tan probabilities, explicit ticket count.
    3. Join exact selected tickets to frozen fake orders and postrace returns.
    Unknown/late/unmatched data fail before any synthetic economic totals.
    """
    def deny(reason: str) -> OfflineV5DayVerdict:
        return OfflineV5DayVerdict(reason)

    if type(data) is not OfflineV5DayInput:
        return deny('DAY_INPUT_INVALID')
    cases, counts, pre, post = (
        data.candidates, data.requested_ticket_counts,
        data.predecision, data.postrace,
    )
    if (type(cases) is not tuple or not 0 < len(cases) <= MAX_RACES
            or any(type(x) is not OfflineV5InferenceInput for x in cases)
            or type(counts) is not tuple or len(counts) != len(cases)
            or any(type(n) is not int or not 1 <= n <= 120 for n in counts)
            or type(pre) is not tuple or len(pre) != len(cases)
            or any(type(x) is not PredeadlineMockRace for x in pre)
            or type(post) is not tuple or len(post) != len(cases)
            or any(type(x) is not PostraceMockResult for x in post)):
        return deny('DAY_COHORT_OR_TICKET_COUNTS_INVALID')

    race_ids = [x.race_id for x in cases]
    pre_ids = [x.race_id for x in pre]
    post_ids = [x.race_id for x in post]
    if (any(type(x) is not str or not x for x in race_ids + pre_ids + post_ids)
            or len(set(race_ids)) != len(race_ids)
            or len(set(pre_ids)) != len(pre_ids)
            or len(set(post_ids)) != len(post_ids)
            or set(race_ids) != set(pre_ids) or set(race_ids) != set(post_ids)):
        return deny('DAY_RACE_ID_JOIN_INVALID')
    if len({rid[:8] for rid in race_ids}) != 1:
        return deny('DAY_MIXED_RACE_DATES')

    pre_by_id = {x.race_id: x for x in pre}
    ranks = []
    for candidate, ticket_count in zip(cases, counts):
        race = pre_by_id[candidate.race_id]
        # Both datetimes are caller supplied mock clocks, not trusted proof.
        if (type(candidate.decision_cutoff_at) is not datetime
                or type(race.frozen_at) is not datetime
                or candidate.decision_cutoff_at != race.frozen_at
                or candidate.decision_cutoff_at.tzinfo is None
                or candidate.decision_cutoff_at.utcoffset() is None):
            return deny('INFERENCE_NOT_TIED_TO_FROZEN_DECISION_TIME')
        scored = check_offline_v5_inference(candidate)
        if (scored.synthetic_math_consistent is not True
                or scored.race_id != candidate.race_id
                or any(getattr(scored, key, None) is not False for key in (
                    'independently_authenticated_source',
                    'original_first_observation_verified',
                    'six_active_starts_confirmed', 'selection_eligible',
                    'beforeinfo_first_write_eligible', 'forward_eligible',
                    'buy_eligible',
                ))):
            return deny('V5_INFERENCE_' + str(scored.reason)[:75])
        ranked = rank_offline_v5_trifectas(scored, ticket_count=ticket_count)
        if (ranked.synthetic_math_consistent is not True
                or ranked.race_id != candidate.race_id
                or ranked.requested_ticket_count != ticket_count
                or len(ranked.ticket_distribution) != 120
                or any(getattr(ranked, key, None) is not False for key in (
                    'independently_authenticated_source',
                    'original_first_observation_verified',
                    'six_active_starts_confirmed', 'selection_eligible',
                    'beforeinfo_first_write_eligible', 'forward_eligible',
                    'buy_eligible',
                ))):
            return deny('V5_TRIFECTA_' + str(ranked.reason)[:75])
        ranks.append(ranked)

    cash = audit_offline_shadow_cash_bridge(tuple(ranks), pre, post)
    if (cash.mock_complete is not True
            or cash.reason != 'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD'
            or cash.candidate_races != len(cases)
            or any(getattr(cash, key, None) is not False for key in (
                'actual_purchase_verified', 'independently_authenticated_source',
                'six_active_starts_confirmed', 'selection_eligible',
                'beforeinfo_first_write_eligible', 'forward_eligible',
                'buy_eligible',
            ))):
        return deny('V5_SHADOW_CASH_' + str(cash.reason)[:75])
    return OfflineV5DayVerdict(
        'SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD', True,
        cash.candidate_races, cash.tickets, cash.synthetic_paid_yen,
        cash.synthetic_return_yen, cash.synthetic_net_yen,
        cash.synthetic_roi_pct,
    )
