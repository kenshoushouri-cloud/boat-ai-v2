"""No DB / network: synthetic rows for one archived six-lane SQL contract."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from v5.offline_six_lane_raw_extract_guard import inspect_six_lane_raw_extract

JST = ZoneInfo("Asia/Tokyo")
DEADLINE = datetime(2026, 5, 1, 17, 41, tzinfo=JST)
LATE = datetime(2026, 8, 15, 13, 54, 54, tzinfo=JST)


def rows():
    return tuple(dict(
        race_id="20260501_24_12",
        race_date=date(2026, 5, 1),
        deadline_at=DEADLINE,
        lane=n,
        racer_number=4000+n,
        racer_class="A1",
        recent_form_json_type="array",
        parsed_history=[{"race_date":"2026-04-30"} for _ in range(5)],
        exhibition_time_rank=(3, 1, 4, 2, 6, 5)[n-1],
        exhibition_source="official_beforeinfo_historical",
        exhibition_snapshot_at=LATE,
        independent_official_six_active_verified=False,
        original_first_observation_verified=False,
        forward_eligible=False,
        buy_eligible=False,
    ) for n in range(1, 7))


def changed(index=0, **changes):
    out = [dict(r) for r in rows()]
    out[index].update(changes)
    return tuple(out)


class TestSixLaneRawExtractGuard(unittest.TestCase):
    def test_complete_archived_rows_are_not_real_predeadline_proof(self):
        result = inspect_six_lane_raw_extract(rows())
        self.assertTrue(result.research_value_shape_complete)
        self.assertEqual(result.status, "ARCHIVED_VALUE_SHAPE_ONLY")
        self.assertIn("HISTORICAL_SOURCE_NOT_PREDECISION_PROOF", result.reasons)
        self.assertIn("EXHIBITION_SNAPSHOT_AFTER_DEADLINE", result.reasons)
        self.assertFalse(result.official_six_active_verified)
        self.assertFalse(result.original_first_observation_verified)
        self.assertFalse(result.v5_real_roi_verified)
        self.assertFalse(result.forward_eligible)
        self.assertFalse(result.buy_eligible)

    def test_missing_lane_kept_as_hold(self):
        result = inspect_six_lane_raw_extract(rows()[:-1])
        self.assertEqual(result.status, "HOLD_INCOMPLETE_SIX_LANE_VALUES")
        self.assertIn("EXACTLY_SIX_ROWS_REQUIRED", result.reasons)

    def test_duplicate_lane_or_registration_kept_as_hold(self):
        result = inspect_six_lane_raw_extract(changed(5, lane=5))
        self.assertTrue(any("DUPLICATE" in x for x in result.reasons))
        self.assertFalse(result.research_value_shape_complete)
        result = inspect_six_lane_raw_extract(changed(5, racer_number=4001))
        self.assertFalse(result.research_value_shape_complete)

    def test_null_registration_and_class_never_coerced(self):
        result = inspect_six_lane_raw_extract(changed(racer_number=None,
                                                       racer_class=None))
        self.assertIn("ROW_1_RACER_MISSING_INVALID_OR_DUPLICATE", result.reasons)
        self.assertIn("ROW_1_RACER_CLASS_MISSING_OR_INVALID", result.reasons)
        self.assertFalse(result.research_value_shape_complete)

    def test_missing_or_six_history_rows_denied(self):
        for history in (None, [], [{"race_date":"2026-04-30"}]*6):
            with self.subTest(history=history):
                result = inspect_six_lane_raw_extract(changed(parsed_history=history))
                self.assertIn("ROW_1_RECENT_FORM_MISSING_OR_INVALID", result.reasons)
        result = inspect_six_lane_raw_extract(changed(recent_form_json_type=None))
        self.assertFalse(result.research_value_shape_complete)

    def test_same_day_or_invalid_history_not_prior_day(self):
        for date_value in ("2026-05-01", "2026-02-31", None):
            with self.subTest(value=date_value):
                result = inspect_six_lane_raw_extract(changed(
                    parsed_history=[{"race_date":date_value}]))
                self.assertIn("ROW_1_RECENT_FORM_NOT_PRIOR_DAY", result.reasons)

    def test_rank_missing_or_duplicate_denied(self):
        for value in (None, 2, 7):
            with self.subTest(rank=value):
                result = inspect_six_lane_raw_extract(changed(exhibition_time_rank=value))
                self.assertIn("ROW_1_EXHIBITION_RANK_MISSING_OR_DUPLICATE", result.reasons)

    def test_timezone_naive_and_missing_snapshot_denied(self):
        result = inspect_six_lane_raw_extract(changed(
            deadline_at=datetime(2026, 5, 1, 17, 41),
            exhibition_snapshot_at=None,
            exhibition_source=None))
        self.assertIn("ROW_1_DEADLINE_TIMEZONE_OR_DATE_UNVERIFIED", result.reasons)
        self.assertIn("ROW_1_SNAPSHOT_TIMEZONE_OR_VALUE_UNVERIFIED", result.reasons)
        self.assertIn("ROW_1_EXHIBITION_SOURCE_MISSING", result.reasons)

    def test_claimed_positive_authority_flag_denied(self):
        result = inspect_six_lane_raw_extract(changed(forward_eligible=True))
        self.assertIn("ROW_1_PROOF_COLUMNS_NOT_FALSE", result.reasons)
        self.assertFalse(result.buy_eligible)
        result = inspect_six_lane_raw_extract(changed(
            independent_official_six_active_verified=True))
        self.assertFalse(result.research_value_shape_complete)

    def test_wrong_day_or_inconsistent_deadline_denied(self):
        result = inspect_six_lane_raw_extract(changed(race_date="2026-05-02"))
        self.assertIn("ROW_1_RACE_ID_OR_DAY_MISMATCH", result.reasons)
        result = inspect_six_lane_raw_extract(changed(
            deadline_at=datetime(2026, 5, 1, 17, 42, tzinfo=JST)))
        self.assertIn("INCONSISTENT_LANE_DEADLINES", result.reasons)

    def test_invalid_row_collection_denied(self):
        self.assertEqual(inspect_six_lane_raw_extract(None).status,
                         "HOLD_INVALID_ROWS")
        result = inspect_six_lane_raw_extract([None]+list(rows()[1:]))
        self.assertIn("ROW_1_MAPPING_REQUIRED", result.reasons)


if __name__ == "__main__":
    unittest.main()
