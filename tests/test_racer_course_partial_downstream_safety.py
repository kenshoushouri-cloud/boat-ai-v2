# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

import collect_racer_course_top3_forward_shadow_pg as forward
import feature_lab_no_odds_pg as feature_lab
import v22_racer_course_shadow_pg as legacy_shadow


class RacerCoursePartialDownstreamSafetyTests(unittest.TestCase):
    def test_forward_source_rejects_missing_top3(self):
        row = {
            "course_snapshot_created_at": datetime(2026, 9, 10, 7, 30, tzinfo=forward.JST),
            "course_source": "boatrace_official_racer_course",
            "course_top3_rate": None,
        }
        deadline = datetime(2026, 9, 10, 12, 0, tzinfo=forward.JST)
        self.assertFalse(forward._source_row_safe(row, deadline))

    def test_forward_distribution_fails_closed_if_any_lane_top3_missing(self):
        entries = []
        for lane in range(1, 7):
            entries.append({
                "lane": lane,
                "racer_class": 1,
                "national_win_rate": 6.0,
                "national_place2_rate": 40.0,
                "local_place2_rate": 40.0,
                "avg_st": 0.15,
                "course_top3_rate": None if lane == 3 else 50.0 + lane,
            })
        with self.assertRaises(RuntimeError):
            forward._distribution(entries, "01", forward.FIXED_COEF)

    def test_legacy_shadow_missing_metrics_are_neutral_not_zero_signal(self):
        stat = {"entry_rate": None, "top3_rate": None, "avg_st": None}
        self.assertAlmostEqual(0.0, legacy_shadow._course_adjustment(stat), places=12)

    def test_feature_lab_missing_metrics_are_neutral_not_zero_signal(self):
        stat = {"entry_rate": None, "top3_rate": None, "avg_st": None}
        self.assertAlmostEqual(0.0, feature_lab.racer_course_adjustment(stat), places=12)


if __name__ == "__main__":
    unittest.main()
