# -*- coding: utf-8 -*-
"""Self-contained offline contract tests; no DB, Railway or external calls."""
from __future__ import annotations

import unittest

from research.historical_incident_eligibility import classify_historical_incident
from research.historical_void_registry import EVIDENCE_REF, VERIFIED_VOID_RACE_IDS


def normal_entries():
    return [
        {"lane": lane, "finish_status": f"{lane:02d}", "is_flying": False, "is_late": False}
        for lane in range(1, 7)
    ]


class HistoricalIncidentEligibilityTests(unittest.TestCase):
    def test_all_71_k_confirmed_cancelled_races_void_even_if_bad_db_status(self):
        for race_id in VERIFIED_VOID_RACE_IDS:
            with self.subTest(race_id=race_id):
                d = classify_historical_incident(race_id, None, result_status="official", race_status="scheduled")
                self.assertEqual(d.state, "VERIFIED_K_VOID")
                self.assertEqual(d.primary_training_eligible, False)
                self.assertEqual(d.hypothetical_investment, 0)
                self.assertEqual(d.economics_policy, "VOID_ZERO_HYPOTHETICAL")
                self.assertEqual(d.evidence_ref, EVIDENCE_REF)
                self.assertFalse(d.historical_incident_timing_proven)

    def test_20260921_completed_mid_card_races_not_falsely_voided(self):
        for race_id in ("20260921_09_01", "20260921_09_04", "20260921_10_09"):
            with self.subTest(race_id=race_id):
                d = classify_historical_incident(race_id, normal_entries())
                self.assertEqual(d.state, "NO_INCIDENT_EVIDENCE")
                self.assertIsNone(d.primary_training_eligible)
                self.assertIsNone(d.hypothetical_investment)
                self.assertEqual(d.economics_policy, "CHECK_ALL_OTHER_GATES")

    def test_all_standard_k_status_codes_exclude_primary_fitting(self):
        sample = {
            "K0": "withdrawal", "K1": "withdrawal",
            "L0": "late", "L1": "late",
            "F": "flying",
            "S0": "incident_or_disqualification",
            "S1": "incident_or_disqualification",
            "S2": "incident_or_disqualification",
        }
        for status, category in sample.items():
            with self.subTest(status=status):
                rows = normal_entries()
                rows[0]["finish_status"] = status
                d = classify_historical_incident("20260921_09_04", rows)
                self.assertEqual(d.state, "ABNORMAL_RESULT")
                self.assertIn(category, d.categories)
                self.assertFalse(d.primary_training_eligible)
                self.assertIsNone(d.hypothetical_investment)
                self.assertEqual(d.economics_policy, "KEEP_ACTUAL_SETTLEMENT_SEPARATE")
                self.assertFalse(d.historical_incident_timing_proven)

    def test_textual_abnormalities_and_full_width_spacing(self):
        samples = {
            "欠 場": "withdrawal",
            "出走取消": "withdrawal",
            "転　覆": "incident_or_disqualification",
            "落 水": "incident_or_disqualification",
            "沈没": "incident_or_disqualification",
            "失 格": "incident_or_disqualification",
            "妨害": "incident_or_disqualification",
        }
        for status, category in samples.items():
            with self.subTest(status=status):
                rows = normal_entries()
                rows[1]["finish_status"] = status
                d = classify_historical_incident("20260921_09_04", rows)
                self.assertEqual(d.state, "ABNORMAL_RESULT")
                self.assertIn(category, d.categories)

    def test_flag_only_incidents_detected(self):
        for key, category in (("is_flying", "flying"), ("is_late", "late")):
            with self.subTest(key=key):
                rows = normal_entries()
                rows[2][key] = True
                d = classify_historical_incident("20260921_09_04", rows)
                self.assertEqual(d.state, "ABNORMAL_RESULT")
                self.assertIn(category, d.categories)

    def test_overlap_categories_do_not_overwrite_status(self):
        rows = normal_entries()
        rows[0]["finish_status"] = "K1"
        rows[1]["finish_status"] = "F"
        rows[2]["finish_status"] = "S1"
        d = classify_historical_incident("20260921_09_04", rows)
        self.assertEqual(d.state, "ABNORMAL_RESULT")
        self.assertEqual(set(d.categories), {"withdrawal", "flying", "incident_or_disqualification"})

    def test_unknown_finish_code_fails_closed(self):
        rows = normal_entries()
        rows[0]["finish_status"] = "00"
        d = classify_historical_incident("20260921_09_04", rows)
        self.assertEqual(d.state, "INSUFFICIENT_RESULT_EVIDENCE")
        self.assertIn("unknown_finish_status", d.categories)
        self.assertFalse(d.primary_training_eligible)
        self.assertEqual(d.economics_policy, "DO_NOT_INFER_SETTLEMENT")

    def test_missing_flags_and_result_status_fail_closed(self):
        rows = normal_entries()
        del rows[0]["is_flying"]
        rows[1]["finish_status"] = ""
        d = classify_historical_incident("20260921_09_04", rows)
        self.assertEqual(d.state, "INSUFFICIENT_RESULT_EVIDENCE")
        self.assertIn("unknown_incident_flag", d.categories)
        self.assertIn("missing_finish_status", d.categories)

    def test_six_unique_lanes_required(self):
        cases = (normal_entries()[:5], normal_entries()[:5] + [dict(normal_entries()[4])])
        for rows in cases:
            with self.subTest(count=len(rows)):
                d = classify_historical_incident("20260921_09_04", rows)
                self.assertEqual(d.state, "INSUFFICIENT_RESULT_EVIDENCE")
                self.assertIn("incomplete_or_duplicate_lanes", d.categories)

    def test_no_result_entries_do_not_mean_cancelled(self):
        for rows in (None, [], ()):
            with self.subTest(rows=rows):
                d = classify_historical_incident("20261005_09_05", rows)
                self.assertEqual(d.state, "INSUFFICIENT_RESULT_EVIDENCE")
                self.assertFalse(d.primary_training_eligible)
                self.assertIsNone(d.hypothetical_investment)
                self.assertNotIn("whole_race_void", d.categories)

    def test_db_cancel_flag_indicates_but_does_not_verify_official_k_void(self):
        for status in ("CANCELLED", "canceled"):
            with self.subTest(status=status):
                d = classify_historical_incident("20261005_09_05", [], result_status=status, race_status="scheduled")
                self.assertEqual(d.state, "DB_CANCELLATION_INDICATED")
                self.assertFalse(d.primary_training_eligible)
                self.assertIsNone(d.hypothetical_investment)
                self.assertEqual(d.economics_policy, "KEEP_ACTUAL_SETTLEMENT_SEPARATE")
                self.assertEqual(d.evidence_ref, "v2_results_postrace_status")

    def test_bad_race_ids_rejected(self):
        for race_id in (None, 9, "", "20260921_09_00", "20260921_09_13", "20260921_9_04", "2026-09-21_09_04"):
            with self.subTest(race_id=race_id):
                with self.assertRaises(ValueError):
                    classify_historical_incident(race_id, normal_entries())

    def test_abnormal_result_only_never_claims_pre_deadline_knowledge(self):
        for status in ("F", "K0", "S1"):
            rows = normal_entries()
            rows[0]["finish_status"] = status
            d = classify_historical_incident("20260921_10_09", rows)
            self.assertFalse(d.historical_incident_timing_proven)
            self.assertIsNone(d.hypothetical_investment)


if __name__ == "__main__":
    unittest.main()
