"""Offline-only V5 two-population retrospective day guard tests.

Synthetic fixtures only: NO actual SQL, HTTP, credential, Forward or BUY.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from v5.offline_retrospective_counter_seed import (
    RetrospectiveKBoat, RetrospectiveResearchRace,
)
from v5.offline_research_two_population_day import (
    CourseKBoat, CourseHistoryRace, project_two_population_day,
)

DAY = date(2026, 10, 20)


def fit(rid="20261020_21_02"):
    rank=(3, 1, 4, 2, 6, 5)
    boats=tuple(
        RetrospectiveKBoat(
            lane=i, racer_number=4210+i,
            racer_class=("A1","A2","B1","B2","A1","B1")[i-1],
            exhibition_rank=rank[i-1],
            start_course=i,
            finish_position=(2,1,3,4,5,6)[i-1],
            is_flying=False, is_late=False,
        ) for i in range(1,7)
    )
    return RetrospectiveResearchRace(
        rid,2,boats,"OFFICIAL",True,(),
    )


def k_course(rid="20261020_21_02",shift=0):
    boats=tuple(
        CourseKBoat(
            lane=i, racer_number=4210+i+shift,
            start_course=i, finish_position=(2,1,3,4,5,6)[i-1],
            is_flying=False, is_late=False,
        ) for i in range(1,7)
    )
    return CourseHistoryRace(rid,boats,"OFFICIAL",True,())


class TestV5TwoPopulationOffline(unittest.TestCase):
    def test_course_population_accepts_no_exhibition_other_race(self):
        a=project_two_population_day(
            DAY, (fit(),),
            (k_course(),k_course("20261020_21_03")),
        )
        self.assertEqual(a.fit_race_ids, ("20261020_21_02",))
        self.assertEqual(a.course_race_ids,
                         ("20261020_21_02","20261020_21_03"))
        self.assertEqual(a.state.completed_races,1)
        self.assertEqual(a.state.counters["lw"][2],1)
        self.assertEqual(sum(a.state.counters["lcs"][1].values()),1)
        self.assertEqual(sum(a.state.counters["cs"].values()),12)
        self.assertEqual(sum(a.state.counters["ct"].values()),6)
        self.assertEqual(a.state.counters["rcs"][2][4212],2)
        self.assertEqual(sum(a.state.counters["ps"].values()),30)
        self.assertFalse(a.first_observation_verified)
        self.assertFalse(a.forward_eligible)
        self.assertFalse(a.buy_eligible)

    def test_only_course_records_do_not_fit_exhibition_factors(self):
        x=project_two_population_day(DAY,(),(k_course(),))
        self.assertEqual(x.state.completed_races,0)
        self.assertEqual(sum(x.state.counters["cs"].values()),6)
        self.assertEqual(sum(x.state.counters["rks"].values()),0)

    def test_fit_missing_from_independent_k_set_rejected(self):
        with self.assertRaisesRegex(ValueError,"NO_APPROVED_K_HISTORY"):
            project_two_population_day(DAY,(fit(),),())

    def test_overlap_conflict_refused_even_if_both_shapes_valid(self):
        with self.assertRaisesRegex(ValueError,"MODEL_FIT_AND_K_SOURCE_CONFLICT"):
            project_two_population_day(DAY,(fit(),),(k_course(shift=100),))

    def test_k_missing_course_cannot_join_fit(self):
        k=k_course()
        boats=list(k.boats)
        boats[2]=replace(boats[2],start_course=None)
        with self.assertRaisesRegex(ValueError,"NO_APPROVED_K_HISTORY"):
            project_two_population_day(DAY,(fit(),),(replace(k,boats=tuple(boats)),))

    def test_k_unknown_refund_is_excluded_retroactively(self):
        k=replace(k_course(),refund_boats=None)
        out=project_two_population_day(DAY,(),(k,))
        self.assertEqual(out.course_race_ids,())
        self.assertEqual(out.course_excluded[0][1],
                         "K_INCIDENT_OR_REFUND_UNKNOWN_OR_PRESENT")
        self.assertEqual(sum(out.state.counters["cs"].values()),0)

    def test_k_duplicate_race_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_K_RACE"):
            project_two_population_day(DAY,(),(k_course(),k_course()))

    def test_k_cross_day_and_flying_excluded(self):
        k=k_course()
        rows=list(k.boats)
        rows[0]=replace(rows[0],is_flying=True)
        res=project_two_population_day(
            DAY,(),
            (k_course("20261019_21_02"),replace(k,boats=tuple(rows))),
        )
        self.assertEqual(len(res.course_excluded),2)
        self.assertEqual(res.course_race_ids,())
        self.assertIn("K_CROSS_DAY",dict(res.course_excluded).values())
        self.assertIn("K_RACER_OR_FLAGS_INVALID",dict(res.course_excluded).values())


if __name__=="__main__":
    unittest.main()
