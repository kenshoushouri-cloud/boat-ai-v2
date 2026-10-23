"""Held two/three-day V5 Counter baseline cohort schedule regression.

Synthetic official-looking rows only; NO PostgreSQL, model fitting, first-write
attestation, historical ROI, real prediction, or BUY.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date,timedelta

from v5.offline_prior_day_factor_export import export_prior_day_factors
from v5.offline_retrospective_counter_seed import (
    RetrospectiveKBoat, RetrospectiveResearchRace,
)
from v5.offline_research_two_population_day import (
    CourseKBoat, CourseHistoryRace, project_two_population_day,
)
from v5.offline_retrospective_prior_day_chain import (
    chain_reference_calendar_days,
)

D0=date(2026,10,20)
D1=date(2026,10,21)
D2=date(2026,10,22)


def race_id(day,round_number):
    return day.strftime("%Y%m%d")+"_21_"+f"{round_number:02d}"


def boats(day,round_number):
    # Deliberately reuse racer numbers so per-racer totals must increment.
    # Synthetic only; no claim of real entrants/accidents/refund status.
    return tuple(CourseKBoat(
        lane=i,racer_number=4000+i,
        start_course=i,finish_position=(2,1,3,4,5,6)[i-1],
        is_flying=False,is_late=False,
    ) for i in range(1,7))


def course(day,round_number):
    return CourseHistoryRace(
        race_id(day,round_number),boats(day,round_number),
        "OFFICIAL",True,(),
    )


def fitted(day,round_number):
    rank=(3,1,4,2,6,5)
    return RetrospectiveResearchRace(
        race_id(day,round_number),2,
        tuple(RetrospectiveKBoat(
            lane=b.lane,racer_number=b.racer_number,
            racer_class=("A1","A2","B1","B2","A1","B1")[b.lane-1],
            exhibition_rank=rank[b.lane-1],
            start_course=b.start_course,finish_position=b.finish_position,
            is_flying=b.is_flying,is_late=b.is_late,
        ) for b in boats(day,round_number)),
        "OFFICIAL",True,(),
    )


def projected(day,fit_rounds,course_rounds,history_start=date(2025,7,1)):
    return project_two_population_day(
        day,
        tuple(fitted(day,n) for n in fit_rounds),
        tuple(course(day,n) for n in course_rounds),
        history_start=history_start,
    )


class TestHeldReferenceDayChain(unittest.TestCase):
    def build(self):
        return chain_reference_calendar_days((
            projected(D0,(2,),(2,3)),
            projected(D1,(),(2,)),
            projected(D2,(2,),(2,)),
        ))

    def test_cumulative_all_13_maps_and_reference_day_cohort(self):
        history=self.build()
        self.assertEqual(history.day_count,3)
        self.assertEqual(history.k_only_days_not_used_in_reference,(D1,))
        a,b,c=history.checkpoints
        self.assertEqual([x.state.completed_races for x in (a,b,c)],[1,1,2])
        self.assertEqual([x.course_race_count_applied for x in (a,b,c)],[2,0,1])
        self.assertEqual([x.state.counters["cs"][1] for x in (a,b,c)],[2,2,3])
        self.assertEqual([x.state.counters["rcs"][1][4001] for x in (a,b,c)],[2,2,3])
        self.assertEqual([x.state.counters["rct"][1][4001] for x in (a,b,c)],[2,2,3])
        self.assertEqual(c.state.counters["ct"][1],3)
        self.assertEqual(c.state.counters["lw"][2],2)
        self.assertEqual(c.state.counters["lcs"][1]["A1"],2)
        self.assertEqual(c.state.counters["lcw"][2]["A2"],2)
        self.assertEqual(c.state.counters["rks"][(2,"A2","1")],2)
        self.assertEqual(c.state.counters["rkw"][(2,"A2","1")],2)
        self.assertEqual(c.state.counters["ps"][(1,"A1",2,"A2")],2)
        self.assertEqual(c.state.counters["pw"][(2,"A2",1,"A1")],2)
        self.assertEqual(c.state.counters["vc"]["21"][2],2)
        self.assertEqual(c.state.counters["vn"]["21"],2)
        self.assertFalse(history.buy_eligible)
        self.assertFalse(history.exact_real_history_parity_verified)

    def test_counters_are_snapshots_not_mutating_prior_days(self):
        history=self.build()
        a,b,c=history.checkpoints
        self.assertEqual(a.state.counters["lw"][2],1)
        self.assertEqual(b.state.counters["lw"][2],1)
        self.assertEqual(c.state.counters["lw"][2],2)

    def test_same_day_model_export_rejects_postrace_counter(self):
        history=self.build()
        a=history.checkpoints[0]
        result=export_prior_day_factors(race_id(D0,4),(),a.state)
        self.assertEqual(result.reason,"PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED")
        self.assertFalse(history.forward_eligible)
        self.assertFalse(a.buy_eligible)

    def test_missing_calendar_day_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError,"CONTIGUOUS_PRIOR_CALENDAR_REQUIRED"):
            chain_reference_calendar_days((
                projected(D0,(2,),(2,)),
                projected(D2,(2,),(2,)),
            ))

    def test_history_start_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError,"HISTORY_START_MISMATCH"):
            chain_reference_calendar_days((
                projected(D0,(2,),(2,)),
                projected(D1,(2,),(2,),history_start=date(2025,7,2)),
            ))

    def test_counter_map_inconsistency_denied(self):
        p=projected(D0,(2,),(2,))
        maps=dict(p.state.counters)
        from collections import Counter
        maps["lw"]=Counter()
        damaged=replace(p,state=replace(p.state,counters=maps))
        with self.assertRaisesRegex(ValueError,"DAY_COUNTER_TOTALS_NOT_CONSISTENT"):
            chain_reference_calendar_days((damaged,))

    def test_empty_or_unchecked_input_cannot_pass(self):
        with self.assertRaisesRegex(ValueError,"NONEMPTY_CALENDAR_DAYS_REQUIRED"):
            chain_reference_calendar_days(())
        with self.assertRaisesRegex(ValueError,"DAY_HELD_PROJECTION_INVALID"):
            chain_reference_calendar_days((object(),))

    def test_course_only_one_day_no_approved_prediction(self):
        p=projected(D0,(),(2,3))
        result=chain_reference_calendar_days((p,))
        self.assertEqual(result.checkpoints[0].course_race_count_applied,0)
        self.assertEqual(result.checkpoints[0].state.completed_races,0)
        self.assertEqual(sum(result.checkpoints[0].state.counters["cs"].values()),0)
        self.assertEqual(result.k_only_days_not_used_in_reference,(D0,))


if __name__=="__main__":
    unittest.main()
