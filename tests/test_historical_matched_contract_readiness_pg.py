# -*- coding: utf-8 -*-
from datetime import date

from research.historical_matched_contract_readiness_pg import (
    HISTORICAL_OPPONENT_MODEL_VERSION,
    COURSE_PROXY_SOURCE,
    expected_course_snapshot,
    opponent_valid,
)


def test_fixed_course_application_terms():
    assert COURSE_PROXY_SOURCE == "boatrace_official_k_applied_term_proxy"
    assert expected_course_snapshot(date(2025, 7, 1)) == date(2025, 4, 30)
    assert expected_course_snapshot(date(2025, 12, 31)) == date(2025, 4, 30)
    assert expected_course_snapshot(date(2026, 1, 1)) == date(2025, 10, 31)
    assert expected_course_snapshot(date(2026, 6, 30)) == date(2025, 10, 31)
    assert expected_course_snapshot(date(2026, 7, 1)) == date(2026, 4, 30)
    assert expected_course_snapshot(date(2026, 9, 29)) == date(2026, 4, 30)


def test_historical_opponent_requires_strict_prior_and_complete_arrays():
    good = {
        "model_version": HISTORICAL_OPPONENT_MODEL_VERSION,
        "race_date": date(2026, 9, 29),
        "train_end": date(2026, 9, 28),
        "matched_opponents": [4, 5, 6, 4, 8, 5],
        "base_win": [0.2, 0.18, 0.17, 0.16, 0.15, 0.14],
        "adj_win": [0.21, 0.17, 0.18, 0.15, 0.16, 0.13],
    }
    assert opponent_valid(good)

    same_day = dict(good, train_end=date(2026, 9, 29))
    assert not opponent_valid(same_day)

    low_match = dict(good, matched_opponents=[4, 5, 3, 4, 8, 5])
    assert not opponent_valid(low_match)

    wrong_model = dict(good, model_version=2)
    assert not opponent_valid(wrong_model)


def test_script_is_result_blind():
    from pathlib import Path

    source = Path("research/historical_matched_contract_readiness_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "set transaction read only" in source
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "return_yen",
        "hit_rate",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in source
