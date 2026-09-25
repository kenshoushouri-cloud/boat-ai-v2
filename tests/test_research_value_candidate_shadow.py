import json
from pathlib import Path

import pytest

from research_value_candidate_shadow import Row, _band, build_summary, load_rows, stats


def test_odds_bands_include_low_and_high_ranges():
    assert _band(1.50) == "1.5-2.0"
    assert _band(1.99) == "1.5-2.0"
    assert _band(2.00) == "2.0-3.0"
    assert _band(2.99) == "2.0-3.0"
    assert _band(3.00) == "3.0-5.5"
    assert _band(5.50) == "5.5-10.0"
    assert _band(20.00) == "20.0+"
    assert _band(1.49) is None


def test_low_odds_positive_value_is_not_excluded():
    row = Row(
        race_date="2026-09-01",
        race_id="r1",
        venue_id="01",
        race_no=1,
        ticket="1-2-3",
        odds=2.0,
        prob=0.60,
        hit=1,
    )
    assert row.value_ratio == pytest.approx(1.20)
    assert row.edge == pytest.approx(0.10)
    summary = build_summary([row], gates=(1.10,), stake_yen=100)
    gate = summary["by_gate"]["1.10"]["overall"]
    assert gate["candidates"] == 1
    assert gate["roi"] == pytest.approx(2.0)
    assert gate["profit_yen"] == pytest.approx(100.0)


def test_same_low_odds_without_value_is_rejected_by_gate():
    row = Row(
        race_date="2026-09-01",
        race_id="r1",
        venue_id="01",
        race_no=1,
        ticket="1-2-3",
        odds=2.0,
        prob=0.52,
        hit=1,
    )
    summary = build_summary([row], gates=(1.10,), stake_yen=100)
    gate = summary["by_gate"]["1.10"]["overall"]
    assert gate["candidates"] == 0


def test_stats_profit_and_losing_streak():
    rows = [
        Row("2026-09-01", "r1", "01", 1, "1-2-3", 2.0, 0.60, 0),
        Row("2026-09-01", "r2", "01", 2, "1-2-3", 2.0, 0.60, 0),
        Row("2026-09-01", "r3", "01", 3, "1-2-3", 2.0, 0.60, 1),
    ]
    out = stats(rows, stake_yen=100)
    assert out["candidates"] == 3
    assert out["hits"] == 1
    assert out["turnover_yen"] == 300
    assert out["payout_yen"] == pytest.approx(200.0)
    assert out["profit_yen"] == pytest.approx(-100.0)
    assert out["roi"] == pytest.approx(2.0 / 3.0)
    assert out["longest_losing_streak"] == 2


def test_loader_rejects_invalid_probability(tmp_path: Path):
    p = tmp_path / "rows.csv"
    p.write_text(
        "race_date,race_id,venue_id,race_no,ticket,odds,prob,hit\n"
        "2026-09-01,r1,01,1,1-2-3,2.0,1.2,1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid prob"):
        load_rows(p)


def test_summary_has_no_action_flags():
    out = build_summary([], gates=(1.10,), stake_yen=100)
    assert out["meta"]["production_write"] is False
    assert out["meta"]["line_send"] is False
    assert out["meta"]["purchase_action"] is False
