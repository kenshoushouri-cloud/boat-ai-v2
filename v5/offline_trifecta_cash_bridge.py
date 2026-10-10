"""Fake-only V5 120-ticket shadow to predeadline orders and postrace ledger.

Never makes purchases, reads odds, or grants Forward/BUY authority. Caller
frozen receipts and SHA256 are synthetic *shapes*, not authenticated evidence.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations

from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_trifecta_cash_ledger import (
    MAX_RACES, MockOrder, PredeadlineMockRace, SyntheticDayCash,
    audit_synthetic_trifecta_cash_ledger,
)

EXPECTED_RANK = 'SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD'
EXPECTED_LEDGER = 'SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED'
AUTH_RANK = (
    'original_first_observation_verified', 'independently_authenticated_source',
    'six_active_starts_confirmed', 'selection_eligible',
    'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible',
)
AUTH_LEDGER = (
    'independently_authenticated_source', 'actual_purchase_verified',
    'six_active_starts_confirmed', 'selection_eligible',
    'forward_eligible', 'buy_eligible',
)
ALL_TICKETS = frozenset('-'.join(map(str, p)) for p in permutations(range(1, 7), 3))


@dataclass(frozen=True, slots=True)
class OfflineShadowCashBridgeVerdict:
    reason: str
    mock_complete: bool = False
    candidate_races: int = 0
    tickets: int = 0
    official_races: int = 0
    void_races: int = 0
    ticket_hits: int = 0
    synthetic_paid_yen: int = 0
    synthetic_return_yen: int = 0
    synthetic_net_yen: int = 0
    synthetic_roi_pct: float | None = None
    synthetic_ticket_hit_pct: float | None = None
    days: tuple[SyntheticDayCash, ...] = ()
    actual_purchase_verified: bool = field(default=False, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def audit_offline_shadow_cash_bridge(
    rankings: object, predecision: object, postrace: object,
) -> OfflineShadowCashBridgeVerdict:
    """Join exact race-ID+TOP-N ticket order; never filter by postrace VOID.

    A complete mock may yield fake-only economics for regression testing. No
    inference or ledger verdict can promote a predeadline permission flag.
    """
    def hold(reason: str) -> OfflineShadowCashBridgeVerdict:
        return OfflineShadowCashBridgeVerdict(reason)

    if (type(rankings) not in (tuple, list) or not 0 < len(rankings) <= MAX_RACES
            or type(predecision) not in (tuple, list)
            or len(predecision) != len(rankings)):
        return hold('BRIDGE_COHORT_SHAPE_MISMATCH')
    if (any(type(x) is not OfflineTrifectaShadowRanking for x in rankings)
            or any(type(x) is not PredeadlineMockRace for x in predecision)):
        return hold('UNTRUSTED_RANKING_OR_PREDECISION_RECORD')
    rank_ids = [r.race_id for r in rankings]
    pre_ids = [r.race_id for r in predecision]
    if (any(type(x) is not str or not x for x in rank_ids + pre_ids)
            or len(set(rank_ids)) != len(rank_ids)
            or len(set(pre_ids)) != len(pre_ids)):
        return hold('DUPLICATE_OR_INVALID_RACE_ID')
    if set(rank_ids) != set(pre_ids):
        return hold('MISSING_OR_EXTRA_RACE_ID')
    by_race = {r.race_id: r for r in predecision}
    receipt_refs: set[str] = set()
    for rank in rankings:
        if (rank.reason != EXPECTED_RANK or rank.synthetic_math_consistent is not True
                or rank.second_third_pl_assumption_unvalidated is not True
                or any(getattr(rank, name, None) is not False for name in AUTH_RANK)):
            return hold('UNTRUSTED_RANKING_AUTHORITY')
        if (type(rank.requested_ticket_count) is not int
                or not 1 <= rank.requested_ticket_count <= 120
                or type(rank.ticket_distribution) is not tuple
                or type(rank.top_tickets) is not tuple
                or len(rank.ticket_distribution) != 120
                or len(rank.top_tickets) != rank.requested_ticket_count):
            return hold('RANKING_SHAPE_INVALID')
        dist = rank.ticket_distribution
        if any(type(x) is not tuple or len(x) != 2
               or type(x[0]) is not str or type(x[1]) not in (int, float)
               or not math.isfinite(x[1]) or x[1] <= 0 for x in dist):
            return hold('RANKING_DISTRIBUTION_INVALID')
        if ({x[0] for x in dist} != ALL_TICKETS
                or not math.isclose(math.fsum(x[1] for x in dist), 1., abs_tol=1e-12)
                or tuple(sorted(dist)) != dist):
            return hold('RANKING_DISTRIBUTION_INVALID')
        expected = tuple(sorted(dist, key=lambda x: (-x[1], x[0]))[:rank.requested_ticket_count])
        if rank.top_tickets != expected:
            return hold('FORGED_OR_STALE_TOP_TICKET_ORDER')
        race = by_race[rank.race_id]
        if (type(race.orders) is not tuple or len(race.orders) != len(expected)
                or any(type(o) is not MockOrder for o in race.orders)
                or tuple(o.ticket for o in race.orders) != tuple(t for t, _ in expected)):
            return hold('MISSING_EXTRA_OR_REORDERED_PURCHASE_TICKETS')
        for o in race.orders:
            if (type(o.purchase_receipt_ref) is not str or not o.purchase_receipt_ref.strip()
                    or o.purchase_receipt_ref in receipt_refs):
                return hold('MISSING_OR_DUPLICATE_PURCHASE_RECEIPT')
            receipt_refs.add(o.purchase_receipt_ref)

    ledger = audit_synthetic_trifecta_cash_ledger(predecision, postrace)
    if (ledger.reason != EXPECTED_LEDGER or ledger.mock_shape_consistent is not True
            or any(getattr(ledger, name, None) is not False for name in AUTH_LEDGER)):
        return hold('LEDGER_' + ledger.reason if type(ledger.reason) is str
                    and ledger.reason.isupper() and len(ledger.reason) <= 96
                    else 'UNTRUSTED_OR_INCOMPLETE_LEDGER')
    if (ledger.predecision_races != len(rankings)
            or ledger.purchased_tickets != sum(r.requested_ticket_count for r in rankings)
            or ledger.official_races + ledger.void_races != len(rankings)
            or sum(x.purchased_tickets for x in ledger.days) != ledger.purchased_tickets
            or sum(x.candidate_races for x in ledger.days) != len(rankings)):
        return hold('LEDGER_ACCOUNTING_MISMATCH')
    return OfflineShadowCashBridgeVerdict(
        'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD', True,
        ledger.predecision_races, ledger.purchased_tickets,
        ledger.official_races, ledger.void_races, ledger.winning_tickets,
        ledger.synthetic_paid_yen, ledger.synthetic_returns_yen,
        ledger.synthetic_net_yen, ledger.synthetic_roi_pct,
        ledger.synthetic_ticket_hit_pct, ledger.days,
    )
