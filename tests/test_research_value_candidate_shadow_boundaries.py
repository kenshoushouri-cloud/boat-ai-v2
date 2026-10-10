import pytest

from research_value_candidate_shadow import Row, build_summary


def _row(odds: float, prob: float, hit: int = 0) -> Row:
    return Row("2026-09-01", f"r-{odds}-{prob}", "01", 1, "1-2-3", odds, prob, hit)


def test_exact_gate_is_included():
    summary = build_summary([_row(2.0, 0.55, 1)], gates=(1.10,), stake_yen=100)
    assert summary["by_gate"]["1.10"]["overall"]["candidates"] == 1


def test_below_supported_odds_universe_not_selected():
    summary = build_summary([_row(1.49, 0.90, 1)], gates=(1.10,), stake_yen=100)
    assert summary["by_gate"]["1.10"]["overall"]["candidates"] == 0


def test_high_odds_needs_value_not_payout_size():
    rows = [_row(20.0, 0.04, 1), _row(20.0, 0.06, 0)]
    summary = build_summary(rows, gates=(1.10,), stake_yen=100)
    selected = summary["by_gate"]["1.10"]["overall"]
    assert selected["candidates"] == 1
    assert selected["avg_value_ratio"] == pytest.approx(1.20)
