# -*- coding: utf-8 -*-
from datetime import date

from research.historical_course_term_seed_pg import (
    SOURCE,
    TERM_SPECS,
    aggregate_entries,
    build_rows,
)


def test_2025h2_training_period_ends_before_application():
    x = TERM_SPECS["2025H2"]
    assert x.training_end == date(2025, 4, 30)
    assert x.application_start == date(2025, 7, 1)
    assert x.training_end < x.application_start


def test_course_proxy_uses_only_prior_training_entries():
    acc = {}
    aggregate_entries(
        [
            {
                "entries": [
                    {"racer_number": 4601, "start_course": 1, "finish_position": 1, "start_timing": 0.14},
                    {"racer_number": 4601, "start_course": 1, "finish_position": 4, "start_timing": 0.16},
                    {"racer_number": 4601, "start_course": 2, "finish_position": 3, "start_timing": 0.18},
                ]
            }
        ],
        acc,
    )
    rows = build_rows(acc, TERM_SPECS["2025H2"])
    by_course = {r["course"]: r for r in rows}
    assert round(by_course[1]["entry_rate"], 4) == 66.6667
    assert by_course[1]["top3_rate"] == 50.0
    assert by_course[1]["avg_st"] == 0.15
    assert round(by_course[2]["entry_rate"], 4) == 33.3333
    assert by_course[2]["top3_rate"] == 100.0
    assert by_course[1]["source"] == SOURCE
    assert by_course[1]["raw"]["historical_reconstruction"] is True
    assert by_course[1]["raw"]["prospective_evidence"] is False
