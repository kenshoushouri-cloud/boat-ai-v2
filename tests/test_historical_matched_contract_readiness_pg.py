# -*- coding: utf-8 -*-
import unittest
from datetime import date
from pathlib import Path

from research.historical_matched_contract_readiness_pg import (
    HISTORICAL_OPPONENT_MODEL_VERSION,
    COURSE_PROXY_SOURCE,
    expected_course_snapshot,
    opponent_valid,
)


class HistoricalMatchedContractReadinessTests(unittest.TestCase):
    def test_fixed_course_application_terms(self):
        self.assertEqual(
            COURSE_PROXY_SOURCE,
            "boatrace_official_k_applied_term_proxy",
        )
        self.assertEqual(expected_course_snapshot(date(2025, 7, 1)), date(2025, 4, 30))
        self.assertEqual(expected_course_snapshot(date(2025, 12, 31)), date(2025, 4, 30))
        self.assertEqual(expected_course_snapshot(date(2026, 1, 1)), date(2025, 10, 31))
        self.assertEqual(expected_course_snapshot(date(2026, 6, 30)), date(2025, 10, 31))
        self.assertEqual(expected_course_snapshot(date(2026, 7, 1)), date(2026, 4, 30))
        self.assertEqual(expected_course_snapshot(date(2026, 9, 29)), date(2026, 4, 30))

    def test_historical_opponent_requires_strict_prior_and_complete_arrays(self):
        good = {
            "model_version": HISTORICAL_OPPONENT_MODEL_VERSION,
            "race_date": date(2026, 9, 29),
            "train_end": date(2026, 9, 28),
            "matched_opponents": [4, 5, 6, 4, 8, 5],
            "base_win": [0.2, 0.18, 0.17, 0.16, 0.15, 0.14],
            "adj_win": [0.21, 0.17, 0.18, 0.15, 0.16, 0.13],
        }
        self.assertTrue(opponent_valid(good))
        self.assertFalse(opponent_valid(dict(good, train_end=date(2026, 9, 29))))
        self.assertFalse(opponent_valid(dict(good, matched_opponents=[4, 5, 3, 4, 8, 5])))
        self.assertFalse(opponent_valid(dict(good, model_version=2)))

    def test_script_is_result_blind(self):
        source = Path("research/historical_matched_contract_readiness_pg.py").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("set transaction read only", source)
        for token in (
            "v2_results",
            "v2_result_entries",
            "v2_odds",
            "payout_yen",
            "return_yen",
            "hit_rate",
            "insert into",
            "update v2_",
            "delete from",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
