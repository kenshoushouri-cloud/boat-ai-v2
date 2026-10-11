"""Offline 7-day Q1/Q2/Q3 multi-race, multi-day and unknown zero-race tests.

All values here are SYNTHETIC. No external database, official source or BUY.
Absence of Q1 rows is not independently verified evidence of a race holiday.
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from v5.offline_seven_day_stream_adapter import (
    audit_feature_streams, audit_postrace_stream,
)

JST = ZoneInfo("Asia/Tokyo")
START = date(2026, 5, 1)
END = date(2026, 5, 8)
IDS = ("20260501_01_01", "20260501_24_12", "20260503_02_05")


def synthetic_race(rid: str):
    day = date.fromisoformat(f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}")
    deadline = datetime(day.year, day.month, day.day, 17, 41, tzinfo=JST)
    inventory = dict(race_id=rid, race_date=day, deadline_at=deadline)
    lanes = []
    for lane in range(1, 7):
        lanes.append(dict(
            race_id=rid, race_date=day, deadline_at=deadline, lane=lane,
            racer_number=4400+lane, racer_class="A1" if lane%2 else "B1",
            recent_form_json_type="array",
            parsed_history=[dict(race_date=(day-timedelta(days=1)).isoformat(),
                                 finish_position=lane)],
            exhibition_source="official_beforeinfo_historical",
            exhibition_time_rank=lane,
            exhibition_snapshot_at=deadline+timedelta(days=30),
            independent_official_six_active_verified=False,
            original_first_observation_verified=False,
            forward_eligible=False, buy_eligible=False,
        ))
    result = dict(
        race_id=rid, race_date=day, result_status="official",
        race_status="official", winning_ticket="1-2-3",
        payout_per_100_yen=1100,
        refund_boats=None, refund_section_verified=False,
        whole_race_void_verified=False, v5_real_roi_verified=False,
        buy_eligible=False,
    )
    return inventory, lanes, result


def cohort():
    inventory, lanes, results = [], [], []
    for rid in IDS:
        row, six, result = synthetic_race(rid)
        inventory.append(row)
        lanes.extend(six)
        results.append(result)
    return inventory, lanes, results


class TestMultiRaceSevenDayCohort(unittest.TestCase):
    def test_three_races_two_venues_and_two_days_retained(self):
        inventory, lanes, _ = cohort()
        # SQL order is not an authority; no results are used to form candidates.
        x = audit_feature_streams(START, END, inventory[::-1], lanes[::-1])
        self.assertEqual(x.inventory_ids, IDS)
        self.assertEqual(tuple(r.race_id for r in x.candidates), IDS)
        self.assertEqual(x.pending_ids, ())
        self.assertEqual(tuple(y.lane for y in x.candidates[0].lanes), tuple(range(1, 7)))
        self.assertFalse(x.inventory_independently_verified)
        self.assertFalse(x.buy_eligible)

    def test_no_rows_day_never_called_verified_holiday(self):
        inventory, lanes, _ = cohort()
        x = audit_feature_streams(START, END, inventory, lanes)
        missing = tuple(START+timedelta(days=n) for n in (1, 3, 4, 5, 6))
        self.assertEqual(x.unrepresented_days, missing)
        self.assertFalse(x.inventory_independently_verified)
        self.assertFalse(x.forward_eligible)
        # Q1 has no independent opening-day proof: an empty day may be an
        # actual race holiday OR missed inventory; do not classify from Q1.
        self.assertFalse(hasattr(x, "official_no_race_days"))

    def test_all_empty_q1_cannot_certify_full_week_closed(self):
        with self.assertRaisesRegex(ValueError, "EMPTY_INVENTORY"):
            audit_feature_streams(START, END, [], [])

    def test_missing_lane_on_one_race_does_not_delete_other_races(self):
        inventory, lanes, _ = cohort()
        damaged = [r for r in lanes if not (r["race_id"] == IDS[1] and r["lane"] == 6)]
        x = audit_feature_streams(START, END, inventory, damaged)
        self.assertEqual(x.inventory_ids, IDS)
        self.assertEqual(x.pending_ids, (IDS[1],))
        self.assertEqual({r.race_id for r in x.candidates}, {IDS[0], IDS[2]})
        self.assertIn((IDS[1], "MISSING_OR_DUPLICATE_LANE_ROWS"), x.issues)

    def test_duplicate_lane_kept_as_pending_not_deduplicated(self):
        inventory, lanes, _ = cohort()
        duplicate = dict(lanes[0])
        x = audit_feature_streams(START, END, inventory, lanes+[duplicate])
        self.assertEqual(x.pending_ids, (IDS[0],))
        self.assertEqual(len(x.inventory_ids), 3)
        self.assertEqual(len(x.candidates), 2)

    def test_missing_or_duplicate_result_never_changes_q1_population(self):
        inventory, lanes, results = cohort()
        features = audit_feature_streams(START, END, inventory, lanes)
        missing = audit_postrace_stream(features, results[:-1])
        self.assertIn(IDS[2], missing.pending_ids)
        duplicate = audit_postrace_stream(features, results + [dict(results[1])])
        self.assertIn((IDS[1], "MISSING_OR_DUPLICATE_RESULT"), duplicate.issues)
        self.assertEqual(features.inventory_ids, IDS)
        self.assertEqual(len(features.candidates), 3)
        self.assertIsNone(missing.hypothetical_roi_pct)
        self.assertIsNone(duplicate.hypothetical_roi_pct)

    def test_result_cancelled_does_not_remove_feature_candidate(self):
        inventory, lanes, results = cohort()
        features = audit_feature_streams(START, END, inventory, lanes)
        results[0]["result_status"] = "cancelled"
        results[0]["race_status"] = "cancelled"
        results[0]["winning_ticket"] = None
        results[0]["payout_per_100_yen"] = None
        postrace = audit_postrace_stream(features, results)
        self.assertEqual(features.inventory_ids, IDS)
        self.assertEqual(len(features.candidates), 3)
        self.assertEqual(postrace.pending_ids, IDS)
        self.assertIn((IDS[0], "STORED_RESULT_OR_REFUND_UNVERIFIED"), postrace.issues)
        self.assertFalse(postrace.v5_real_roi_verified)

    def test_result_column_must_not_cross_into_predecision_Q2(self):
        inventory, lanes, _ = cohort()
        for r in lanes:
            if r["race_id"] == IDS[2] and r["lane"] == 1:
                r["payout_per_100_yen"] = 1100
        x = audit_feature_streams(START, END, inventory, lanes)
        self.assertEqual(x.pending_ids, (IDS[2],))
        self.assertEqual(len(x.candidates), 2)

    def test_unknown_result_race_rejected_not_dropped(self):
        inventory, lanes, results = cohort()
        x = audit_feature_streams(START, END, inventory, lanes)
        results.append(dict(synthetic_race("20260502_01_01")[2]))
        with self.assertRaisesRegex(ValueError, "RESULT_OUTSIDE_INVENTORY"):
            audit_postrace_stream(x, results)

    def test_same_day_result_not_used_as_race_history(self):
        inventory, lanes, _ = cohort()
        for r in lanes:
            if r["race_id"] == IDS[1] and r["lane"] == 1:
                r["parsed_history"] = [dict(race_date="2026-05-01", finish_position=1)]
        x = audit_feature_streams(START, END, inventory, lanes)
        self.assertEqual(x.pending_ids, (IDS[1],))
        self.assertEqual(len(x.candidates), 2)
        self.assertFalse(x.buy_eligible)


if __name__ == "__main__":
    unittest.main()
