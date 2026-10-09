# -*- coding: utf-8 -*-
"""Offline provenance safety regression. No Postgres/Railway/network."""
from __future__ import annotations
import unittest
from copy import deepcopy

from research.v5_strong_core_exhibition_predeadline_gate import (
    FROZEN_TABLE, check_frozen_exhibition_predeadline,
)

RACE = "20261009_09_04"
DEADLINE = "2026-10-09T12:00:00+09:00"
CUTOFF = "2026-10-09T11:55:00+09:00"


def valid_row():
    return {
        "race_id": RACE,
        "captured_at": "2026-10-09T11:50:00+09:00",
        "deadline_at": DEADLINE,
        "minutes_before": 10.0,
        "source": "official_beforeinfo",
        "exhibition_time_ranks": [4, 1, 2, 3, 6, 5],
        "exhibition_times": [6.88, 6.77, 6.83, 6.85, 6.91, 6.90],
    }


def run_gate(row=None, **overrides):
    args = dict(
        race_id=RACE,
        frozen_row=valid_row() if row is None else row,
        source_table=FROZEN_TABLE,
        official_deadline_at=DEADLINE,
        prediction_cutoff_at=CUTOFF,
    )
    args.update(overrides)
    return check_frozen_exhibition_predeadline(**args)


class TestV5StrongCoreFrozenExhibition(unittest.TestCase):
    def deny(self, reason, row=None, **overrides):
        result = run_gate(row=row, **overrides)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["scope"], "exhibition_only")

    def test_valid_immutable_official_six_boat_10_min_window(self):
        self.assertEqual(run_gate(), {"eligible": True, "reason": "FROZEN_OFFICIAL_BEFORE_CUTOFF", "scope": "exhibition_only"})

    def test_mutable_historical_table_is_not_prospective_proof(self):
        self.deny("MUTABLE_OR_UNVERIFIED_SOURCE", source_table="v2_realtime_exhibition_snapshots")

    def test_not_present_or_other_race(self):
        self.deny("MISSING_FROZEN_ROW", row={})
        bad=valid_row();bad["race_id"]="20261009_09_05"
        self.deny("RACE_ID_MISMATCH", row=bad)

    def test_only_official_first_capture_source(self):
        bad=valid_row();bad["source"]="historical_reconstruction"
        self.deny("UNVERIFIED_OFFICIAL_SOURCE", row=bad)

    def test_deadline_must_match_independent_race_record(self):
        self.deny("DEADLINE_MISMATCH", official_deadline_at="2026-10-09T12:01:00+09:00")

    def test_timestamp_must_have_timezone_and_parse(self):
        bad=valid_row();bad["captured_at"]="2026-10-09T11:50:00"
        self.deny("MISSING_OR_UNZONED_TIME", row=bad)
        bad["captured_at"]="not-a-date"
        self.deny("MISSING_OR_UNZONED_TIME", row=bad)

    def test_cannot_take_exhibition_after_prediction_cutoff(self):
        self.deny("NOT_CAPTURED_BEFORE_CUTOFF", prediction_cutoff_at="2026-10-09T11:49:00+09:00")
        self.deny("NOT_CAPTURED_BEFORE_CUTOFF", prediction_cutoff_at="2026-10-09T12:01:00+09:00")

    def test_capture_window_must_be_8_to_15_minutes(self):
        bad=valid_row();bad["captured_at"]="2026-10-09T11:44:00+09:00"
        self.deny("OUTSIDE_FROZEN_CAPTURE_WINDOW", row=bad)
        bad["captured_at"]="2026-10-09T11:53:00+09:00"
        self.deny("OUTSIDE_FROZEN_CAPTURE_WINDOW", row=bad, prediction_cutoff_at="2026-10-09T11:55:00+09:00")

    def test_stored_minutes_does_not_override_real_clock(self):
        bad=valid_row();bad["minutes_before"]=12.0
        self.deny("STORED_WINDOW_CONFLICT", row=bad)
        bad["minutes_before"]=float("nan")
        self.deny("INVALID_STORED_WINDOW", row=bad)

    def test_incomplete_rank_set(self):
        bad=valid_row();bad["exhibition_time_ranks"]=[1,2,3,4,5]
        self.deny("INCOMPLETE_SIX_LANE_RANKS", row=bad)

    def test_duplicate_or_noninteger_rank(self):
        bad=valid_row();bad["exhibition_time_ranks"]=[1,2,3,4,5,5]
        self.deny("INVALID_SIX_LANE_RANKS", row=bad)
        bad["exhibition_time_ranks"]=[1,2,3,4,5,"6"]
        self.deny("INVALID_SIX_LANE_RANKS", row=bad)

    def test_missing_or_zero_exhibition_times(self):
        bad=valid_row();bad["exhibition_times"]=[6.8]*5
        self.deny("INCOMPLETE_SIX_LANE_TIMES", row=bad)
        bad["exhibition_times"]=[6.8]*5+[0]
        self.deny("INVALID_SIX_LANE_TIMES", row=bad)

    def test_nonfinite_time_is_rejected(self):
        bad=valid_row();bad["exhibition_times"]=[6.8]*5+[float("inf")]
        self.deny("INVALID_SIX_LANE_TIMES", row=bad)


if __name__=="__main__":
    unittest.main()
