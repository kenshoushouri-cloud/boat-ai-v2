# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from research.learning_odds_only_contract import (
    build_learning_plan,
    estimate_request_savings,
)


def test_full_learning_contract_matches_current_intent():
    plan = build_learning_plan("full")
    assert plan.snapshot_label == "learning_all"
    assert plan.collect_scope == "all"
    assert plan.window_before_min == 30
    assert plan.window_after_min == 0
    assert plan.fetch_beforeinfo is True
    assert plan.fetch_odds3t is True
    assert plan.save_odds is True
    assert plan.non_odds_write_paths == 5
    assert plan.decision_enabled is False
    assert plan.line_enabled is False
    assert plan.purchase_enabled is False


def test_odds_only_preserves_market_sample_contract_and_skips_beforeinfo_paths():
    plan = build_learning_plan("odds_only")
    assert plan.snapshot_label == "learning_all"
    assert plan.collect_scope == "all"
    assert (plan.window_before_min, plan.window_after_min) == (30, 0)
    assert plan.fetch_odds3t is True
    assert plan.save_odds is True
    assert plan.fetch_beforeinfo is False
    assert plan.non_odds_write_paths == 0
    assert plan.decision_enabled is False
    assert plan.line_enabled is False
    assert plan.purchase_enabled is False


def test_odds_only_changes_only_non_odds_collection_surface():
    full = build_learning_plan("full")
    odds = build_learning_plan("odds_only")
    stable_fields = (
        "snapshot_label",
        "window_before_min",
        "window_after_min",
        "collect_scope",
        "fetch_odds3t",
        "save_odds",
        "decision_enabled",
        "line_enabled",
        "purchase_enabled",
    )
    for field in stable_fields:
        assert getattr(full, field) == getattr(odds, field)
    assert full.fetch_beforeinfo is True and odds.fetch_beforeinfo is False
    assert full.non_odds_write_paths == 5
    assert odds.non_odds_write_paths == 0


def test_request_savings_are_one_beforeinfo_page_per_target_attempt():
    result = estimate_request_savings(80)
    assert result == {
        "target_attempts": 80,
        "full_page_fetches": 160,
        "odds_only_page_fetches": 80,
        "avoided_beforeinfo_fetches": 80,
        "avoided_page_fetches": 80,
        "retained_odds_fetches": 80,
    }


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        build_learning_plan("disabled")
