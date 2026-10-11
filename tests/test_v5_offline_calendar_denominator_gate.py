"""No DB. Q1 missing day != independently certified no-race day."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from v5.offline_seven_day_stream_adapter import audit_feature_streams
from v5.offline_calendar_denominator_gate import (
    CalendarDayClaim, audit_window_calendar, audit_period_calendar,
)
# v5.offline_research_period_batches imports WholeDayResearchLedger, which is
# genuine source in full repo; this test env supplies minimal import stubs only.
from v5.offline_research_period_batches import plan_research_period

S=date(2026,5,1)
E=date(2026,5,8)
D1=date(2026,5,1)
D3=date(2026,5,3)
T=ZoneInfo("Asia/Tokyo")

def features():
    rows=[]
    for rid in ("20260501_01_01","20260501_24_12","20260503_02_05"):
        day=date(int(rid[:4]),int(rid[4:6]),int(rid[6:8]))
        rows.append(dict(race_id=rid,race_date=day,
            deadline_at=datetime(day.year,day.month,day.day,17,40,tzinfo=T)))
    return audit_feature_streams(S,E,rows,[])

def daystatus(a, day):
    return next(r.status for r in a.days if r.day==day)

class TestCalendarGate(unittest.TestCase):
    def test_no_claim_empty_day_is_hold_not_holiday(self):
        a=audit_window_calendar(S,E,features())
        self.assertEqual(a.days[0].q1_races,2)
        self.assertEqual(a.days[2].q1_races,1)
        self.assertEqual(len(a.days),7)
        self.assertEqual(daystatus(a,S+timedelta(days=1)),
                         "HOLD_Q1_EMPTY_UNKNOWN_NOT_PROVEN_HOLIDAY")
        self.assertFalse(a.hypothetical_roi_authorized)

    def test_calendar_zero_claim_is_not_verified(self):
        a=audit_window_calendar(S,E,features(),
            (CalendarDayClaim(S+timedelta(days=1),0,"claimed-official-schedule"),))
        self.assertEqual(daystatus(a,S+timedelta(days=1)),
                         "HOLD_ZERO_RACE_CLAIM_NOT_INDEPENDENTLY_VERIFIED")
        self.assertFalse(a.full_window_denominator_verified)

    def test_positive_scheduled_races_missing_from_q1(self):
        a=audit_window_calendar(S,E,features(),
            (CalendarDayClaim(S+timedelta(days=1),12,"manifest"),))
        self.assertEqual(daystatus(a,S+timedelta(days=1)),
                         "HOLD_Q1_MISSING_CLAIMED_RACES")

    def test_count_shortfall_holds(self):
        a=audit_window_calendar(S,E,features(),
            (CalendarDayClaim(D1,3,"manifest"),))
        self.assertEqual(daystatus(a,D1),"HOLD_Q1_FEWER_THAN_CALENDAR_CLAIM")

    def test_count_excess_or_false_holiday_holds(self):
        for n in (0,1):
            with self.subTest(n=n):
                a=audit_window_calendar(S,E,features(),
                    (CalendarDayClaim(D1,n,"manifest"),))
                self.assertEqual(daystatus(a,D1),"HOLD_Q1_EXCEEDS_CALENDAR_CLAIM")

    def test_matching_count_remains_claim_only(self):
        a=audit_window_calendar(S,E,features(),(CalendarDayClaim(D1,2,"manifest"),))
        self.assertEqual(daystatus(a,D1),"HOLD_MATCHED_CLAIM_NOT_INDEPENDENT_PROOF")
        self.assertFalse(a.buy_eligible)

    def test_duplicate_and_bad_source_rejected(self):
        x=CalendarDayClaim(D1,2,"manifest")
        for claims in ((x,x),(CalendarDayClaim(D1,2,""),),
                       (CalendarDayClaim(S-timedelta(days=1),0,"m"),),
                       (CalendarDayClaim(D1,True,"m"),)):
            with self.subTest(claims=claims):
                with self.assertRaisesRegex(ValueError,"CALENDAR_CLAIM"):
                    audit_window_calendar(S,E,features(),claims)

    def test_corrupted_unrepresented_day_list_rejected(self):
        f=features()
        with self.assertRaisesRegex(ValueError,"Q1_UNREPRESENTED_DAYS"):
            audit_window_calendar(S,E,replace(f,unrepresented_days=()))

    def test_dropped_pending_cannot_hide_denominator(self):
        f=features()
        with self.assertRaisesRegex(ValueError,"Q1_CANDIDATE_PENDING"):
            audit_window_calendar(S,E,replace(f,pending_ids=f.pending_ids[:-1]))

    def test_missing_window_in_period_is_explicit(self):
        plan=plan_research_period(S,E-timedelta(days=1),7)
        out=audit_period_calendar(plan,())
        self.assertEqual(len(out.missing_windows),1)
        self.assertEqual(out.status,"HOLD_MISSING_WINDOW_CALENDAR")
        self.assertFalse(out.hypothetical_roi_authorized)

    def test_zero_race_claim_cannot_open_roi_for_fully_supplied_period(self):
        plan=plan_research_period(S,S+timedelta(days=6),7)
        day=S+timedelta(days=1)
        w=audit_window_calendar(S,E,features(),(CalendarDayClaim(day,0,"m"),))
        out=audit_period_calendar(plan,(w,))
        self.assertEqual(out.supplied_windows,1)
        self.assertEqual(out.declared_no_race_days_unverified,(day,))
        self.assertFalse(out.full_period_denominator_verified)
        self.assertFalse(out.hypothetical_roi_authorized)

    def test_extra_or_duplicate_window_rejected(self):
        plan=plan_research_period(S,E,7)
        w=audit_window_calendar(S,E,features())
        with self.assertRaisesRegex(ValueError,"WINDOW_UNEXPECTED_OR_DUPLICATE"):
            audit_period_calendar(plan,(w,w))

if __name__=="__main__":
    unittest.main()
