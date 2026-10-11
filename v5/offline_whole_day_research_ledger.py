"""Whole-day retrospective V5 research denominator, NOT real purchase evidence.

Reconcile an existing FrozenDay + inventory / NO_BUY / PENDING ledger with a
separately reconstructed ranked-ticket cohort BEFORE passing selected results
to the existing payout calculator. The full claimed inventory and all supplied
outcomes remain in the audit, including races with no hypothetical selection.

This is a read-only, offline shape check. It cannot prove the claimed roster,
the temporal authenticity of a historical FrozenDay or the six active starts.
No database, official GET, production, Forward, LINE or BUY access.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from v5.offline_day_evidence_coverage import DayEvidenceRow
from v5.offline_frozen_day_evidence_adapter import (
    FrozenDayEvidenceBinding, audit_actual_frozen_day,
)
from v5.offline_prior_day_counter_update import FrozenDay
from v5.offline_retrospective_result_adapter import (
    FrozenResearchRank, StoredResultRow, V5ScenarioJoin,
    join_ranked_v5_scenarios,
)


@dataclass(frozen=True)
class WholeDayResearchLedger:
    reason: str
    coverage: FrozenDayEvidenceBinding
    # Inventory order is preserved, not filtered by settled/ranked outcomes.
    all_race_decisions: tuple[tuple[str, str], ...]
    all_result_rows: tuple[StoredResultRow, ...]
    selected_race_ids: tuple[str, ...]
    no_buy_race_ids: tuple[str, ...]
    pending_race_ids: tuple[str, ...]
    scenario: V5ScenarioJoin | None
    # A zero-ticket day has zero invested yen and no ROI; an incomplete
    # selected cohort with refund unknown withholds even hypothetical ROI.
    hypothetical_roi_available: bool
    inventory_independently_verified: bool = field(default=False, init=False)
    original_selection_time_verified: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def reconcile_whole_day_research(
    frozen_day: FrozenDay,
    inventory_race_ids: tuple[str, ...],
    inventory_source_ref: str,
    decisions: tuple[DayEvidenceRow, ...],
    claimed_frozen_race_ids: tuple[str, ...],
    frozen_ranks: tuple[FrozenResearchRank, ...],
    result_rows: tuple[StoredResultRow, ...],
) -> WholeDayResearchLedger:
    """Fail closed on denominator, tickets, or time discrepancies.

    Result rows are consulted ONLY after selection IDs and ticket combinations
    have been reconciled. This does not prove the selections were really made
    at their claimed times; every completed output is still scenario-only.
    """
    binding = audit_actual_frozen_day(
        frozen_day, inventory_race_ids, inventory_source_ref,
        decisions, claimed_frozen_race_ids,
    )
    if not binding.audit.caller_inventory_matches_decision_ledger:
        raise ValueError("CLAIMED_DAY_INVENTORY_INCOMPLETE")
    if type(frozen_ranks) is not tuple or type(result_rows) is not tuple:
        raise ValueError("RANK_OR_RESULT_COHORT_TYPE_INVALID")

    selected = binding.frozen_hypothetical_ticket_ids
    ranks = {}
    for case in frozen_ranks:
        if type(case) is not FrozenResearchRank:
            raise ValueError("RECONSTRUCTED_RANK_TYPE_INVALID")
        rid = getattr(case.ranking, "race_id", None)
        if type(rid) is not str or rid in ranks:
            raise ValueError("DUPLICATE_OR_INVALID_RANK_ID")
        ranks[rid] = case
    if set(ranks) != set(selected):
        raise ValueError("RECONSTRUCTED_RANK_COHORT_MISMATCH")

    frozen_by_id = {race.race_id: race for race in frozen_day.races}
    ledger_by_id = {row.race_id: row for row in decisions}
    for rid in selected:
        race = frozen_by_id[rid]
        expected = []
        for ticket in race.selected_tickets:
            if (type(ticket) is not tuple or len(ticket) != 3
                    or any(type(x) is not int or x not in range(1, 7)
                           for x in ticket)
                    or len(set(ticket)) != 3):
                raise ValueError("INVALID_FROZEN_TICKET")
            expected.append("-".join(map(str, ticket)))
        if len(expected) != len(set(expected)):
            raise ValueError("DUPLICATE_FROZEN_TICKET")
        candidate = ranks[rid]
        top = getattr(candidate.ranking, "top_tickets", None)
        if (type(top) is not tuple
                or tuple(item[0] for item in top
                         if type(item) is tuple and len(item) == 2) != tuple(expected)
                or len(top) != len(expected)):
            raise ValueError("RECONSTRUCTED_TICKET_SELECTION_MISMATCH")
        proof = ledger_by_id[rid]
        if (candidate.decision_cutoff_at != proof.decision_cutoff_at
                or candidate.race_deadline_at != proof.deadline_at):
            raise ValueError("RECONSTRUCTED_DECISION_CLOCK_MISMATCH")

    inventory = set(inventory_race_ids)
    seen_results = set()
    for result in result_rows:
        if type(result) is not StoredResultRow:
            raise ValueError("RESULT_ROW_TYPE_INVALID")
        if result.race_id not in inventory or result.race_id in seen_results:
            raise ValueError("RESULT_OUTSIDE_INVENTORY_OR_DUPLICATE")
        seen_results.add(result.race_id)
    full_status = tuple(
        (rid, ledger_by_id[rid].decision) for rid in inventory_race_ids
    )
    if not selected:
        return WholeDayResearchLedger(
            "ZERO_SELECTED_RACES_NO_ROI", binding, full_status,
            result_rows, (), binding.frozen_no_buy_ids,
            tuple(rid for rid, decision in full_status if decision == "PENDING"),
            None, False,
        )

    # Only selected races feed the existing payout scenario, while ALL supplied
    # results and the entire race-day cohort remain visible in this audit.
    selected_rows = tuple(row for row in result_rows
                          if row.race_id in ranks)
    joined = join_ranked_v5_scenarios(
        tuple(ranks[rid] for rid in selected), selected_rows,
    )
    if joined.reason != "RETROSPECTIVE_V5_SCENARIO_JOIN_NO_BUY_AUTHORITY":
        raise ValueError("RECONSTRUCTED_SCENARIO_JOIN_FAILED:" + joined.reason)
    economics = joined.economics
    return WholeDayResearchLedger(
        "WHOLE_DAY_RETROSPECTIVE_SCENARIO_ONLY", binding,
        full_status, result_rows, selected, binding.frozen_no_buy_ids,
        tuple(rid for rid, decision in full_status if decision == "PENDING"),
        joined,
        economics is not None and economics.hypothetical_roi_pct is not None,
    )
