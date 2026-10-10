# -*- coding: utf-8 -*-
from pathlib import Path


def test_course_cohort_comparison_freezes_before_result_query():
    s = Path("research/v4_course_neutral_cohort_comparison_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    marker = "# outcome_query_boundary"
    assert marker in s
    before, after = s.split(marker, 1)
    assert "v2_results" not in before
    assert "trifecta_payout" not in before
    assert "v2_odds" not in s
    assert "v2_results" in after
    assert "set transaction read only" in s
    for token in ("insert into", "update v2_", "delete from"):
        assert token not in s
