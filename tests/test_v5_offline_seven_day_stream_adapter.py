"""No-network synthetic checks of V5 seven-day Q1/Q2/Q3 data streams."""
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from v5.offline_seven_day_stream_adapter import audit_feature_streams, audit_postrace_stream

D = date(2026, 5, 1)
T = datetime(2026, 5, 1, 17, 41, tzinfo=ZoneInfo("Asia/Tokyo"))
R = "20260501_24_12"

def sample():
    inv = [dict(race_id=R, race_date=D, deadline_at=T)]
    lanes = [dict(race_id=R, race_date=D, deadline_at=T, lane=n,
        racer_number=4000+n, racer_class="A1", recent_form_json_type="array",
        parsed_history=[dict(race_date="2026-04-30",finish_position=3)],
        exhibition_source="official_beforeinfo_historical",
        exhibition_time_rank=(3,1,4,2,6,5)[n-1],
        exhibition_snapshot_at=T+timedelta(days=30),
        independent_official_six_active_verified=False,
        original_first_observation_verified=False,
        forward_eligible=False,buy_eligible=False) for n in range(1,7)]
    results = [dict(race_id=R, race_date=D, result_status="official",
        race_status="official",winning_ticket="2-1-5",
        payout_per_100_yen=6180,refund_boats=None,
        refund_section_verified=False,whole_race_void_verified=False,
        v5_real_roi_verified=False,buy_eligible=False)]
    return inv, lanes, results

def features():
    i,l,_=sample()
    return audit_feature_streams(D,D+timedelta(days=1),i,l)

class TestOfflineStreams(unittest.TestCase):
    def test_complete_six_lanes_are_retrospective_only(self):
        x=features()
        self.assertEqual(len(x.candidates),1)
        self.assertFalse(x.buy_eligible)
        self.assertFalse(x.original_capture_verified)
        self.assertFalse(hasattr(x.candidates[0], "stored_ticket"))

    def test_postrace_separate_and_refunds_unverified(self):
        i,l,r=sample()
        f=audit_feature_streams(D,D+timedelta(days=1),i,l)
        x=audit_postrace_stream(f,r)
        self.assertEqual(len(x.stored_only),1)
        self.assertEqual(x.pending_ids,(R,))
        self.assertIsNone(x.hypothetical_roi_pct)
        self.assertIsNone(x.stored_only[0].refund_boats)

    def test_missing_and_duplicate_lanes_do_not_drop_inventory(self):
        i,l,_=sample()
        for bad in (l[:-1],l+l[-1:]):
            x=audit_feature_streams(D,D+timedelta(days=1),i,bad)
            self.assertEqual(x.inventory_ids,(R,))
            self.assertEqual(x.pending_ids,(R,))

    def test_result_column_cannot_enter_features(self):
        i,l,_=sample()
        l[0]["winning_ticket"]="2-1-5"
        x=audit_feature_streams(D,D+timedelta(days=1),i,l)
        self.assertEqual(x.pending_ids,(R,))

    def test_same_day_history_does_not_enter_features(self):
        i,l,_=sample()
        l[0]["parsed_history"]=[dict(race_date="2026-05-01",finish_position=1)]
        x=audit_feature_streams(D,D+timedelta(days=1),i,l)
        self.assertEqual(x.pending_ids,(R,))

    def test_refund_false_claim_is_rejected(self):
        i,l,r=sample()
        r[0]["refund_boats"]=()
        x=audit_postrace_stream(features(),r)
        self.assertEqual(x.stored_only,())
        self.assertEqual(x.pending_ids,(R,))

    def test_duplicate_result_remains_pending(self):
        i,l,r=sample()
        x=audit_postrace_stream(features(),r+r)
        self.assertEqual(x.stored_only,())
        self.assertEqual(x.pending_ids,(R,))

    def test_window_and_duplicate_inventory_guard(self):
        i,l,_=sample()
        with self.assertRaises(ValueError):
            audit_feature_streams(D,D+timedelta(days=8),i,l)
        with self.assertRaises(ValueError):
            audit_feature_streams(D,D+timedelta(days=1),i+i,l)

if __name__=="__main__":
    unittest.main()
