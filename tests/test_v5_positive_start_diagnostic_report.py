"""Offline-only tests: no requests, Railway, DB, sessions or official race GET."""
import dataclasses
import unittest

from v5.positive_start_diagnostic_preflight import PreflightResult
from v5.positive_start_diagnostic_report import (
    OfflineDiagnosticReport, prepare_offline_diagnostic_report,
)

RACE = "20261011_03_02"
PREVIEW = "PREFLIGHT_ONLY_NOT_LIVE_AUTHORIZATION"


class OfflineDiagnosticReportTests(unittest.TestCase):
    def test_no_result_fails_closed(self):
        self.assertEqual(
            prepare_offline_diagnostic_report(None).reason_code,
            "UNTRUSTED_PREFLIGHT_RESULT")

    def test_foreign_object_fails_closed(self):
        self.assertFalse(prepare_offline_diagnostic_report(
            {"forward_eligible": True, "race_id": RACE}).forward_eligible)

    def test_default_production_denial_is_reported(self):
        r = prepare_offline_diagnostic_report(PreflightResult(
            "NO_AUTHORITATIVE_SCHEMA", RACE))
        self.assertEqual(r.reason_code, "NO_AUTHORITATIVE_SCHEMA")
        self.assertEqual(r.race_id, RACE)
        self.assertEqual(r.proposed_get_count, 0)
        self.assertEqual(r.attempted_gets, 0)

    def test_offline_fixture_preview_never_authorizes(self):
        p = PreflightResult(PREVIEW, RACE, True, 2)
        r = prepare_offline_diagnostic_report(p)
        self.assertTrue(r.preflight_conditions_met)
        self.assertEqual(r.proposed_get_count, 2)
        self.assertEqual(r.status, "HARD_HOLD_NO_LIVE_DIAGNOSTIC")
        for name in ("diagnostic_live_get_authorized",
                     "source_bytes_independently_authenticated",
                     "original_first_observation_proven",
                     "six_active_starts_confirmed",
                     "beforeinfo_first_write_eligible",
                     "forward_eligible", "persistence_performed"):
            with self.subTest(name=name):
                self.assertIs(getattr(r, name), False)

    def test_frozen_cannot_mutate_forward_flag(self):
        r = prepare_offline_diagnostic_report(PreflightResult(PREVIEW, RACE, True, 1))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.forward_eligible = True
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.proposed_get_count = 3

    def test_bad_reason_is_not_reflected(self):
        r = prepare_offline_diagnostic_report(PreflightResult(
            "sensitive page contents or actor-supplied status", RACE))
        self.assertEqual(r.reason_code, "UNTRUSTED_PREFLIGHT_RESULT")
        self.assertIsNone(r.race_id)

    def test_inconsistent_preflight_rejected(self):
        for p in (PreflightResult(PREVIEW, RACE, False, 2),
                  PreflightResult(PREVIEW, RACE, True, 0),
                  PreflightResult(PREVIEW, RACE, True, 3),
                  PreflightResult("NO_AUTHORITATIVE_SCHEMA", RACE, True, 2),
                  PreflightResult("NO_AUTHORITATIVE_SCHEMA", RACE, False, 1)):
            with self.subTest(p=p):
                self.assertEqual(
                    prepare_offline_diagnostic_report(p).reason_code,
                    "UNTRUSTED_PREFLIGHT_RESULT")

    def test_completed_edogawa_never_produces_preview(self):
        p = PreflightResult(PREVIEW, "20261010_03_01", True, 2)
        self.assertEqual(
            prepare_offline_diagnostic_report(p).reason_code,
            "UNTRUSTED_PREFLIGHT_RESULT")

    def test_invalid_identity_and_date_sanitized(self):
        for race in ("name=John", "20261340_03_02", "", None):
            with self.subTest(race=race):
                r = prepare_offline_diagnostic_report(PreflightResult(
                    "NO_AUTHORITATIVE_SCHEMA", race))
                self.assertIsNone(r.race_id)

    def test_forged_positive_flag_is_rejected(self):
        p = PreflightResult(PREVIEW, RACE, True, 2)
        object.__setattr__(p, "forward_eligible", True)
        r = prepare_offline_diagnostic_report(p)
        self.assertEqual(r.reason_code, "UNTRUSTED_PREFLIGHT_RESULT")
        self.assertFalse(r.forward_eligible)

    def test_report_contains_only_anonymous_allowlisted_fields(self):
        r = prepare_offline_diagnostic_report(PreflightResult(PREVIEW, RACE, True, 2))
        summary = r.anonymous_summary()
        self.assertEqual(summary["race_id"], RACE)
        self.assertFalse(summary["forward_eligible"])
        self.assertFalse(summary["diagnostic_live_get_authorized"])
        self.assertEqual(summary["attempted_gets"], 0)
        self.assertFalse(any(k in summary for k in (
            "racer_id", "racer_name", "raw_html", "source_url",
            "official_deadline_at", "manual_approval_ref")))


if __name__ == "__main__":
    unittest.main()
