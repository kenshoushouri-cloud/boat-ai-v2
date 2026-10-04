# -*- coding: utf-8 -*-
from pathlib import Path


def test_opponent_provenance_diagnostic_is_result_blind_and_read_only():
    source = Path("research/opponent_provenance_readiness_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "set transaction read only" in source
    assert "opponent_provenance" in source
    assert "left join v2_opponent_pressure_shadow_v2" in source
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in source
