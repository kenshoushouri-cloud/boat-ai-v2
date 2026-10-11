"""V5 frozen PL scenario tickets -> stored official 3連単 settlement.

OFFLINE ONLY: no DB, network, saved odds, purchase, or privileged state.
Caller timestamps/sources never prove real cutoff authenticity. Missing refund
verification ALWAYS withholds whole-cohort scenario ROI, not loss or exclusion.
This is retrospective scenario linkage, NOT verified actual V5 betting returns.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_retrospective_trifecta_returns import (
    FixedSelection, FixedTicket, OfficialSettlement, RetrospectiveReturns,
    evaluate_fixed_retrospective_returns,
)

_JST = ZoneInfo("Asia/Tokyo")
_EXPECTED = "SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD"
_RACE_ID = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
_ALL = frozenset("-".join(map(str, p)) for p in permutations(range(1, 7), 3))
_GUARDS = (
    "original_first_observation_verified", "independently_authenticated_source",
    "six_active_starts_confirmed", "selection_eligible",
    "beforeinfo_first_write_eligible", "forward_eligible", "buy_eligible",
)


@dataclass(frozen=True)
class FrozenResearchRank:
    ranking: OfflineTrifectaShadowRanking
    decision_cutoff_at: datetime
    race_deadline_at: datetime
    materialized_at: datetime  # Recorded reconstruction time, NOT trusted first observation.
    stake_per_ticket_yen: int  # Required explicit decision; no V4 default.


@dataclass(frozen=True)
class StoredResultRow:
    race_id: str
    result_status: str | None
    race_status: str | None
    winning_ticket: str | None
    payout_per_100_yen: int | None
    # None is unverified even when no F/L appears elsewhere.
    refund_boats: tuple[int, ...] | None = None
    refund_section_verified: bool = False
    whole_race_void_verified: bool = False


@dataclass(frozen=True)
class V5ScenarioJoin:
    reason: str
    selections: tuple[FixedSelection, ...] = ()
    settlements: tuple[OfficialSettlement, ...] = ()
    provenance_by_race: tuple[tuple[str, str], ...] = ()
    economics: RetrospectiveReturns | None = None
    scenario_only: bool = field(default=True, init=False)
    predeadline_original_capture_verified: bool = field(default=False, init=False)
    independently_authenticated_official_source: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _check_frozen(case: FrozenResearchRank) -> bool:
    rank = case.ranking
    if (type(rank) is not OfflineTrifectaShadowRanking
            or rank.reason != _EXPECTED or rank.synthetic_math_consistent is not True
            or any(getattr(rank, flag, None) is not False for flag in _GUARDS)
            or type(rank.race_id) is not str
            or _RACE_ID.fullmatch(rank.race_id) is None
            or rank.race_id[:8] < "20250701"):
        return False
    if (not all(_aware(t) for t in
                (case.decision_cutoff_at, case.race_deadline_at, case.materialized_at))
            or case.decision_cutoff_at >= case.race_deadline_at
            or type(case.stake_per_ticket_yen) is not int
            or case.stake_per_ticket_yen < 100 or case.stake_per_ticket_yen % 100 != 0):
        return False
    if (case.decision_cutoff_at.astimezone(_JST).strftime("%Y%m%d")
            != rank.race_id[:8]
            or case.race_deadline_at.astimezone(_JST).strftime("%Y%m%d")
            != rank.race_id[:8]):
        return False
    distribution = rank.ticket_distribution
    if (type(distribution) is not tuple or len(distribution) != 120
            or type(rank.top_tickets) is not tuple
            or type(rank.requested_ticket_count) is not int
            or not 1 <= rank.requested_ticket_count <= 120):
        return False
    if any(type(p) is not tuple or len(p) != 2
           or type(p[0]) is not str or p[0] not in _ALL
           or type(p[1]) not in (int, float)
           or not math.isfinite(p[1]) or p[1] <= 0 for p in distribution):
        return False
    if (frozenset(ticket for ticket, _ in distribution) != _ALL
            or not math.isclose(math.fsum(p for _, p in distribution),
                                1., rel_tol=0., abs_tol=1e-9)):
        return False
    ordered = tuple(sorted(distribution, key=lambda x: (-x[1], x[0])))
    return rank.top_tickets == ordered[:rank.requested_ticket_count]


def _stored_to_official(row: StoredResultRow) -> OfficialSettlement:
    result_status = str(row.result_status or "").strip().lower()
    race_status = str(row.race_status or "").strip().lower()
    if (row.whole_race_void_verified is True
            and result_status in ("void", "cancelled")
            and race_status in ("void", "cancelled")
            and row.winning_ticket is None and row.payout_per_100_yen is None):
        return OfficialSettlement(row.race_id, "VOID")
    if result_status != "official" or race_status != "official":
        return OfficialSettlement(row.race_id, "PENDING")
    if (type(row.winning_ticket) is not str
            or row.winning_ticket not in _ALL
            or type(row.payout_per_100_yen) is not int
            or row.payout_per_100_yen < 100):
        return OfficialSettlement(row.race_id, "PENDING")
    refunds = row.refund_boats if row.refund_section_verified is True else None
    # Explicitly verified empty refund section is different from unknown.
    return OfficialSettlement(row.race_id, "OFFICIAL", row.winning_ticket,
                              row.payout_per_100_yen, refunds)


def join_ranked_v5_scenarios(
    frozen_cases: object, result_rows: object,
) -> V5ScenarioJoin:
    """Fix ticket choices BEFORE reading outcomes; never choose by winnings."""
    def fail(reason: str) -> V5ScenarioJoin:
        return V5ScenarioJoin(reason)

    if (type(frozen_cases) not in (tuple, list)
            or not 1 <= len(frozen_cases) <= 500
            or any(type(c) is not FrozenResearchRank for c in frozen_cases)):
        return fail("INVALID_FROZEN_RANK_COHORT")
    if (type(result_rows) not in (tuple, list)
            or any(type(r) is not StoredResultRow for r in result_rows)):
        return fail("INVALID_STORED_RESULT_ROWS")
    ids = [c.ranking.race_id for c in frozen_cases]
    if len(set(ids)) != len(ids) or any(not _check_frozen(c) for c in frozen_cases):
        return fail("RANKING_OR_TIME_SHAPE_INVALID")
    if (len({r.race_id for r in result_rows}) != len(result_rows)
            or {r.race_id for r in result_rows} - set(ids)):
        return fail("DUPLICATE_OR_EXTRANEOUS_RESULT_RACE")
    selections = tuple(
        FixedSelection(c.ranking.race_id,
                       tuple(FixedTicket(t, c.stake_per_ticket_yen)
                             for t, _ in c.ranking.top_tickets))
        for c in frozen_cases
    )
    provenance = tuple(
        (c.ranking.race_id,
         "RETROSPECTIVE_ARCHIVE_NOT_ASOF"
         if c.materialized_at >= c.decision_cutoff_at
         else "EARLY_TIMESTAMP_CLAIM_NOT_SOURCE_AUTHENTICATED")
        for c in frozen_cases
    )
    # Unmatched original selections remain PENDING in the whole-cohort ledger.
    settlements = tuple(_stored_to_official(r) for r in result_rows)
    economics = evaluate_fixed_retrospective_returns(selections, settlements)
    if economics.reason not in (
            "RETROSPECTIVE_RESULT_PAYOUT_SCENARIO_ONLY",
            "INCOMPLETE_COHORT_ROI_WITHHELD"):
        return fail("CASH_LEDGER_" + economics.reason)
    return V5ScenarioJoin(
        "RETROSPECTIVE_V5_SCENARIO_JOIN_NO_BUY_AUTHORITY",
        selections, settlements, provenance, economics,
    )
