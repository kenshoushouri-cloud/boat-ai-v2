# -*- coding: utf-8 -*-
from pathlib import Path

from research.matched_contract_selection_freeze_pg import motor_ticket_score


def test_motor_score_uses_frozen_position_weights():
    motor = {1: 60.0, 2: 50.0, 3: 40.0, 4: 30.0, 5: 20.0, 6: 10.0}
    assert motor_ticket_score("1-2-3", motor) > 0
    assert motor_ticket_score("6-5-4", motor) < 0


def test_selection_freeze_has_no_outcome_or_odds_access():
    source = Path("research/matched_contract_selection_freeze_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "set transaction read only" in source
    assert "selection_outcome_read" in source
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "trifecta_payout",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in source
