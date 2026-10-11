"""Bounded 7-day research batch planner and whole-period scenario rollup.

No database/network/official GET. Do not infer frozen picks from outcomes.
A complete *caller-supplied* inventory is not independent source attestation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from v5.offline_whole_day_research_ledger import WholeDayResearchLedger

START = date(2025, 7, 1)
MAX_DAYS = 900


@dataclass(frozen=True)
class ResearchWindow:
    start: date
    end: date  # inclusive
    expected_days: int


@dataclass(frozen=True)
class ResearchPeriodPlan:
    start: date
    end: date
    windows: tuple[ResearchWindow, ...]
    expected_days: int
    scenario_only: bool = field(default=True, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class ResearchPeriodSummary:
    status: str
    expected_days: int
    supplied_days: int
    missing_days: tuple[date, ...]
    inventory_races: int
    selected_races: int
    no_buy_races: int
    pending_races: int
    unresolved_selected_races: int
    hypothetical_stake_yen: int
    hypothetical_gross_yen: int
    hypothetical_net_yen: int | None
    hypothetical_roi_pct: float | None
    scenario_only: bool = field(default=True, init=False)
    independently_verified_inventory: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def plan_research_period(start: date, end: date, days_per_window: int = 7) -> ResearchPeriodPlan:
    """Prepare multi-day work before any access to costly external systems."""
    if (type(start) is not date or type(end) is not date or start < START
            or end < start or (end - start).days >= MAX_DAYS):
        raise ValueError("PERIOD_BOUNDS_INVALID")
    if type(days_per_window) is not int or not 1 <= days_per_window <= 31:
        raise ValueError("WINDOW_DAYS_INVALID")
    windows = []
    day = start
    while day <= end:
        upper = min(day + timedelta(days=days_per_window - 1), end)
        windows.append(ResearchWindow(day, upper, (upper-day).days + 1))
        day = upper + timedelta(days=1)
    return ResearchPeriodPlan(start, end, tuple(windows), (end-start).days+1)


def rollup_research_period(plan: ResearchPeriodPlan,
                           days: tuple[WholeDayResearchLedger, ...]) -> ResearchPeriodSummary:
    """Never silently drop unfinished days or publish full-window ROI early.

    Values are hypothetical research scenarios, never historical buys/profits.
    """
    if type(plan) is not ResearchPeriodPlan or type(days) is not tuple:
        raise ValueError("PERIOD_INPUT_TYPE_INVALID")
    expected = {plan.start + timedelta(days=n) for n in range(plan.expected_days)}
    observed: dict[date, WholeDayResearchLedger] = {}
    count = selected = no_buy = pending = unresolved = stake = gross = 0
    for row in days:
        if type(row) is not WholeDayResearchLedger:
            raise ValueError("DAY_LEDGER_TYPE_INVALID")
        audit = row.coverage.audit
        day = audit.day
        if day not in expected or day in observed:
            raise ValueError("DUPLICATE_OR_OUT_OF_PERIOD_DAY")
        observed[day] = row
        roster = row.all_race_decisions
        ids = [rid for rid, _ in roster]
        if (not audit.caller_inventory_matches_decision_ledger
                or audit.inventory_count != len(roster) or not roster
                or len(set(ids)) != len(ids)
                or any(type(rid) is not str or rid[:8] != day.strftime("%Y%m%d")
                       for rid in ids)
                or audit.unaccounted_ids or audit.unexpected_ids):
            raise ValueError("DAY_INVENTORY_UNVERIFIED_OR_INCOMPLETE")
        subsets = (row.selected_race_ids, row.no_buy_race_ids, row.pending_race_ids)
        for names, label in zip(subsets, ("FROZEN", "NO_BUY", "PENDING")):
            if set(names) != {rid for rid, decision in roster if decision == label}:
                raise ValueError("DAY_DECISION_COHORT_MISMATCH")
        if sum(map(len, subsets)) != len(roster):
            raise ValueError("DAY_DECISION_COUNT_INCONSISTENT")
        count += len(roster)
        selected += len(row.selected_race_ids)
        no_buy += len(row.no_buy_race_ids)
        pending += len(row.pending_race_ids)
        if row.selected_race_ids:
            if (row.scenario is None or row.scenario.economics is None
                    or not row.scenario.scenario_only):
                raise ValueError("SELECTED_DAY_SCENARIO_MISSING")
            economics = row.scenario.economics
            if (economics.candidate_races != len(row.selected_race_ids)
                    or economics.resolved_races + economics.unresolved_races
                       != economics.candidate_races
                    or economics.planned_stake_yen <= 0
                    or economics.gross_return_yen < 0):
                raise ValueError("SCENARIO_SETTLEMENT_COUNTS_INVALID")
            unresolved += economics.unresolved_races
            stake += economics.planned_stake_yen
            gross += economics.gross_return_yen
        elif row.scenario is not None:
            raise ValueError("ZERO_BUY_DAY_SCENARIO_FORBIDDEN")
    missing = tuple(sorted(expected - set(observed)))
    complete = not missing and not pending and not unresolved and selected > 0
    reason = ("RESEARCH_SCENARIO_ALL_DECLARED_DAYS_RESOLVED" if complete
              else "RESEARCH_COHORT_INCOMPLETE_ROI_WITHHELD")
    return ResearchPeriodSummary(
        reason, plan.expected_days, len(observed), missing,
        count, selected, no_buy, pending, unresolved, stake, gross,
        gross-stake if complete else None,
        round(100*gross/stake, 4) if complete else None)
