"""Offline-only synthetic tests. No requests/session, CI dispatch, DB, or Railway."""
import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from v5.positive_start_diagnostic_preflight import (
    ApprovedRaceScope, ReviewedSourceSchema, _expected_urls,
    _review_preflight, review_positive_start_diagnostic_preflight,
)

JST = timezone(timedelta(hours=9))
RACE = "20261011_03_02"  # deliberately NOT the completed Edogawa 20261010_03_01
DEADLINE = datetime(2026, 10, 11, 12, 0, tzinfo=JST)
CUTOFF = datetime(2026, 10, 11, 11, 56, tzinfo=JST)
START = datetime(2026, 10, 11, 11, 50, tzinfo=JST)
SCHEMA_ID = "FIXTURE_ONLY_NOT_OFFICIAL"
SCHEMA = ReviewedSourceSchema(
    schema_id=SCHEMA_ID,
    official_documentation_url="https://www.boatrace.jp/fixture-not-real",
    independent_review_ref="FAKE_TEST_REVIEW_ONLY",
    affirmative_status_field="fixture.affirmative_active_status",
    lane_field="fixture.lane",
    racer_registration_field="fixture.registration",
    candidate_endpoint="beforeinfo",
)
URLS = _expected_urls(RACE, "beforeinfo")
SCOPE = ApprovedRaceScope(
    race_id=RACE, schema_id=SCHEMA_ID,
    independent_review_ref="FAKE_TEST_REVIEW_ONLY",
    manual_approval_ref="SYNTHETIC_APPROVAL_NOT_REAL",
    official_deadline_at=DEADLINE, decision_cutoff_at=CUTOFF,
    exact_urls=URLS,
)


def review(**changed):
    args = dict(race_ids=[RACE], schema_id=SCHEMA_ID,
                official_deadline_at=DEADLINE, decision_cutoff_at=CUTOFF,
                observation_start_at=START, requested_urls=URLS,
                reviewed_schemas={SCHEMA_ID: SCHEMA},
                approved_scopes=frozenset({SCOPE}))
    args.update(changed)
    return _review_preflight(**args)


class DiagnosticPreflightTests(unittest.TestCase):
    def assert_denied(self, result, code):
        self.assertEqual(result.reason_code, code)
        self.assertFalse(result.preflight_conditions_met)
        self.assertEqual(result.planned_gets, 0)
        self.assertFalse(result.forward_eligible)
        self.assertFalse(result.diagnostic_live_get_authorized)

    def test_production_default_denies_even_with_fake_review_data(self):
        result = review_positive_start_diagnostic_preflight(
            race_ids=[RACE], schema_id=SCHEMA_ID,
            official_deadline_at=DEADLINE, decision_cutoff_at=CUTOFF,
            observation_start_at=START, requested_urls=URLS)
        self.assert_denied(result, "NO_AUTHORITATIVE_SCHEMA")

    def test_synthetic_review_checks_only_never_authorizes_get(self):
        result = review()
        self.assertTrue(result.preflight_conditions_met)
        self.assertEqual(result.reason_code, "PREFLIGHT_ONLY_NOT_LIVE_AUTHORIZATION")
        self.assertEqual(result.planned_gets, 2)
        self.assertFalse(result.forward_eligible)
        self.assertFalse(result.diagnostic_live_get_authorized)
        self.assertFalse(result.six_active_starts_confirmed)
        self.assertFalse(result.beforeinfo_first_write_eligible)
        self.assertFalse(result.persistence_performed)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.forward_eligible = True

    def test_no_manual_scope(self):
        self.assert_denied(review(approved_scopes=frozenset()),
                           "RACE_SPECIFIC_MANUAL_REVIEW_MISSING")

    def test_wrong_manual_scope_binding(self):
        other = dataclasses.replace(SCOPE, race_id="20261011_03_03")
        self.assert_denied(review(approved_scopes=frozenset({other})),
                           "RACE_SPECIFIC_MANUAL_REVIEW_MISSING")

    def test_wrong_manual_deadline_binding(self):
        other = dataclasses.replace(SCOPE, official_deadline_at=DEADLINE + timedelta(minutes=1))
        self.assert_denied(review(approved_scopes=frozenset({other})),
                           "RACE_SPECIFIC_MANUAL_REVIEW_MISSING")

    def test_no_official_schema(self):
        self.assert_denied(review(reviewed_schemas={}), "NO_AUTHORITATIVE_SCHEMA")

    def test_unreviewed_schema_assertion_not_accepted(self):
        unsafe = dataclasses.replace(SCHEMA, independent_review_ref="")
        self.assert_denied(review(reviewed_schemas={SCHEMA_ID: unsafe}),
                           "NO_AUTHORITATIVE_SCHEMA")

    def test_one_race_only(self):
        for race_ids in ([], [RACE, "20261011_03_03"], [RACE, RACE], RACE):
            with self.subTest(race_ids=race_ids):
                self.assert_denied(review(race_ids=race_ids), "ONE_RACE_REQUIRED")

    def test_no_repeat_completed_edogawa(self):
        self.assert_denied(review(race_ids=["20261010_03_01"]),
                           "PREVIOUSLY_PROBED_RACE_FORBIDDEN")

    def test_race_date_invalid(self):
        self.assert_denied(review(race_ids=["20261340_03_02"]), "INVALID_RACE_DATE")

    def test_window_boundaries_8_and_15_inclusive(self):
        for delta in (8, 15):
            with self.subTest(delta=delta):
                result = review(observation_start_at=DEADLINE-timedelta(minutes=delta))
                self.assertTrue(result.preflight_conditions_met)
        for delta in (7, 16):
            with self.subTest(delta=delta):
                self.assert_denied(review(observation_start_at=DEADLINE-timedelta(minutes=delta)),
                                   "OUTSIDE_PREDEADLINE_WINDOW")

    def test_naive_or_missing_clock(self):
        self.assert_denied(review(official_deadline_at=DEADLINE.replace(tzinfo=None)),
                           "OFFICIAL_DEADLINE_UNVERIFIED")
        self.assert_denied(review(observation_start_at=None),
                           "OFFICIAL_DEADLINE_UNVERIFIED")

    def test_wrong_day_and_cutoff(self):
        self.assert_denied(review(observation_start_at=START-timedelta(days=1)),
                           "OFFICIAL_DEADLINE_UNVERIFIED")
        self.assert_denied(review(decision_cutoff_at=START-timedelta(minutes=1)),
                           "OFFICIAL_DEADLINE_UNVERIFIED")

    def test_exact_official_urls_only(self):
        for urls in (URLS[::-1], URLS+(URLS[0],),
                     (URLS[0].replace("www.boatrace.jp", "fake.boatrace.jp"), URLS[1]),
                     (URLS[0]+"&extra=1", URLS[1]), (URLS[0],),
                     (URLS[0], URLS[0])):
            with self.subTest(urls=urls):
                code = "INVALID_GET_SCOPE" if len(urls)>2 else "SOURCE_URL_NOT_EXACTLY_ALLOWLISTED"
                self.assert_denied(review(requested_urls=urls), code)

    def test_no_arbitrary_racer_data_or_positive_boolean_input(self):
        self.assertNotIn("forward_eligible", review.__code__.co_varnames)
        self.assertFalse(review().forward_eligible)
        self.assertFalse(review().six_active_starts_confirmed)

    def test_timezone_equivalence_must_match_scope(self):
        converted = DEADLINE.astimezone(timezone.utc)
        result = review(official_deadline_at=converted)
        self.assertTrue(result.preflight_conditions_met)

    def test_only_canonical_source_schema(self):
        invalid = dataclasses.replace(SCHEMA, candidate_endpoint="oddstf")
        self.assert_denied(review(reviewed_schemas={SCHEMA_ID: invalid}),
                           "NO_AUTHORITATIVE_SCHEMA")


if __name__ == "__main__":
    unittest.main()
