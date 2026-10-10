# -*- coding: utf-8 -*-
from pathlib import Path


def test_recent_form_readiness_is_read_only_and_pre_outcome():
    s = Path("research/v51_recent_form_readiness_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "return_yen",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in s


def test_candidate_contract_is_frozen():
    s = Path("research/v51_recent_form_readiness_pg.py").read_text(encoding="utf-8")
    assert "V51_RECENT_FORM_LAST5_TOP3_V1" in s
    assert "minimum_valid_finishes_per_lane" in s
    assert "at_least_2_valid_lanes_and_nonzero_stddev" in s
    assert "official_k_file" in s
