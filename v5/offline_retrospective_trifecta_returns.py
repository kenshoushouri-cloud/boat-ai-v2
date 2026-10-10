"""V5 retrospective 3連単 returns, from FIXED selections + actual result rows.

Pure CPU-only economics: no DB, HTTP, Railway, official fetch, stake placement or
prediction based on postrace results/closing odds. An output is scenario math,
NOT evidence that selections or odds existed before the actual race cutoff.
ALL selected races are retained. PENDING/unverified refund -> no full-cohort ROI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from itertools import permutations

_RACE = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
_TICKETS = frozenset("-".join(map(str, t)) for t in permutations(range(1, 7), 3))


@dataclass(frozen=True)
class FixedTicket:
    combination: str
    stake_yen: int


@dataclass(frozen=True)
class FixedSelection:
    race_id: str
    tickets: tuple[FixedTicket, ...]


@dataclass(frozen=True)
class OfficialSettlement:
    race_id: str
    status: str  # "OFFICIAL", "VOID", "PENDING"
    winning_ticket: str | None = None
    payout_per_100_yen: int | None = None
    # None means unknown/unverified, () means confirmed no refundable boats.
    refund_boats: tuple[int, ...] | None = None


@dataclass(frozen=True)
class RetrospectiveReturns:
    reason: str
    scenario_only: bool = True
    original_predeadline_capture_verified: bool = False
    genuine_forward_roi_verified: bool = False
    buy_eligible: bool = False
    candidate_races: int = 0
    planned_stake_yen: int = 0
    resolved_races: int = 0
    unresolved_races: int = 0
    resolved_stake_yen: int = 0
    unresolved_stake_yen: int = 0
    gross_return_yen: int = 0
    hypothetical_net_yen: int | None = None
    hypothetical_roi_pct: float | None = None
    status_by_race: tuple[tuple[str, str], ...] = ()


def _race_id(s: str) -> bool:
    if type(s) is not str or _RACE.fullmatch(s) is None:
        return False
    try:
        return datetime.strptime(s[:8], "%Y%m%d") >= datetime(2025, 7, 1)
    except ValueError:
        return False


def evaluate_fixed_retrospective_returns(
    selections: object,
    settlements: object,
) -> RetrospectiveReturns:
    """Compute hypothetical returns only after the entire cohort is resolved.

    A numeric output never proves the tickets were actually selected before
    cutoff, nor that 3連単 second/third probabilities were calibrated.
    """
    def fail(msg: str) -> RetrospectiveReturns:
        return RetrospectiveReturns(msg)

    if (type(selections) not in (tuple, list) or not 0 < len(selections) <= 500
            or any(type(s) is not FixedSelection or not _race_id(s.race_id)
                   or type(s.tickets) is not tuple or not 1 <= len(s.tickets) <= 120
                   for s in selections)):
        return fail("SELECTION_COHORT_INVALID")
    race_ids: set[str] = set()
    paid_by_race: dict[str, int] = {}
    for s in selections:
        if s.race_id in race_ids:
            return fail("DUPLICATE_SELECTED_RACE")
        race_ids.add(s.race_id)
        tickets: set[str] = set()
        paid = 0
        for t in s.tickets:
            if (type(t) is not FixedTicket
                    or t.combination not in _TICKETS
                    or type(t.stake_yen) is not int
                    or t.stake_yen < 100 or t.stake_yen % 100 != 0):
                return fail("INVALID_SELECTED_TICKET")
            if t.combination in tickets:
                return fail("DUPLICATE_SELECTED_TICKET")
            tickets.add(t.combination)
            paid += t.stake_yen
        paid_by_race[s.race_id] = paid
    if (type(settlements) not in (list, tuple)
            or any(type(x) is not OfficialSettlement or not _race_id(x.race_id)
                   for x in settlements)):
        return fail("SETTLEMENT_INPUT_INVALID")
    if (len({x.race_id for x in settlements}) != len(settlements)
            or {x.race_id for x in settlements} - race_ids):
        return fail("EXTRA_OR_DUPLICATE_SETTLEMENT")
    by_id = {x.race_id: x for x in settlements}
    gross, settled_stake, nsettled = 0, 0, 0
    statuses: list[tuple[str, str]] = []
    for sel in selections:  # The original selected cohort is NEVER postrace-filtered.
        outcome = by_id.get(sel.race_id)
        status = "UNRESOLVED"
        if outcome is None or outcome.status == "PENDING":
            statuses.append((sel.race_id, status))
            continue
        if outcome.status not in ("OFFICIAL", "VOID"):
            return fail("UNKNOWN_RACE_STATUS")
        if outcome.status == "VOID":
            if (outcome.winning_ticket is not None
                    or outcome.payout_per_100_yen is not None
                    or outcome.refund_boats not in (None, ())):
                return fail("VOID_SETTLEMENT_CONTRADICTION")
            returned = paid_by_race[sel.race_id]
            status = "VOID_REFUNDED"
        else:
            if (outcome.winning_ticket not in _TICKETS
                    or type(outcome.payout_per_100_yen) is not int
                    or outcome.payout_per_100_yen < 100):
                return fail("OFFICIAL_WINNER_OR_PAYOUT_INVALID")
            if outcome.refund_boats is None:
                statuses.append((sel.race_id, "REFUND_MAPPING_UNVERIFIED"))
                continue
            if (type(outcome.refund_boats) is not tuple
                    or len(set(outcome.refund_boats)) != len(outcome.refund_boats)
                    or any(type(x) is not int or x not in range(1, 7)
                           for x in outcome.refund_boats)):
                return fail("REFUND_BOATS_INVALID")
            # Official winning ticket must not contain a fully refunded boat.
            winning_boats = set(map(int, outcome.winning_ticket.split("-")))
            if winning_boats.intersection(outcome.refund_boats):
                return fail("WINNER_REFUND_CONTRADICTION")
            returned = 0
            for t in sel.tickets:
                boats = set(map(int, t.combination.split("-")))
                if boats.intersection(outcome.refund_boats):
                    returned += t.stake_yen
                elif t.combination == outcome.winning_ticket:
                    returned += (t.stake_yen // 100) * outcome.payout_per_100_yen
            status = "OFFICIAL_RESOLVED"
        gross += returned
        settled_stake += paid_by_race[sel.race_id]
        nsettled += 1
        statuses.append((sel.race_id, status))
    all_stake = sum(paid_by_race.values())
    pending_stake = all_stake - settled_stake
    complete = nsettled == len(selections)
    return RetrospectiveReturns(
        reason=("RETROSPECTIVE_CLOSING_PRICE_SCENARIO_ONLY" if complete
                else "INCOMPLETE_COHORT_ROI_WITHHELD"),
        candidate_races=len(selections),
        planned_stake_yen=all_stake,
        resolved_races=nsettled,
        unresolved_races=len(selections)-nsettled,
        resolved_stake_yen=settled_stake,
        unresolved_stake_yen=pending_stake,
        gross_return_yen=gross,
        hypothetical_net_yen=(gross-all_stake if complete else None),
        hypothetical_roi_pct=(round(100*gross/all_stake, 4) if complete else None),
        status_by_race=tuple(statuses),
    )
