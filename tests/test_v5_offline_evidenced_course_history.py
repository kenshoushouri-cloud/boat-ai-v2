"""Fast DB-free tests: history-only evidence with one daily freeze barrier."""
from __future__ import annotations

import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import date

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters
from v5.offline_prior_day_counter_update import (
    FrozenRace, RaceResult, freeze_day_predictions,
)
from v5.offline_evidenced_course_history import (
    EvidencedCourseRace, EvidencedCourseRow, apply_evidenced_course_history,
)

DAY = date(2026, 5, 1)


def state():
    c = {k: Counter() for k in MAP_KEYS - NESTED}
    for key in NESTED - {"vc"}:
        c[key] = {lane: Counter() for lane in range(1, 7)}
    c["vc"] = {}
    return PriorDayCounters(date(2026, 4, 30), date(2025, 7, 1),
                            0, c, "offline-only-history-test")


def predicted(race_no=1):
    return FrozenRace(f"20260501_24_{race_no:02d}",
                      tuple(4000+i for i in range(1, 7)),
                      ("A1", "A2", "B1", "B2", "A1", "A2"),
                      (3, 1, 4, 2, 6, 5), ())  # NO BUY still frozen


def result(race_no=1, **kwargs):
    return RaceResult(f"20260501_24_{race_no:02d}", "OFFICIAL", 2,
                      kwargs.get("incident", False), kwargs.get("refund", ()))


def history(race_no=1, *, racer_start=4000, refund=()):
    return EvidencedCourseRace(
        f"20260501_24_{race_no:02d}", "OFFICIAL", "OFFICIAL",
        True, True, refund,
        tuple(EvidencedCourseRow(
            lane, racer_start+lane, lane, lane, f"{lane:02d}", False, False
        ) for lane in range(1, 7)),
        "caller-official-reference-not-independent-proof",
    )


class TestEvidencedHistory(unittest.TestCase):
    def frozen(self):
        prior = state()
        return prior, freeze_day_predictions(prior, DAY, (predicted(),))

    def test_scored_and_feature_missing_unscored_race_both_increment_once(self):
        prior, frozen = self.frozen()
        original = deepcopy(prior.counters)
        done = apply_evidenced_course_history(
            prior, frozen, (result(),),
            (history(1), history(2, racer_start=5000)))
        self.assertEqual(done.day_update.state.completed_races, 1)
        self.assertEqual(done.day_update.course_rows_applied, 0)
        self.assertEqual(done.state.completed_races, 1)
        self.assertEqual(done.applied_race_ids,
                         ("20260501_24_01", "20260501_24_02"))
        self.assertEqual(done.increments, {"cs":12, "ct":6, "rcs":12, "rct":6})
        self.assertEqual(done.state.counters["rcs"][1][5001], 1)
        self.assertEqual(done.state.counters["cs"][1], 2)
        self.assertEqual(done.state.counters["lw"][2], 1)
        self.assertEqual(prior.counters, original)
        self.assertEqual(len(done.day_update.all_results), 1)
        self.assertFalse(done.buy_eligible)
        self.assertFalse(done.evidence_provenance_independently_verified)

    def test_one_invalid_numeric_row_keeps_five_valid_rows(self):
        prior, frozen = self.frozen()
        h = history()
        last = replace(h.rows[-1], finish_position=None)
        h = replace(h, rows=h.rows[:-1]+(last,))
        done = apply_evidenced_course_history(prior, frozen, (result(),), (h,))
        self.assertEqual(done.skipped_invalid_rows, ((h.race_id, 6),))
        self.assertEqual(done.increments, {"cs":5, "ct":3, "rcs":5, "rct":3})
        self.assertEqual(done.state.counters["cs"][6], 0)

    def test_refunds_void_incident_and_unknown_are_held_not_omitted(self):
        prior, frozen = self.frozen()
        cases = (
            (history(2,refund=None), "REFUND_OR_FROZEN_RESULT_UNRESOLVED"),
            (history(3,refund=(2,)), "REFUND_OR_FROZEN_RESULT_UNRESOLVED"),
            (replace(history(4), official_k_void_checked_clear=False),
             "OFFICIAL_OR_VOID_EVIDENCE_MISSING"),
            (replace(history(5), rows=history(5).rows[:-1]+
                     (replace(history(5).rows[-1], is_flying=True),)),
             "INCIDENT_OR_SIX_RESULT_EVIDENCE_MISSING"),
            (replace(history(6), official_result_verified=False),
             "OFFICIAL_OR_VOID_EVIDENCE_MISSING"),
        )
        done = apply_evidenced_course_history(
            prior, frozen, (result(),), tuple(r for r, _ in cases))
        self.assertEqual(done.applied_race_ids, ())
        self.assertEqual(dict(done.held_races),
                         {r.race_id: expected for r, expected in cases})
        self.assertEqual(len(done.all_course_evidence), len(cases))
        self.assertEqual(sum(done.state.counters["cs"].values()), 0)

    def test_frozen_incident_or_refund_cannot_be_overridden_by_evidence(self):
        for kwargs in ({"incident": True}, {"refund": None}, {"refund": (2,)}):
            with self.subTest(kwargs=kwargs):
                prior, frozen = self.frozen()
                done = apply_evidenced_course_history(
                    prior, frozen, (result(**kwargs),), (history(),))
                self.assertEqual(done.applied_race_ids, ())
                self.assertEqual(done.held_races,
                                 ((history().race_id, "REFUND_OR_FROZEN_RESULT_UNRESOLVED"),))

    def test_duplicate_race_lane_and_conflicting_identity_are_rejected(self):
        prior, frozen = self.frozen()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_HISTORY_RACE"):
            apply_evidenced_course_history(
                prior, frozen, (result(),), (history(), history()))
        h=history(2)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_HISTORY_LANE"):
            bad=replace(h,rows=h.rows[:-1]+(h.rows[0],))
            apply_evidenced_course_history(prior, frozen, (result(),), (bad,))
        mismatch = history(1, racer_start=9000)
        done = apply_evidenced_course_history(
            prior, frozen, (result(),), (mismatch,))
        self.assertEqual(done.held_races,
                         ((mismatch.race_id, "FROZEN_RACER_IDENTITY_MISMATCH"),))

    def test_bad_course_or_finish_duplicate_held(self):
        prior, frozen = self.frozen()
        h = history(2)
        second = replace(h.rows[1], start_course=1)
        duplicated = replace(h, rows=(h.rows[0], second) + h.rows[2:])
        done = apply_evidenced_course_history(
            prior, frozen, (result(),), (duplicated,))
        self.assertEqual(done.held_races,
                         ((duplicated.race_id, "DUPLICATE_VALID_COURSE_OR_FINISH"),))

    def test_date_leakage_zero_predictions_and_incomplete_results_blocked(self):
        prior, frozen = self.frozen()
        with self.assertRaisesRegex(ValueError, "HISTORY_DAY_MISMATCH"):
            apply_evidenced_course_history(
                prior, frozen, (result(),),
                (replace(history(2), race_id="20260502_24_02"),))
        with self.assertRaisesRegex(ValueError, "DAY_PREDICTIONS_REQUIRED"):
            freeze_day_predictions(prior, DAY, ())
        with self.assertRaisesRegex(ValueError, "OUTCOMES_MISSING"):
            apply_evidenced_course_history(prior, frozen, (), (history(),))
        self.assertEqual(sum(prior.counters["cs"].values()), 0)


if __name__ == "__main__":
    unittest.main()
