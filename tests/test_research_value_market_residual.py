from datetime import date

import pytest

from research_value_candidate_shadow import Row
from research_value_market_residual import TICKETS, complete_races, residual_gate


def make_race(race_date: str, race_id: str, actual: str, model_good: bool) -> list[Row]:
    rows = []
    for ticket in TICKETS:
        hit = int(ticket == actual)
        if model_good:
            prob = 0.50 if hit else 0.50 / 119.0
        else:
            # Put very little mass on the actual ticket so market-only should win.
            prob = 0.0001 if hit else (1.0 - 0.0001) / 119.0
        rows.append(
            Row(
                race_date=race_date,
                race_id=race_id,
                venue_id="01",
                race_no=1,
                ticket=ticket,
                odds=120.0,
                prob=prob,
                hit=hit,
            )
        )
    return rows


def test_complete_race_contract_requires_all_120_tickets():
    rows = make_race("2026-08-01", "r1", "1-2-3", True)
    races, coverage = complete_races(rows)
    assert len(races) == 1
    assert coverage["complete_races"] == 1

    races2, coverage2 = complete_races(rows[:-1])
    assert races2 == []
    assert coverage2["skipped_incomplete"] == 1


def test_train_selected_positive_alpha_can_support_future_market_residual():
    rows = []
    rows += make_race("2026-08-01", "train1", "1-2-3", True)
    rows += make_race("2026-08-02", "train2", "2-1-3", True)
    rows += make_race("2026-09-01", "test1", "3-1-2", True)

    out = residual_gate(
        rows,
        train_end=date(2026, 8, 31),
        test_start=date(2026, 9, 1),
        test_end=date(2026, 9, 30),
    )
    assert out["selected_alpha"] == pytest.approx(1.0)
    assert out["oos_residual_support"] is True
    assert out["selected_minus_market"]["logloss"] < 0
    assert out["selected_minus_market"]["brier"] < 0
    assert out["promotion_allowed"] is False


def test_bad_model_selects_market_only_and_fails_residual_gate():
    rows = []
    rows += make_race("2026-08-01", "train1", "1-2-3", False)
    rows += make_race("2026-08-02", "train2", "2-1-3", False)
    rows += make_race("2026-09-01", "test1", "3-1-2", False)

    out = residual_gate(
        rows,
        train_end=date(2026, 8, 31),
        test_start=date(2026, 9, 1),
        test_end=date(2026, 9, 30),
    )
    assert out["selected_alpha"] == pytest.approx(0.0)
    assert out["oos_residual_support"] is False
    assert out["status"] == "MARKET_RESIDUAL_NOT_ESTABLISHED"


def test_insufficient_future_data_fails_closed():
    rows = make_race("2026-08-01", "train1", "1-2-3", True)
    out = residual_gate(
        rows,
        train_end=date(2026, 8, 31),
        test_start=date(2026, 9, 1),
        test_end=date(2026, 9, 30),
    )
    assert out["status"] == "INSUFFICIENT_COMPLETE_TRAIN_OR_TEST_RACES"
    assert out["oos_residual_support"] is False
    assert out["promotion_allowed"] is False
