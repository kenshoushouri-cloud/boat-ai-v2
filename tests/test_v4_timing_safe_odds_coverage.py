# -*- coding: utf-8 -*-
from pathlib import Path


def test_coverage_ladder_has_no_outcome_surface():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_timing_safe_odds_coverage_pg.py"
    ).read_text(encoding="utf-8").lower()
    assert "set transaction read only" in source
    assert "v2_realtime_odds_snapshots" in source
    assert "v2_results" not in source
    assert "trifecta_payout" not in source
    assert "purchase_action": false" in source
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in source
