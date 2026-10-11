"""Offline counter parity against the ACTUAL research source AST, without DB.

Only two-phase/valid complete-race parity is established. The reference's
hday is independent of its scored days: skipped-feature and incomplete-course
history can affect cs/ct/rcs/rct even when no prediction row is scored. Those
non-parity cases are explicitly tested, not silently called PASS.
"""
from __future__ import annotations

import ast
import copy
import unittest
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path

from v5.offline_prior_day_factor_export import MAP_KEYS, NESTED, PriorDayCounters
from v5.offline_prior_day_counter_update import (
    FrozenRace, RaceResult, CourseFinish,
    freeze_day_predictions, roll_forward_day,
)

DAY1 = date(2026, 5, 1)
DAY2 = date(2026, 5, 2)
SOURCE = Path(__file__).resolve().parents[1] / "research/v5_strong_core_calibration_pg.py"


def _original_daily_updates():
    """Compile daily increments extracted from original main(), not a retyped formula."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    day_loop = next(n for n in main.body if isinstance(n, ast.For)
                    and ast.unparse(n.iter) == "sorted(days)")
    race_index = next(i for i, n in enumerate(day_loop.body)
                      if isinstance(n, ast.For)
                      and ast.unparse(n.iter) == "days[day]")
    race_loop = day_loop.body[race_index]
    win_index = next(i for i, n in enumerate(race_loop.body)
                     if isinstance(n, ast.Assign)
                     and any(isinstance(x, ast.Name) and x.id == "winner"
                             for x in n.targets))
    assert [ast.unparse(n.targets[0]) for n in day_loop.body[:2]] == ["gp", "priors"]
    assert "classes" in ast.unparse(race_loop.body[0])
    assert "dlw[winner]" in ast.unparse(race_loop.body[win_index])
    assert "cs[c]" in ast.unparse(day_loop.body[-1])
    original_subset = ast.For(
        target=copy.deepcopy(day_loop.target),
        iter=copy.deepcopy(day_loop.iter),
        body=[
            *copy.deepcopy(day_loop.body[2:race_index]),  # original daily deltas
            ast.For(target=copy.deepcopy(race_loop.target),
                    iter=copy.deepcopy(race_loop.iter),
                    body=[copy.deepcopy(race_loop.body[0]),  # original classes
                          *copy.deepcopy(race_loop.body[win_index:])],
                    orelse=[]),
            *copy.deepcopy(day_loop.body[race_index+1:]),  # original merges, hday
        ],
        orelse=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[original_subset], type_ignores=[]))
    return compile(module, str(SOURCE), "exec")


REFERENCE_UPDATES = _original_daily_updates()


def starting_state():
    c = {k: Counter() for k in MAP_KEYS - NESTED}
    for k in NESTED - {"vc"}:
        c[k] = {i: Counter() for i in range(1, 7)}
    c["vc"] = {}
    return PriorDayCounters(date(2026, 4, 30), date(2025, 7, 1),
                            0, c, "synthetic-reference-fixture-only")


def race(day: date, venue: int, number: int, racer_start: int = 4100):
    return FrozenRace(
        f"{day:%Y%m%d}_{venue:02d}_{number:02d}",
        tuple(racer_start + i for i in range(1, 7)),
        ("A1", "A2", "B1", "B2", "A1", "A2"),
        (3, 1, 4, 2, 6, 5),
        (),  # no-buy is still frozen, and still belongs to the outcome cohort
    )


def finish_rows(r: FrozenRace, *, missing_last=False):
    return tuple(CourseFinish(r.race_id, lane, r.racer_numbers[lane-1],
                              lane, lane if not (missing_last and lane == 6) else None)
                 for lane in range(1, 7))


def reference_counts(before, frozen, settled, history):
    """Run exact original increment statements, including independent hday."""
    fitted = {r.race_id: r for r in frozen.races
              if settled[r.race_id].status == "OFFICIAL"
              and settled[r.race_id].winner_lane is not None
              and settled[r.race_id].has_incident is False
              and settled[r.race_id].refund_boats == ()}
    q = copy.deepcopy(dict(before.counters))
    # Research initializes vc as defaultdict(Counter), not a plain dict.
    q["vc"] = defaultdict(Counter, q["vc"])
    loc = dict(q)
    loc.update(
        gn=before.completed_races,
        days={frozen.day.isoformat(): sorted(fitted)},
        wb={rid: settled[rid].winner_lane for rid in fitted},
        vb={rid: rid[9:11] for rid in fitted},
        by={rid: {lane: (
            r.racer_numbers[lane-1], r.racer_classes[lane-1],
            None, None, str(r.exhibition_ranks[lane-1])
        ) for lane in range(1, 7)} for rid, r in fitted.items()},
        hday={frozen.day.isoformat(): [
            (row.racer_number, row.start_course, row.finish_position)
            for row in history if row.start_course in range(1, 7)
            and row.finish_position in range(1, 7)
        ]},
        Counter=Counter, defaultdict=defaultdict,
    )
    exec(REFERENCE_UPDATES, {"Counter": Counter, "defaultdict": defaultdict}, loc)
    return {key: loc[key] for key in MAP_KEYS}


class TestOriginalResearchCounterParity(unittest.TestCase):
    def test_two_races_all_thirteen_counters_match_original(self):
        before = starting_state()
        a, b = race(DAY1, 24, 1), race(DAY1, 5, 3, 5000)
        frozen = freeze_day_predictions(before, DAY1, (b, a))
        settled = {
            a.race_id: RaceResult(a.race_id, "OFFICIAL", 2, False, ()),
            b.race_id: RaceResult(b.race_id, "OFFICIAL", 5, False, ()),
        }
        h = finish_rows(a) + finish_rows(b)
        done = roll_forward_day(before, frozen, tuple(settled.values()), h)
        expected = reference_counts(before, frozen, settled, h)
        self.assertEqual(set(expected), MAP_KEYS)
        for key in sorted(MAP_KEYS):
            with self.subTest(counter=key):
                self.assertEqual(done.state.counters[key], expected[key])
        self.assertEqual(done.state.completed_races, 2)
        self.assertEqual(done.course_rows_applied, 12)
        self.assertFalse(done.buy_eligible)

    def test_two_days_with_no_same_day_leakage(self):
        before = starting_state()
        a = race(DAY1, 24, 1)
        f1 = freeze_day_predictions(before, DAY1, (a,))
        r1 = {a.race_id: RaceResult(a.race_id, "OFFICIAL", 2, False, ())}
        h1 = finish_rows(a)
        d1 = roll_forward_day(before, f1, tuple(r1.values()), h1)
        self.assertEqual(d1.state.counters, reference_counts(before, f1, r1, h1))
        b = race(DAY2, 24, 1, 6000)
        f2 = freeze_day_predictions(d1.state, DAY2, (b,))
        r2 = {b.race_id: RaceResult(b.race_id, "OFFICIAL", 3, False, ())}
        h2 = finish_rows(b)
        d2 = roll_forward_day(d1.state, f2, tuple(r2.values()), h2)
        self.assertEqual(d2.state.counters, reference_counts(d1.state, f2, r2, h2))
        self.assertEqual(d2.state.completed_races, 2)
        self.assertEqual(before.completed_races, 0)

    def test_original_includes_valid_history_from_unscored_race_gap(self):
        before = starting_state()
        a = race(DAY1, 24, 1)
        unscored = race(DAY1, 5, 8, 7000)  # no complete valid exhibition/feature row
        frozen = freeze_day_predictions(before, DAY1, (a,))
        settled = {a.race_id: RaceResult(a.race_id, "OFFICIAL", 2, False, ())}
        scored_history = finish_rows(a)
        reference = reference_counts(before, frozen, settled,
                                     scored_history + finish_rows(unscored))
        done = roll_forward_day(before, frozen, tuple(settled.values()), scored_history)
        for key in MAP_KEYS - {"cs", "ct", "rcs", "rct"}:
            self.assertEqual(done.state.counters[key], reference[key])
        self.assertNotEqual(done.state.counters["cs"], reference["cs"])
        self.assertEqual(sum(reference["cs"].values()), 12)
        self.assertEqual(sum(done.state.counters["cs"].values()), 6)

    def test_original_accepts_valid_rows_even_when_one_course_invalid_gap(self):
        before = starting_state()
        a = race(DAY1, 24, 1)
        frozen = freeze_day_predictions(before, DAY1, (a,))
        settled = {a.race_id: RaceResult(a.race_id, "OFFICIAL", 2, False, ())}
        history = finish_rows(a, missing_last=True)
        done = roll_forward_day(before, frozen, tuple(settled.values()), history)
        reference = reference_counts(before, frozen, settled, history)
        self.assertEqual(done.state.completed_races, 1)
        self.assertEqual(done.course_rows_applied, 0)  # intentionally fail-closed
        self.assertEqual(sum(reference["cs"].values()), 5)
        self.assertEqual(sum(done.state.counters["cs"].values()), 0)
        self.assertEqual(done.state.counters["lw"], reference["lw"])


if __name__ == "__main__":
    unittest.main()
