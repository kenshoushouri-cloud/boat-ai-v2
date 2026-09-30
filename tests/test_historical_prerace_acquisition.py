# -*- coding: utf-8 -*-
from datetime import date
import pytest

from research.historical_prerace_acquisition import (
    DEFAULT_SOURCES,
    build_summary,
    iter_dates,
    source_url,
    FetchRecord,
)


def test_one_chunk_is_max_31_days():
    assert len(list(iter_dates(date(2025, 7, 1), date(2025, 7, 31)))) == 31
    with pytest.raises(ValueError):
        list(iter_dates(date(2025, 7, 1), date(2025, 8, 1)))


def test_source_url_is_date_scoped_program_archive():
    assert source_url("race_cards", date(2025, 7, 1)) == (
        "https://boatracecsv.github.io/data/programs/race_cards/2025/07/01.csv"
    )


def test_default_sources_never_include_results_odds_or_payouts():
    joined = " ".join(DEFAULT_SOURCES).lower()
    assert "result" not in joined
    assert "odds" not in joined
    assert "payout" not in joined


def test_summary_counts_ok_missing_error():
    rows = [
        FetchRecord("2025-07-01", "race_cards", "u", "OK", 200, 10, 2, "a"*64, "p", None),
        FetchRecord("2025-07-02", "race_cards", "u", "MISSING_404", 404, 0, None, None, None, None),
        FetchRecord("2025-07-03", "race_cards", "u", "ERROR", None, 0, None, None, None, "x"),
    ]
    out = build_summary(rows)
    s = out["by_source"]["race_cards"]
    assert s["requested_days"] == 3
    assert s["ok_days"] == 1
    assert s["missing_days"] == 1
    assert s["error_days"] == 1
    assert s["coverage_pct"] == 33.33
