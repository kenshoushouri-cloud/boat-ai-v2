"""Offline course-history arithmetic parity against the original research AST.

This test executes the exact cs/ct/rcs/rct update loop extracted from
research/v5_strong_core_calibration_pg.py. It deliberately separates arithmetic
parity from evidence eligibility: missing refund proof or contradictory courses
are held by V5 even when the old arithmetic would have counted those rows.
Not a test of real database provenance, complete coverage, settlement or ROI.
"""
from __future__ import annotations

import ast
import copy
import unittest
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters
from v5.offline_prior_day_counter_update import (
    FrozenRace, RaceResult, freeze_day_predictions,
)
from v5.offline_evidenced_course_history import (
    EvidencedCourseRace, EvidencedCourseRow, apply_evidenced_course_history,
)

DAY = date(2026, 5, 1)
RESEARCH = Path(__file__).resolve().parents[1] / "research/v5_strong_core_calibration_pg.py"
COURSE_KEYS = ("cs", "ct", "rcs", "rct")


def original_hday_loop():
    """Compile the original hday update loop, not a retyped calculation."""
    tree = ast.parse(RESEARCH.read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    daily = next(n for n in main.body
                 if isinstance(n, ast.For)
                 and ast.unparse(n.iter) == "sorted(days)")
    history = next(n for n in daily.body
                   if isinstance(n, ast.For)
                   and ast.unparse(n.iter) == "hday.get(day, [])")
    assert ast.unparse(history.target) == "(racer, c, f)"
    assert "rcs[c][racer]" in ast.unparse(history)
    assert "rct[c][racer]" in ast.unparse(history)
    return compile(ast.fix_missing_locations(
        ast.Module(body=[copy.deepcopy(history)], type_ignores=[])),
        str(RESEARCH), "exec")


ORIGINAL_LOOP = original_hday_loop()


def baseline():
    counters = {key: Counter() for key in MAP_KEYS - NESTED}
    for key in NESTED - {"vc"}:
        counters[key] = {lane: Counter() for lane in range(1, 7)}
    counters["vc"] = {}
    return PriorDayCounters(date(2026, 4, 30), date(2025, 7, 1),
                            0, counters, "synthetic-parity-only")


def candidate(number=1):
    return FrozenRace(f"20260501_24_{number:02d}",
                      tuple(4100 + i for i in range(1, 7)),
                      ("A1", "A2", "B1", "B2", "A1", "A2"),
                      (3, 1, 4, 2, 6, 5), ())


def evidence(number=1, racer_start=4100, refund=()):
    return EvidencedCourseRace(
        f"20260501_24_{number:02d}",
        "OFFICIAL", "OFFICIAL", True, True, refund,
        tuple(EvidencedCourseRow(
            lane, racer_start + lane, lane, lane, f"{lane:02d}", False, False)
            for lane in range(1, 7)),
        "synthetic-official-status-not-independently-verified",
    )


def update(histories):
    prior = baseline()
    frozen = freeze_day_predictions(prior, DAY, (candidate(),))
    result = RaceResult(candidate().race_id, "OFFICIAL", 1, False, ())
    done = apply_evidenced_course_history(prior, frozen, (result,), histories)
    return prior, done


def original_delta(histories):
    """Original numeric hday validity filter; evidence gating is separate."""
    rows = []
    for h in histories:
        for row in h.rows:
            if (type(row.racer_number) is int and row.racer_number > 0
                    and type(row.start_course) is int and row.start_course in range(1, 7)
                    and type(row.finish_position) is int
                    and row.finish_position in range(1, 7)):
                rows.append((row.racer_number, row.start_course, row.finish_position))
    env = {
        "day": DAY.isoformat(),
        "hday": {DAY.isoformat(): rows},
        "cs": Counter(), "ct": Counter(),
        "rcs": {i: Counter() for i in range(1, 7)},
        "rct": {i: Counter() for i in range(1, 7)},
    }
    exec(ORIGINAL_LOOP, {}, env)
    return {key: env[key] for key in COURSE_KEYS}


class TestCourseHistoryParity(unittest.TestCase):
    def assert_course_equal(self, actual, expected):
        for key in COURSE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(actual.state.counters[key], expected[key])

    def test_complete_normal_predicted_race_matches_all_four(self):
        histories = (evidence(),)
        _, done = update(histories)
        self.assert_course_equal(done, original_delta(histories))
        self.assertEqual(done.increments, {"cs":6, "ct":3, "rcs":6, "rct":3})

    def test_feature_missing_race_still_matches_old_hday(self):
        # The second race was never frozen/scored for prediction.
        histories = (evidence(), evidence(2, racer_start=5000))
        prior, done = update(histories)
        self.assert_course_equal(done, original_delta(histories))
        self.assertEqual(done.increments, {"cs":12, "ct":6, "rcs":12, "rct":6})
        self.assertEqual(done.state.completed_races, 1)
        self.assertEqual(prior.completed_races, 0)

    def test_partly_invalid_numeric_course_row_matches_old_hday(self):
        rowset = evidence().rows
        histories = (replace(evidence(),
                             rows=rowset[:-1]+(replace(rowset[-1],
                                                      finish_position=None),)),)
        _, done = update(histories)
        self.assert_course_equal(done, original_delta(histories))
        self.assertEqual(done.skipped_invalid_rows,
                         ((evidence().race_id, 6),))
        self.assertEqual(done.increments["cs"], 5)

    def test_refund_unknown_intentionally_holds_even_if_old_math_counts(self):
        histories = (evidence(2, racer_start=5000, refund=None),)
        _, done = update(histories)
        ref = original_delta(histories)
        self.assertEqual(done.increments["cs"], 0)
        self.assertEqual(sum(ref["cs"].values()), 6)
        self.assertEqual(done.held_races,
                         ((histories[0].race_id, "REFUND_OR_FROZEN_RESULT_UNRESOLVED"),))
        self.assertEqual(done.all_course_evidence, histories)

    def test_conflicting_duplicate_course_intentionally_holds(self):
        h = evidence(2, racer_start=5000)
        h = replace(h, rows=h.rows[:1]+
                    (replace(h.rows[1], start_course=1),)+h.rows[2:])
        _, done = update((h,))
        self.assertEqual(done.increments["cs"], 0)
        self.assertEqual(sum(original_delta((h,))["cs"].values()), 6)
        self.assertEqual(done.held_races,
                         ((h.race_id, "DUPLICATE_VALID_COURSE_OR_FINISH"),))

    def test_unverified_official_and_k_void_status_fail_closed(self):
        for change in ({"official_result_verified": False},
                       {"official_k_void_checked_clear": None}):
            with self.subTest(change=change):
                h = replace(evidence(2, racer_start=5000), **change)
                _, done = update((h,))
                self.assertEqual(done.increments["cs"], 0)
                self.assertEqual(done.held_races,
                                 ((h.race_id, "OFFICIAL_OR_VOID_EVIDENCE_MISSING"),))


if __name__ == "__main__":
    unittest.main()
