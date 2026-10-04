# -*- coding: utf-8 -*-
from pathlib import Path

import research.v51_recent_form_blind_val_oos_pg as rf


def test_frozen_coefficient_and_populations():
    assert rf.COEFFICIENT == 0.30
    assert rf.TRAIN_FREEZE_SHA256 == "7b53c68c22ef351b85293205395938c12705ca87f03b50be9d87f196a95c3c9c"
    assert rf.SPLITS["VALIDATION"]["expected_population"] == 28178
    assert rf.SPLITS["OOS"]["expected_population"] == 14492


def test_no_search_odds_payout_or_db_write():
    s = Path("research/v51_recent_form_blind_val_oos_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    assert "v2_odds" not in s
    assert "payout_yen" not in s
    assert "trifecta_payout" not in s
    for token in ("insert into", "update v2_", "delete from"):
        assert token not in s


def test_gate_is_exactly_preregistered_rule():
    base = {
        "mean_logloss": 1.0,
        "mean_multiclass_brier": 0.9,
        "mean_official_ticket_rank": 20.0,
    }
    good = {
        "mean_logloss": 0.99,
        "mean_multiclass_brier": 0.89,
        "mean_official_ticket_rank": 20.0,
    }
    bad_rank = dict(good, mean_official_ticket_rank=20.01)
    assert rf.gate(base, good)["pass"] is True
    assert rf.gate(base, bad_rank)["pass"] is False
