"""V5 OFFLINE retrospective TOP-N trifecta + recorded settlement adapter.

No SQL, HTTP, odds access or BUY. A complete output is HYPOTHETICAL scenario
math; no first-write/as-of, official refund authenticity or purchase proven.
Never infer 'no refunds' from missing F/L fields, or omit VOID/PENDING races.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import permutations

from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_retrospective_trifecta_returns import (
    FixedTicket, FixedSelection, OfficialSettlement, RetrospectiveReturns,
    evaluate_fixed_retrospective_returns,
)

ALL_TICKETS = frozenset("-".join(map(str, x))
                        for x in permutations(range(1, 7), 3))
RANK_REASON = "SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD"
RANK_NO_AUTH = (
    "original_first_observation_verified", "independently_authenticated_source",
    "six_active_starts_confirmed", "selection_eligible",
    "beforeinfo_first_write_eligible", "forward_eligible", "buy_eligible",
)
VOID_LABELS = frozenset(("void", "cancelled", "canceled", "不成立", "中止"))


@dataclass(frozen=True, slots=True)
class StoredResult:
    race_id: str
    result_status: str | None
    race_status: str | None
    winning_ticket: str | None
    payout_per_100_yen: int | None


@dataclass(frozen=True, slots=True)
class RefundEvidenceClaim:
    """Caller-entered official refund-section evidence, NOT independently checked."""
    race_id: str
    refundable_boats: tuple[int, ...]  # () ONLY when explicitly confirmed none
    source_ref: str


@dataclass(frozen=True, slots=True)
class VoidEvidenceClaim:
    race_id: str
    source_ref: str  # e.g. specific official cancelled-race record


@dataclass(frozen=True, slots=True)
class JoinedRetrospective:
    reason: str
    cash: RetrospectiveReturns | None = None
    known_official_races: int = 0
    evidenced_void_races: int = 0
    missing_result_races: int = 0
    missing_refund_evidence_races: int = 0
    postrace_archive_only: bool = field(default=True, init=False)
    independently_authenticated_source: bool = field(default=False, init=False)
    predeadline_frozen_selection_verified: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def join_v5_rankings_to_stored_results(
    rankings: object,
    stored_results: object,
    refund_evidence: object,
    void_evidence: object,
    *,
    ticket_stake_yen: object,
) -> JoinedRetrospective:
    """Fixed order from V5 shadow ranking, payout from stored official result.

    ALL originally ranked races remain in the denominator, even when pending.
    Closing odds are neither read nor accepted as an input parameter.
    """
    def hold(code: str) -> JoinedRetrospective:
        return JoinedRetrospective(code)

    if (type(ticket_stake_yen) is not int or ticket_stake_yen < 100
            or ticket_stake_yen % 100 != 0):
        return hold("EXPLICIT_VALID_TICKET_STAKE_REQUIRED")
    if (type(rankings) not in (tuple, list) or not 0 < len(rankings) <= 500
            or any(type(r) is not OfflineTrifectaShadowRanking for r in rankings)):
        return hold("RANKING_COHORT_INVALID")
    ids = [r.race_id for r in rankings]
    if len(set(ids)) != len(ids):
        return hold("DUPLICATE_RANKING_RACE")
    fixed: list[FixedSelection] = []
    for r in rankings:
        if (r.reason != RANK_REASON or r.synthetic_math_consistent is not True
                or any(getattr(r, name, None) is not False for name in RANK_NO_AUTH)
                or type(r.requested_ticket_count) is not int
                or not 1 <= r.requested_ticket_count <= 120
                or type(r.ticket_distribution) is not tuple
                or type(r.top_tickets) is not tuple
                or len(r.ticket_distribution) != 120
                or len(r.top_tickets) != r.requested_ticket_count):
            return hold("UNTRUSTED_OR_INCOMPLETE_V5_RANKING")
        distribution = r.ticket_distribution
        if (any(type(row) is not tuple or len(row) != 2
                or type(row[0]) is not str
                or row[0] not in ALL_TICKETS
                or type(row[1]) not in (float, int)
                or not math.isfinite(row[1]) or row[1] <= 0
                for row in distribution)
                or {x[0] for x in distribution} != ALL_TICKETS
                or distribution != tuple(sorted(distribution))
                or not math.isclose(math.fsum(x[1] for x in distribution), 1.0,
                                    rel_tol=0, abs_tol=1e-9)):
            return hold("INVALID_V5_TICKET_DISTRIBUTION")
        expected = tuple(sorted(distribution, key=lambda x: (-x[1], x[0]))
                         [:r.requested_ticket_count])
        if r.top_tickets != expected:
            return hold("STALE_OR_FORGED_V5_TOP_TICKETS")
        fixed.append(FixedSelection(
            r.race_id, tuple(FixedTicket(t, ticket_stake_yen) for t, _ in expected)))
    if any(not isinstance(x, (tuple, list)) for x in
           (stored_results, refund_evidence, void_evidence)):
        return hold("EVIDENCE_COLLECTION_INVALID")

    def checked_map(values: object, cls: type) -> dict | None:
        if any(type(row) is not cls or row.race_id not in ids
               or type(row.race_id) is not str for row in values):
            return None
        result = {row.race_id: row for row in values}
        return result if len(result) == len(values) else None

    results = checked_map(stored_results, StoredResult)
    refunds = checked_map(refund_evidence, RefundEvidenceClaim)
    voids = checked_map(void_evidence, VoidEvidenceClaim)
    if results is None or refunds is None or voids is None:
        return hold("EXTRA_DUPLICATE_OR_BAD_EVIDENCE")
    for proof in refunds.values():
        if (type(proof.source_ref) is not str or not proof.source_ref.strip()
                or type(proof.refundable_boats) is not tuple
                or len(set(proof.refundable_boats)) != len(proof.refundable_boats)
                or any(type(n) is not int or n not in range(1, 7)
                       for n in proof.refundable_boats)):
            return hold("INVALID_REFUND_CLAIM")
    if any(type(p.source_ref) is not str or not p.source_ref.strip()
           for p in voids.values()):
        return hold("INVALID_VOID_CLAIM")
    if set(refunds) & set(voids):
        return hold("REFUND_AND_VOID_CLAIMS_CONFLICT")

    settlements: list[OfficialSettlement] = []
    official = void_count = missing_result = missing_refund = 0
    for rid in ids:
        r = results.get(rid)
        if r is None:
            missing_result += 1
            settlements.append(OfficialSettlement(rid, "PENDING"))
            continue
        if type(r.result_status) is not str or type(r.race_status) is not str:
            missing_result += 1
            settlements.append(OfficialSettlement(rid, "PENDING"))
            continue
        flags = (r.result_status.strip().lower(), r.race_status.strip().lower())
        if flags == ("official", "official"):
            if rid in voids:
                return hold("OFFICIAL_RESULT_CONFLICTS_WITH_VOID_EVIDENCE")
            official += 1
            if rid not in refunds:
                missing_refund += 1
            settlements.append(OfficialSettlement(
                rid, "OFFICIAL", r.winning_ticket, r.payout_per_100_yen,
                refunds[rid].refundable_boats if rid in refunds else None))
        elif all(x in VOID_LABELS for x in flags):
            if rid not in voids:
                missing_result += 1
                settlements.append(OfficialSettlement(rid, "PENDING"))
                continue
            if r.winning_ticket is not None or r.payout_per_100_yen is not None:
                return hold("VOID_HAS_WINNER_OR_PAYOUT")
            void_count += 1
            settlements.append(OfficialSettlement(rid, "VOID"))
        else:
            missing_result += 1
            settlements.append(OfficialSettlement(rid, "PENDING"))
    cash = evaluate_fixed_retrospective_returns(tuple(fixed), tuple(settlements))
    if cash.reason not in (
        "RETROSPECTIVE_RESULT_PAYOUT_SCENARIO_ONLY",
        "INCOMPLETE_COHORT_ROI_WITHHELD",
    ):
        return hold("SETTLEMENT_" + cash.reason)
    return JoinedRetrospective(
        "RETROSPECTIVE_JOIN_SCENARIO_ONLY"
        if cash.unresolved_races == 0 else "RETROSPECTIVE_JOIN_PENDING_ROI_WITHHELD",
        cash, official, void_count, missing_result, missing_refund)
