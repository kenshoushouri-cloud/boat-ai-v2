# -*- coding: utf-8 -*-
from pathlib import Path

import research.v51_recent_form_train_fit_pg as rf


def test_grid_is_exactly_frozen_11_values():
    assert rf.GRID == (-0.50, -0.40, -0.30, -0.20, -0.10, 0.00, 0.10, 0.20, 0.30, 0.40, 0.50)


def test_train_dates_are_hard_locked():
    assert rf.TRAIN_START.isoformat() == "2025-07-01"
    assert rf.TRAIN_END.isoformat() == "2025-12-31"
    assert rf.EXPECTED_PREOUTCOME_POPULATION == 26801


def test_script_does_not_query_validation_oos_odds_or_payout():
    s = Path("research/v51_recent_form_train_fit_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    assert "v2_odds" not in s
    assert "payout_yen" not in s
    assert "trifecta_payout" not in s
    assert "2026-01-01" not in s
    assert "2026-06-30" not in s
    assert "2026-07-01" not in s
    assert "2026-09-30" not in s
    for token in ("insert into", "update v2_", "delete from"):
        assert token not in s


def test_recent_form_requires_strict_prior_day():
    entries = [
        {
            "lane": 1,
            "recent_form": [
                {"source": "official_k_file", "race_date": "2025-06-30", "finish_position": 1},
                {"source": "official_k_file", "race_date": "2025-06-29", "finish_position": 4},
                {"source": "official_k_file", "race_date": "2025-06-28", "finish_position": 3},
            ],
        },
        {
            "lane": 2,
            "recent_form": [
                {"source": "official_k_file", "race_date": "2025-06-30", "finish_position": 6},
                {"source": "official_k_file", "race_date": "2025-06-29", "finish_position": 5},
                {"source": "official_k_file", "race_date": "2025-06-28", "finish_position": 4},
            ],
        },
    ]
    z = rf.recent_feature(entries, rf.TRAIN_START)
    assert set(z) == {1, 2}
    assert z[1] > 0 and z[2] < 0

    entries[0]["recent_form"][0]["race_date"] = "2025-07-01"
    z2 = rf.recent_feature(entries, rf.TRAIN_START)
    assert z2 == {}
