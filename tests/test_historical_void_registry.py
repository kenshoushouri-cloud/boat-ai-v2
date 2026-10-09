# -*- coding: utf-8 -*-
"""Offline tests: never require a DB or external services."""
import unittest

from research.historical_void_registry import (
    VERIFIED_VOID_RACE_IDS,
    EVIDENCE_REF,
    classify_historical_void,
)


class TestOfficialKVoidRegistry(unittest.TestCase):
    def test_exactly_71_officially_confirmed_ids(self):
        self.assertEqual(len(VERIFIED_VOID_RACE_IDS), 71)
        self.assertEqual(len(set(VERIFIED_VOID_RACE_IDS)), 71)

    def test_all_groups_and_boundaries(self):
        groups = (
            ("20260811", "03", range(1, 13)),
            ("20260909", "03", range(1, 13)),
            ("20260921", "02", range(1, 13)),
            ("20260921", "03", range(1, 13)),
            ("20260921", "09", range(5, 13)),
            ("20260921", "10", range(10, 13)),
            ("20260922", "09", range(1, 13)),
        )
        expected = {f"{day}_{venue}_{n:02d}" for day, venue, nums in groups for n in nums}
        self.assertEqual(VERIFIED_VOID_RACE_IDS, frozenset(expected))

    def test_20260921_completed_races_preserved(self):
        for rid in ("20260921_09_01", "20260921_09_04", "20260921_10_09"):
            with self.subTest(rid=rid):
                decision = classify_historical_void(rid)
                self.assertEqual(decision.state, "UNDETERMINED")
                self.assertIsNone(decision.primary_training_eligible)
                self.assertIsNone(decision.hypothetical_investment)

    def test_void_is_training_excluded_with_zero_hypothetical_investment(self):
        for rid in VERIFIED_VOID_RACE_IDS:
            with self.subTest(rid=rid):
                decision = classify_historical_void(rid)
                self.assertEqual(decision.state, "VERIFIED_VOID")
                self.assertFalse(decision.primary_training_eligible)
                self.assertEqual(decision.backtest_treatment, "VOID")
                self.assertEqual(decision.hypothetical_investment, 0)
                self.assertEqual(decision.evidence_ref, EVIDENCE_REF)

    def test_other_race_not_automatically_eligible(self):
        decision = classify_historical_void("20261005_09_05")
        self.assertEqual(decision.state, "UNDETERMINED")
        self.assertEqual(decision.backtest_treatment, "CHECK_OTHER_ELIGIBILITY")
        self.assertIsNone(decision.primary_training_eligible)

    def test_reject_non_string_ids(self):
        with self.assertRaises(TypeError):
            classify_historical_void(None)


if __name__ == "__main__":
    unittest.main()
