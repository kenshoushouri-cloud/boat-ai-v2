# -*- coding: utf-8 -*-
"""Pure monthly-profit feasibility math for V5/V5.1 planning.

This module is deliberately result-agnostic and has no I/O.
It converts a prospective policy's already-measured ROI and natural volume into:
- monthly investment;
- monthly profit at a fixed ticket stake;
- ROI required to reach a monthly profit target at that stake;
- planning-only ticket stake required to reach the target at a supplied ROI.

Important:
- this is NOT a staking strategy;
- it does NOT authorize a stake change;
- selection thresholds must never be tuned merely to satisfy the profit target;
- stake scaling is considered only after the policy's preregistered evidence gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil


TARGET_MONTHLY_PROFIT_JPY = 50_000
BASE_TICKET_STAKE_JPY = 100
PLANNING_DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class MonthlyScenario:
    days: float
    races_per_day: float
    tickets_per_race: float
    stake_per_ticket_jpy: float
    roi: float  # decimal, 1.0 == 100%

    @property
    def bets_per_month(self) -> float:
        return self.days * self.races_per_day * self.tickets_per_race

    @property
    def investment_jpy(self) -> float:
        return self.bets_per_month * self.stake_per_ticket_jpy

    @property
    def profit_jpy(self) -> float:
        return self.investment_jpy * (self.roi - 1.0)


def required_roi_for_target(
    *,
    target_profit_jpy: float,
    days: float,
    races_per_day: float,
    tickets_per_race: float,
    stake_per_ticket_jpy: float,
) -> float:
    investment = days * races_per_day * tickets_per_race * stake_per_ticket_jpy
    if investment <= 0:
        raise ValueError("monthly investment must be positive")
    return 1.0 + target_profit_jpy / investment


def required_stake_for_target(
    *,
    target_profit_jpy: float,
    days: float,
    races_per_day: float,
    tickets_per_race: float,
    roi: float,
) -> float | None:
    edge = roi - 1.0
    monthly_bets = days * races_per_day * tickets_per_race
    if monthly_bets <= 0:
        raise ValueError("monthly bets must be positive")
    if edge <= 0:
        return None
    return target_profit_jpy / (monthly_bets * edge)


def ceil_to_100_jpy(value: float | None) -> int | None:
    if value is None:
        return None
    return int(ceil(value / 100.0) * 100)


def evidence_scaling_gate(
    *,
    observed_units: int,
    required_units: int,
    conservative_roi: float,
) -> dict:
    sample_ready = observed_units >= required_units
    conservative_profitable = conservative_roi > 1.0
    return {
        "sample_ready": sample_ready,
        "conservative_roi_above_100": conservative_profitable,
        "stake_scaling_review_allowed": sample_ready and conservative_profitable,
        "stake_change_authorized": False,
    }


def build_reference_report() -> dict:
    """Freeze the 2026-09-30 planning checkpoint using already-recorded metrics."""

    # Current formal V4 checkpoint through 2026-09-28.
    v4_overall_roi = 1.477273
    v4_second_half_roi = 1.352083
    v4_leave_one_day_worst_roi = 1.123684

    # Current S03_M2 checkpoint through 2026-09-28.
    s03_overall_roi = 1.606349
    s03_second_half_roi = 0.565625

    notification_rows = []
    for races_per_day in (1, 2, 3):
        required_roi = required_roi_for_target(
            target_profit_jpy=TARGET_MONTHLY_PROFIT_JPY,
            days=PLANNING_DAYS_PER_MONTH,
            races_per_day=races_per_day,
            tickets_per_race=2,
            stake_per_ticket_jpy=BASE_TICKET_STAKE_JPY,
        )
        notification_rows.append(
            {
                "races_per_day": races_per_day,
                "tickets_per_race": 2,
                "stake_per_ticket_jpy": BASE_TICKET_STAKE_JPY,
                "monthly_investment_jpy": (
                    PLANNING_DAYS_PER_MONTH
                    * races_per_day
                    * 2
                    * BASE_TICKET_STAKE_JPY
                ),
                "required_roi_for_plus_50000": required_roi,
            }
        )

    v4_6r = MonthlyScenario(
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=6,
        tickets_per_race=2,
        stake_per_ticket_jpy=BASE_TICKET_STAKE_JPY,
        roi=v4_overall_roi,
    )
    v4_required_stake_overall = required_stake_for_target(
        target_profit_jpy=TARGET_MONTHLY_PROFIT_JPY,
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=6,
        tickets_per_race=2,
        roi=v4_overall_roi,
    )
    v4_required_stake_second = required_stake_for_target(
        target_profit_jpy=TARGET_MONTHLY_PROFIT_JPY,
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=6,
        tickets_per_race=2,
        roi=v4_second_half_roi,
    )
    v4_required_stake_loo = required_stake_for_target(
        target_profit_jpy=TARGET_MONTHLY_PROFIT_JPY,
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=6,
        tickets_per_race=2,
        roi=v4_leave_one_day_worst_roi,
    )

    s03_natural = MonthlyScenario(
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=2.71,
        tickets_per_race=1,
        stake_per_ticket_jpy=BASE_TICKET_STAKE_JPY,
        roi=s03_overall_roi,
    )
    s03_required_stake = required_stake_for_target(
        target_profit_jpy=TARGET_MONTHLY_PROFIT_JPY,
        days=PLANNING_DAYS_PER_MONTH,
        races_per_day=2.71,
        tickets_per_race=1,
        roi=s03_overall_roi,
    )

    return {
        "contract": "MONTHLY_PROFIT_TARGET_FEASIBILITY_V1",
        "target_monthly_profit_jpy": TARGET_MONTHLY_PROFIT_JPY,
        "base_ticket_stake_jpy": BASE_TICKET_STAKE_JPY,
        "planning_days_per_month": PLANNING_DAYS_PER_MONTH,
        "notification_volume_reference": notification_rows,
        "v4_formal_top2": {
            "resolved_days": 8,
            "required_days": 20,
            "overall_roi": v4_overall_roi,
            "second_half_roi": v4_second_half_roi,
            "leave_one_day_worst_roi": v4_leave_one_day_worst_roi,
            "formal_races_per_day": 6,
            "tickets_per_race": 2,
            "monthly_profit_at_100_jpy_if_overall_roi_persisted": v4_6r.profit_jpy,
            "planning_stake_for_plus_50000_at_overall_roi": v4_required_stake_overall,
            "planning_stake_for_plus_50000_at_second_half_roi": v4_required_stake_second,
            "planning_stake_for_plus_50000_at_leave_one_day_worst_roi": v4_required_stake_loo,
            "rounded_100_jpy_planning_stakes": {
                "overall": ceil_to_100_jpy(v4_required_stake_overall),
                "second_half": ceil_to_100_jpy(v4_required_stake_second),
                "leave_one_day_worst": ceil_to_100_jpy(v4_required_stake_loo),
            },
            "evidence_gate": evidence_scaling_gate(
                observed_units=8,
                required_units=20,
                conservative_roi=v4_leave_one_day_worst_roi,
            ),
        },
        "s03_m2": {
            "evaluated_observations": 63,
            "required_observations": 100,
            "overall_roi": s03_overall_roi,
            "second_half_roi": s03_second_half_roi,
            "observed_recent_natural_races_per_day": 2.71,
            "tickets_per_race": 1,
            "monthly_profit_at_100_jpy_if_overall_roi_persisted": s03_natural.profit_jpy,
            "planning_stake_for_plus_50000_at_overall_roi": s03_required_stake,
            "rounded_100_jpy_planning_stake_overall": ceil_to_100_jpy(
                s03_required_stake
            ),
            "evidence_gate": evidence_scaling_gate(
                observed_units=63,
                required_units=100,
                conservative_roi=s03_second_half_roi,
            ),
        },
        "policy": {
            "monthly_profit_target_is_selection_tuning_target": False,
            "threshold_relaxation_for_volume_or_profit_allowed": False,
            "stake_change_authorized": False,
            "purchase_action": False,
            "production_behavior_changed": False,
            "rule": (
                "prove prospective edge first; then measure natural volume; "
                "only then review stake scaling separately"
            ),
        },
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build_reference_report(), ensure_ascii=False, indent=2, sort_keys=True))
