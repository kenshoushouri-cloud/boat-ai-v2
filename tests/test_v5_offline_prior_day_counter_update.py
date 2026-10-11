"""No DB, Actions, Forward or BUY: test two-phase daily Counter updates."""
from __future__ import annotations

import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import date

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters
from v5.offline_prior_day_counter_update import (
    CourseFinish, FrozenRace, RaceResult, freeze_day_predictions, roll_forward_day,
)

DAY = date(2026, 5, 1)


def state():
    c = {k: Counter() for k in MAP_KEYS - NESTED}
    for k in NESTED - {"vc"}:
        c[k] = {i: Counter() for i in range(1, 7)}
    c["vc"] = {}
    return PriorDayCounters(date(2026, 4, 30), date(2025, 7, 1),
                            0, c, "offline-fixture-not-verified")


def predicted(n=1):
    return FrozenRace(f"20260501_24_{n:02d}", tuple(4100+i for i in range(1,7)),
                      ("A1", "A2", "B1", "B2", "A1", "A2"),
                      (3, 1, 4, 2, 6, 5), ((2, 1, 5),))


def outcome(n=1, *, winner=2, status="OFFICIAL", incident=False, refund=()):
    return RaceResult(predicted(n).race_id, status, winner, incident, refund)


def histories(n=1):
    return tuple(CourseFinish(predicted(n).race_id, i, 4100+i, i, i)
                 for i in range(1, 7))


class TestDailyCounterUpdate(unittest.TestCase):
    def test_exact_counter_keys_and_research_increments(self):
        previous = state()
        original = deepcopy(previous.counters)
        frozen = freeze_day_predictions(previous, DAY, (predicted(),))
        self.assertFalse(frozen.buy_eligible)
        self.assertEqual(previous.counters, original)  # freezing does not train
        done = roll_forward_day(previous, frozen, (outcome(),), histories())
        q = done.state.counters
        self.assertEqual(set(q), MAP_KEYS)
        self.assertEqual(done.state.completed_races, 1)
        self.assertEqual(done.state.fitted_through, DAY)
        self.assertEqual(q["lw"][2], 1)
        self.assertEqual(q["lcs"][1]["A1"], 1)
        self.assertEqual(q["lcs"][6]["A2"], 1)
        self.assertEqual(q["lcw"][2]["A2"], 1)
        self.assertEqual(q["rks"][(1, "A1", "3")], 1)
        self.assertEqual(q["rkw"][(2, "A2", "1")], 1)
        self.assertEqual(sum(q["ps"].values()), 30)
        self.assertEqual(sum(q["pw"].values()), 5)
        self.assertEqual(q["ps"][(3,"B1",1,"A1")], 1)
        self.assertEqual(q["pw"][(2,"A2",1,"A1")], 1)
        self.assertEqual(q["vc"]["24"][2], 1)
        self.assertEqual(q["vn"]["24"], 1)
        self.assertEqual(sum(q["cs"].values()), 6)
        self.assertEqual(sum(q["ct"].values()), 3)
        self.assertEqual(q["rcs"][4][4104], 1)
        self.assertEqual(q["rct"][4][4104], 0)
        self.assertEqual(done.course_rows_applied, 6)
        self.assertEqual(previous.counters, original)
        self.assertFalse(done.buy_eligible)

    def test_results_of_one_race_cannot_update_before_all_day_predictions(self):
        previous = state()
        frozen = freeze_day_predictions(previous, DAY, (predicted(2), predicted(1)))
        with self.assertRaisesRegex(ValueError, "OUTCOMES_MISSING"):
            roll_forward_day(previous, frozen, (outcome(1),))
        self.assertEqual(previous.completed_races, 0)
        done = roll_forward_day(previous, frozen, (outcome(2), outcome(1)))
        self.assertEqual(done.state.completed_races, 2)
        self.assertEqual(done.fitted_race_ids,
                         (predicted(1).race_id, predicted(2).race_id))
        with self.assertRaisesRegex(ValueError, "FROZEN_BASELINE"):
            roll_forward_day(done.state, frozen, (outcome(1), outcome(2)))

    def test_post_prediction_void_pending_fl_refund_not_dropped(self):
        previous = state()
        frozen = freeze_day_predictions(previous, DAY,
                                        tuple(predicted(i) for i in range(1,5)))
        all_results = (
            outcome(1, winner=None, status="VOID", incident=None, refund=None),
            outcome(2, winner=None, status="PENDING", incident=None, refund=None),
            outcome(3, incident=True, refund=()),
            outcome(4, incident=False, refund=(2,)),
        )
        done = roll_forward_day(previous, frozen, all_results,
                                histories(3)+histories(4))
        self.assertEqual(done.all_results, all_results)
        self.assertEqual(len(done.all_results), 4)
        self.assertEqual(len(done.all_course_rows), 12)
        self.assertEqual(done.fitted_race_ids, ())
        self.assertEqual(done.course_rows_applied, 0)
        self.assertEqual(done.state.completed_races, 0)

    def test_unknown_refund_is_not_no_refund(self):
        p = state()
        f = freeze_day_predictions(p, DAY, (predicted(),))
        done = roll_forward_day(p, f, (outcome(refund=None),), histories())
        self.assertEqual(done.state.completed_races, 0)
        self.assertEqual(done.all_results[0].refund_boats, None)

    def test_reject_duplicate_or_extra_results(self):
        p = state()
        f = freeze_day_predictions(p, DAY, (predicted(),))
        for rs in ((outcome(), outcome()), (outcome(2),)):
            with self.assertRaises(ValueError):
                roll_forward_day(p, f, rs)

    def test_reject_partial_course_rows_or_wrong_racer(self):
        p = state()
        f = freeze_day_predictions(p, DAY, (predicted(),))
        with self.assertRaisesRegex(ValueError, "PARTIAL_COURSE_HISTORY"):
            roll_forward_day(p, f, (outcome(),), histories()[:-1])
        rows = list(histories())
        rows[0] = replace(rows[0], racer_number=8888)
        with self.assertRaisesRegex(ValueError, "COURSE_ROW_INVALID"):
            roll_forward_day(p, f, (outcome(),), tuple(rows))

    def test_baseline_counter_tampering_rejected(self):
        p = state()
        f = freeze_day_predictions(p, DAY, (predicted(),))
        p.counters["ps"][(1,"A1",2,"A2")] += 1
        with self.assertRaisesRegex(ValueError, "FROZEN_BASELINE"):
            roll_forward_day(p, f, (outcome(),))

    def test_same_day_and_bad_tickets_rejected(self):
        p = state()
        with self.assertRaises(ValueError):
            freeze_day_predictions(replace(p, fitted_through=DAY),
                                   DAY, (predicted(),))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TICKETS"):
            bad = replace(predicted(), selected_tickets=((2,1,5),(2,1,5)))
            freeze_day_predictions(p, DAY, (bad,))
        with self.assertRaisesRegex(ValueError, "CROSS_DAY_RACE"):
            freeze_day_predictions(p, DAY,
                                   (replace(predicted(),race_id="20260502_24_01"),))
        with self.assertRaises(ValueError):
            freeze_day_predictions(p, DAY, (predicted(),predicted()))

    def test_invalid_history_values_never_affect_frozen_predictions(self):
        p = state()
        frozen = freeze_day_predictions(p, DAY, (predicted(),))
        rows = list(histories())
        rows[0] = replace(rows[0], finish_position=None)
        done = roll_forward_day(p, frozen, (outcome(),), tuple(rows))
        self.assertEqual(done.state.completed_races, 1)
        self.assertEqual(done.course_rows_applied, 0)
        self.assertEqual(sum(done.state.counters["cs"].values()), 0)


if __name__ == "__main__":
    unittest.main()
