# -*- coding: utf-8 -*-
from pathlib import Path

import research.v51_exhibition_time_oos_gap_diagnosis_pg as d


def test_period_is_oos_only():
    assert d.START.isoformat() == "2026-07-01"
    assert d.END.isoformat() == "2026-09-30"


def test_read_only_no_outcome():
    s = Path("research/v51_exhibition_time_oos_gap_diagnosis_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "trifecta_payout",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in s
