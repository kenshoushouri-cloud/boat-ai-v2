"""Offline V5 one-day retrospective Counter contribution regression.

Synthetic inputs only. Never a predecision freeze, Forward audit or BUY path.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from v5.offline_prior_day_factor_export import MAP_KEYS
from v5.offline_retrospective_counter_seed import (
    RetrospectiveKBoat, RetrospectiveResearchRace,
    project_one_retrospective_day,
)

DAY = date(2026, 10, 20)


def row(
    *, race_id="20261020_21_02", incident=False,
    refund=(), status="OFFICIAL",
):
    boats = tuple(
        RetrospectiveKBoat(
            lane=i, racer_number=4200 + i,
            racer_class=("A1", "A2", "B1", "B2", "A1", "B1")[i-1],
            exhibition_rank=(3, 1, 4, 2, 6, 5)[i-1],
            start_course=i,
            finish_position=(2, 1, 3, 4, 5, 6)[i-1],
            is_flying=False, is_late=False,
        ) for i in range(1, 7)
    )
    return RetrospectiveResearchRace(
        race_id, 2, boats, status, incident, refund,
    )


class TestHeldRetrospectiveCounterProjection(unittest.TestCase):
    def test_one_day_all_13_counter_contributions(self):
        out = project_one_retrospective_day(DAY, (row(),))
        q = out.state.counters
        self.assertEqual(set(q), MAP_KEYS)
        self.assertEqual(out.accepted_race_ids, ("20261020_21_02",))
        self.assertEqual(out.excluded, ())
        self.assertEqual(out.state.completed_races, 1)
        self.assertEqual(out.state.fitted_through, DAY)
        self.assertEqual(q["lw"][2], 1)
        self.assertEqual(q["lcs"][2]["A2"], 1)
        self.assertEqual(q["lcw"][2]["A2"], 1)
        self.assertEqual(q["rks"][(2, "A2", "1")], 1)
        self.assertEqual(q["rkw"][(2, "A2", "1")], 1)
        self.assertEqual(sum(q["ps"].values()), 30)
        self.assertEqual(sum(q["pw"].values()), 5)
        self.assertEqual(q["vc"]["21"][2], 1)
        self.assertEqual(q["vn"]["21"], 1)
        self.assertEqual(sum(q["cs"].values()), 6)
        self.assertEqual(sum(q["ct"].values()), 3)
        self.assertEqual(q["rcs"][5][4205], 1)
        self.assertEqual(q["rct"][5][4205], 0)
        self.assertTrue(out.reconstructed_only)
        self.assertFalse(out.original_first_observation_verified)
        self.assertFalse(out.forward_eligible)
        self.assertFalse(out.buy_eligible)

    def test_unknown_refunds_and_incident_proof_fail_closed(self):
        samples = (
            row(refund=None),
            row(incident=None),
            row(status="PENDING"),
        )
        for item in samples:
            with self.subTest(race=item.race_id, status=item.result_status):
                out = project_one_retrospective_day(DAY, (item,))
                self.assertEqual(out.state.completed_races, 0)
                self.assertEqual(len(out.excluded), 1)
                self.assertFalse(out.buy_eligible)

    def test_invalid_k_finish_or_course_is_excluded(self):
        sample = row()
        for attr,value in (("finish_position", None), ("start_course", None)):
            boats = list(sample.boats)
            boats[2] = replace(boats[2], **{attr:value})
            out = project_one_retrospective_day(DAY, (replace(sample,boats=tuple(boats)),))
            self.assertEqual(out.state.completed_races, 0)
            self.assertEqual(out.excluded[0][1],
                             "SIX_LANES_COURSES_FINISHES_INVALID")

    def test_f_or_l_flags_cannot_enter_history(self):
        sample = row()
        boats = list(sample.boats)
        boats[0] = replace(boats[0], is_flying=True)
        out = project_one_retrospective_day(DAY, (replace(sample, boats=tuple(boats)),))
        self.assertEqual(out.state.completed_races, 0)
        self.assertEqual(out.excluded[0][1],
                         "SIX_K_FIELDS_OR_EXHIBITION_INVALID")

    def test_conflicting_k_winner_rejected(self):
        sample = row()
        out = project_one_retrospective_day(DAY, (replace(sample, winner_lane=3),))
        self.assertEqual(out.state.completed_races, 0)
        self.assertEqual(out.excluded[0][1], "OFFICIAL_WINNER_K_CONFLICT")

    def test_cross_day_is_not_accepted(self):
        sample = row(race_id="20261019_21_02")
        out = project_one_retrospective_day(DAY, (sample,))
        self.assertEqual(out.state.completed_races, 0)
        self.assertEqual(out.excluded[0][1], "RACE_NOT_SELECTED_DAY")

    def test_duplicate_source_race_rejected(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_RACE_ID"):
            project_one_retrospective_day(DAY,(row(),row()))

    def test_projection_not_full_historical_prior_state(self):
        out = project_one_retrospective_day(DAY, ())
        self.assertIn("NOT_FULL_HISTORY", out.reason)
        self.assertEqual(out.state.completed_races, 0)
        self.assertTrue(out.state.source_ref.startswith("RETROSPECTIVE_"))
        self.assertFalse(out.forward_eligible)


if __name__ == "__main__":
    unittest.main()
