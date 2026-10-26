"""Synthetic VIEW-shaped rows; no PostgreSQL, collectors or BUY."""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import replace

from v5.entry_quality_policy import STATS
from v5.offline_entry_view_adapter import inspect_offline_view_rows

JST = timezone(timedelta(hours=9))


def example():
    race = {
        "race_id": "20261026_10_01",
        "race_date": date(2026, 10, 26),
        "deadline_at": datetime(2026, 10, 26, 8, 47, tzinfo=JST),
        "status": "scheduled",
    }
    stats = {key: Decimal("4.25") for key in STATS}
    stats.update({
        "avg_st": Decimal("0.16"), "motor_no": "025", "boat_no": "016",
        "national_win_rate": Decimal("6.35"),
        "local_win_rate": Decimal("5.28"),
    })
    rows = []
    for i in range(1, 7):
        rows.append({
            "race_id": race["race_id"], "lane": i,
            "racer_no": str(4000 + i), "racer_number": 4000 + i,
            **stats, "created_at": race["deadline_at"] + timedelta(days=90),
            "updated_at": race["deadline_at"] + timedelta(days=91),
            "recent_form": {"not": "proof"},
            "raw": {"mutable": "not proof"},
        })
    return race, rows


class OfflineViewEntryAdapterTest(unittest.TestCase):
    def check_never_authorizes(self, verdict):
        for attr in (
            "original_first_observation_verified",
            "independently_authenticated_source", "six_active_starts_confirmed",
            "selection_eligible", "forward_eligible", "buy_eligible",
        ):
            self.assertIs(getattr(verdict, attr), False)
        with self.assertRaises(AttributeError):
            verdict.buy_eligible = True
        return verdict

    def test_full_entries_research_shape_only_even_if_updated_late(self):
        race, rows = example()
        result = self.check_never_authorizes(inspect_offline_view_rows(race, rows))
        self.assertEqual(result.reason, "VIEW_SHAPE_ONLY_ORIGINAL_ASOF_UNVERIFIED_HOLD")
        self.assertEqual(result.entry_quality_status, "COMPLETE_STATS_RESEARCH_ONLY")
        self.assertEqual(result.checked_lanes, 6)
        self.assertTrue(result.metadata_shape_consistent)

    def test_same_jst_deadline_returned_as_utc_is_valid_shape(self):
        race, rows = example()
        race["deadline_at"] = race["deadline_at"].astimezone(timezone.utc)
        self.assertTrue(self.check_never_authorizes(
            inspect_offline_view_rows(race, rows)).metadata_shape_consistent)

    def test_unverified_null_never_becomes_official_unreported(self):
        race, rows = example()
        rows[0]["avg_st"] = None
        result = self.check_never_authorizes(inspect_offline_view_rows(race, rows))
        self.assertEqual(result.reason, "ENTRY_QUALITY_HOLD")
        self.assertEqual(result.entry_quality_status, "AT_LEAST_ONE_LANE_QUALITY_HOLD")

    def test_identity_conflict_holds(self):
        race, rows = example()
        rows[2]["racer_no"] = "9999"
        result = self.check_never_authorizes(inspect_offline_view_rows(race, rows))
        self.assertEqual(result.reason, "ENTRY_TYPE_OR_IDENTITY_HOLD")

    def test_duplicate_lane_holds(self):
        race, rows = example()
        rows[1]["lane"] = 1
        result = self.check_never_authorizes(inspect_offline_view_rows(race, rows))
        self.assertEqual(result.reason, "ENTRY_QUALITY_HOLD")
        self.assertEqual(result.entry_quality_status, "SIX_LANE_IDENTITY_HOLD")

    def test_missing_or_invalid_motor_number_holds(self):
        race, rows = example()
        rows[0]["motor_no"] = "02A"
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")
        rows[0]["motor_no"] = None
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_QUALITY_HOLD")

    def test_missing_entry_field_holds(self):
        race, rows = example()
        del rows[0]["racer_number"]
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")

    def test_non_numeric_in_numeric_field_holds(self):
        race, rows = example()
        rows[0]["national_win_rate"] = "6.35"
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")

    def test_nan_and_bool_hold(self):
        race, rows = example()
        rows[0]["avg_st"] = float("nan")
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")
        rows[0]["avg_st"] = True
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")

    def test_absent_or_naive_deadline_holds(self):
        race, rows = example()
        race["deadline_at"] = None
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "RACE_METADATA_SHAPE_HOLD")
        race["deadline_at"] = datetime(2026, 10, 26, 8, 47)
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "RACE_METADATA_SHAPE_HOLD")

    def test_wrong_race_and_wrong_date_holds(self):
        race, rows = example()
        rows[0]["race_id"] = "20261026_10_02"
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "ENTRY_TYPE_OR_IDENTITY_HOLD")
        race, rows = example()
        race["race_date"] = date(2026, 10, 25)
        self.assertEqual(inspect_offline_view_rows(race, rows).reason,
                         "RACE_METADATA_SHAPE_HOLD")

    def test_fewer_than_six_entries_holds(self):
        race, rows = example()
        self.assertEqual(inspect_offline_view_rows(race, rows[:5]).reason,
                         "SIX_ENTRY_SHAPE_HOLD")

    def test_no_rating_is_inferred_from_class_or_raw(self):
        race, rows = example()
        for row in rows:
            row["class"] = "A1"
            row["raw"] = {"rating": 1000, "original_before_deadline": True}
        verdict = self.check_never_authorizes(inspect_offline_view_rows(race, rows))
        self.assertEqual(verdict.reason, "VIEW_SHAPE_ONLY_ORIGINAL_ASOF_UNVERIFIED_HOLD")


if __name__ == "__main__":
    unittest.main()
