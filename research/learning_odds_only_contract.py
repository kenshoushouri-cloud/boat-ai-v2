# -*- coding: utf-8 -*-
"""Pure design contract for a possible learning-all odds-only mode.

Research-only: no database, HTTP, Railway, LINE, decision, or purchase access.
This module describes desired behavior without wiring it into any runtime path.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningCollectionPlan:
    mode: str
    snapshot_label: str
    window_before_min: int
    window_after_min: int
    collect_scope: str
    fetch_beforeinfo: bool
    fetch_odds3t: bool
    save_weather: bool
    save_exhibition: bool
    save_entries: bool
    save_race_condition: bool
    save_racer_condition: bool
    save_odds: bool
    decision_enabled: bool
    line_enabled: bool
    purchase_enabled: bool

    @property
    def non_odds_write_paths(self) -> int:
        return sum(
            int(value)
            for value in (
                self.save_weather,
                self.save_exhibition,
                self.save_entries,
                self.save_race_condition,
                self.save_racer_condition,
            )
        )


def build_learning_plan(mode: str = "full") -> LearningCollectionPlan:
    normalized = str(mode or "").strip().lower()
    common = dict(
        snapshot_label="learning_all",
        window_before_min=30,
        window_after_min=0,
        collect_scope="all",
        fetch_odds3t=True,
        save_odds=True,
        decision_enabled=False,
        line_enabled=False,
        purchase_enabled=False,
    )
    if normalized == "full":
        return LearningCollectionPlan(
            mode="full",
            fetch_beforeinfo=True,
            save_weather=True,
            save_exhibition=True,
            save_entries=True,
            save_race_condition=True,
            save_racer_condition=True,
            **common,
        )
    if normalized == "odds_only":
        return LearningCollectionPlan(
            mode="odds_only",
            fetch_beforeinfo=False,
            save_weather=False,
            save_exhibition=False,
            save_entries=False,
            save_race_condition=False,
            save_racer_condition=False,
            **common,
        )
    raise ValueError(f"unsupported learning collection mode: {mode!r}")


def estimate_request_savings(target_attempts: int) -> dict[str, int]:
    """Compare page-fetch counts assuming one beforeinfo and one odds page per target."""
    attempts = max(0, int(target_attempts))
    full = build_learning_plan("full")
    odds_only = build_learning_plan("odds_only")
    full_pages = attempts * (int(full.fetch_beforeinfo) + int(full.fetch_odds3t))
    odds_only_pages = attempts * (
        int(odds_only.fetch_beforeinfo) + int(odds_only.fetch_odds3t)
    )
    return {
        "target_attempts": attempts,
        "full_page_fetches": full_pages,
        "odds_only_page_fetches": odds_only_pages,
        "avoided_beforeinfo_fetches": attempts,
        "avoided_page_fetches": full_pages - odds_only_pages,
        "retained_odds_fetches": attempts,
    }
