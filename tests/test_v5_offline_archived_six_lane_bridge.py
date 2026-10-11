"""Offline reconstruction tests. Only illustrative, not actual V5 predictions."""
import unittest
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo
from v5.offline_archived_six_lane_bridge import (
    ArchivedLane, ArchivedRaceFactors, build_archived_rank,
)
from v5.offline_retrospective_result_adapter import StoredResultRow, join_ranked_v5_scenarios

JST = ZoneInfo("Asia/Tokyo")


def dt(y, m, d, h=12, minute=0):
    return datetime(y, m, d, h, minute, tzinfo=JST)


def race():
    lanes = tuple(ArchivedLane(
        i, 4000+i, "A1",
        tuple({"race_date": f"2026-04-{d:02d}"} for d in range(26,31)),
        (3,1,4,2,6,5)[i-1], "official_beforeinfo_historical",
        dt(2026,8,15),
    ) for i in range(1,7))
    # Equal probabilities and unity factors are a MOCK, NOT measured V5 inputs.
    return ArchivedRaceFactors(
        "20260501_24_12", dt(2026,5,1,17), dt(2026,5,1,17,41),
        date(2026,4,30), (1/6,)*6,
        {k:(1.,)*6 for k in
         ("recent_form","exhibition_rank","racer_course","opponent","venue_lane")},
        lanes, 2, 100)


class OfflineMappingTests(unittest.TestCase):
    def test_offline_chain_historical_fixture_without_provenance(self):
        out = build_archived_rank(race())
        self.assertEqual(out.reason,
                         "ARCHIVED_SIX_LANE_V5_RECONSTRUCTION_NO_REAL_ASOF_PROOF")
        self.assertEqual((out.historical_exhibition_lanes,
                          out.late_or_unknown_snapshot_lanes), (6,6))
        self.assertEqual(len(out.frozen_case.ranking.top_tickets), 2)
        self.assertFalse(out.buy_eligible)
        # Stored actual winner ticket/payout used only AFTER research ticket
        # choice; unverified refund means even retrospective ROI is withheld.
        settled = StoredResultRow("20260501_24_12",
                                 "official","official","2-1-5",6180)
        joined = join_ranked_v5_scenarios([out.frozen_case], [settled])
        self.assertIsNone(joined.economics.hypothetical_roi_pct)
        self.assertEqual(joined.provenance_by_race[0][1],
                         "RETROSPECTIVE_ARCHIVE_NOT_ASOF")

    def test_late_recent_form_rejected(self):
        x = race()
        rows = list(x.lanes)
        rows[0] = replace(rows[0],recent_form=({"race_date":"2026-05-01"},))
        self.assertEqual(build_archived_rank(replace(x,lanes=tuple(rows))).reason,
                         "RECENT_FORM_NOT_PRIOR_DAY")

    def test_missing_lane_rejected(self):
        x = race()
        self.assertEqual(build_archived_rank(replace(x,lanes=x.lanes[:5])).reason,
                         "SIX_LANE_ROWS_REQUIRED")

    def test_duplicate_exhibition_rank_rejected(self):
        x = race()
        rows = list(x.lanes)
        rows[0] = replace(rows[0],exhibition_time_rank=1)
        self.assertEqual(build_archived_rank(replace(x,lanes=tuple(rows))).reason,
                         "EXHIBITION_RANK_INCOMPLETE_OR_DUPLICATE")

    def test_same_day_fit_denied(self):
        x = race()
        self.assertEqual(build_archived_rank(
            replace(x,model_fitted_through=date(2026,5,1))).reason,
            "HISTORICAL_MODEL_TIME_LEAK_OR_UNKNOWN")

    def test_explicit_stake_required(self):
        x = race()
        self.assertEqual(build_archived_rank(
            replace(x,stake_per_ticket_yen=50)).reason,
            "EXPLICIT_TICKET_COUNT_AND_STAKE_REQUIRED")

    def test_missing_previous_day_factors_fails(self):
        x = race()
        self.assertEqual(build_archived_rank(replace(x,factors={})).reason,
                         "PREVIOUS_DAY_FROZEN_FACTOR_VECTORS_REQUIRED")

    def test_duplicate_racer_rejected(self):
        x = race()
        rows = list(x.lanes)
        rows[0] = replace(rows[0],racer_number=4002)
        self.assertEqual(build_archived_rank(replace(x,lanes=tuple(rows))).reason,
                         "RACER_ID_OR_CLASS_INVALID")

    def test_historical_source_claims_only_timestamp(self):
        x = race()
        rows = tuple(replace(r,exhibition_source="learning_all",
                             exhibition_snapshot_at=dt(2026,5,1,16))
                     for r in x.lanes)
        out = build_archived_rank(replace(x,lanes=rows))
        self.assertEqual(out.late_or_unknown_snapshot_lanes,0)
        self.assertFalse(out.original_first_observation_verified)

    def test_missing_exhibition_timestamp(self):
        x = race()
        rows = list(x.lanes)
        rows[0] = replace(rows[0],exhibition_snapshot_at=None)
        self.assertEqual(build_archived_rank(replace(x,lanes=tuple(rows))).reason,
                         "EXHIBITION_PROVENANCE_MISSING")


if __name__ == "__main__":
    unittest.main()
