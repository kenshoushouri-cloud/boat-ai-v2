# -*- coding: utf-8 -*-
from pathlib import Path


def test_inventory_is_hard_read_only_and_deadline_contract_is_explicit():
    text = Path("research/historical_point_in_time_inventory_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in text
    assert "default_transaction_read_only=on" in text
    assert "strictly_available_before_target_race_deadline" in text
    assert "current_value_substitution_allowed" in text
    assert "target_race_outcome_as_feature_allowed" in text
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "create table",
        "alter table",
        "drop table",
        "send_line",
    ):
        assert forbidden not in text, forbidden


def test_no_odds_source_is_used():
    text = Path("research/historical_point_in_time_inventory_pg.py").read_text(encoding="utf-8").lower()
    assert "v2_odds" not in text
    assert '"odds_read": false' in text
