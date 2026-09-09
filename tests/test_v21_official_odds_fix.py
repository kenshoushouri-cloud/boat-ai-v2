"""Offline regression tests for the realtime official-odds fix."""
from __future__ import annotations

import itertools
import math
import unittest
from pathlib import Path

import official_odds3t_parser as parser

ROOT = Path(__file__).resolve().parents[1]


def exact_values(lanes=(1, 2, 3, 4, 5, 6), start=10.0):
    tickets = [
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations(lanes, 3)
    ]
    return {ticket: start + i / 10 for i, ticket in enumerate(tickets, 1)}


def structural_html():
    firsts = (1, 2, 3, 4, 5, 6)
    tokens = []
    expected = {}
    counter = 0
    for second_group in range(5):
        second_by_first = {
            first: [x for x in firsts if x != first][second_group]
            for first in firsts
        }
        for third_row in range(4):
            for first in firsts:
                second = second_by_first[first]
                third = [x for x in firsts if x not in (first, second)][third_row]
                counter += 1
                odd = 10.0 + counter / 10.0
                if third_row == 0:
                    tokens.extend((str(second), str(third), f"{odd:.1f}"))
                else:
                    tokens.extend((str(third), f"{odd:.1f}"))
                expected[f"{first}-{second}-{third}"] = odd
    html = (
        "<html><body><h2>3連単オッズ</h2><table><tr><td>"
        + "</td><td>".join(tokens)
        + "</td></tr></table><p>締切時オッズは</p></body></html>"
    )
    return html, expected


class OfficialOddsFixTests(unittest.TestCase):
    def test_structural_current_layout_parses_exact_120(self):
        html, expected = structural_html()
        actual = parser.parse_official_odds3t(html)
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 120)
        self.assertTrue(parser.is_complete_snapshot(actual))

    def test_damaged_structural_layout_fails_closed(self):
        html, _ = structural_html()
        damaged = html.replace("<td>22.0</td>", "", 1)
        self.assertEqual(parser.parse_official_odds3t(damaged), {})

    def test_dynamic_complete_sets_accept_120_60_24(self):
        for lanes, count in (((1,2,3,4,5,6),120), ((1,2,3,4,5),60), ((1,2,3,4),24)):
            with self.subTest(lanes=lanes):
                values = exact_values(lanes)
                self.assertEqual(len(values), count)
                self.assertTrue(parser.is_complete_snapshot(values))
                self.assertEqual(len(parser.complete_snapshot_ticket_set(values)), count)

    def test_partial_sets_rejected_even_above_old_80_threshold(self):
        values = exact_values()
        for count in (80, 97, 117, 118, 119):
            with self.subTest(count=count):
                partial = dict(list(values.items())[:count])
                self.assertFalse(parser.is_complete_snapshot(partial))
                chosen, source = parser.choose_realtime_snapshot({}, partial)
                self.assertEqual(chosen, {})
                self.assertEqual(source, "unavailable_incomplete")

    def test_invalid_extra_or_nonfinite_values_rejected(self):
        for replacement in (math.nan, math.inf, 0.0, -1.0, "bad"):
            with self.subTest(replacement=replacement):
                values = exact_values()
                values[next(iter(values))] = replacement
                self.assertFalse(parser.is_complete_snapshot(values))
        values = exact_values()
        values["bad-ticket"] = 9.9
        self.assertFalse(parser.is_complete_snapshot(values))

    def test_complete_official_wins_over_complete_base(self):
        official = exact_values(start=20.0)
        base = exact_values(start=30.0)
        chosen, source = parser.choose_realtime_snapshot(official, base)
        self.assertEqual(chosen, official)
        self.assertEqual(source, "official_odds3t")

    def test_only_complete_base_can_fallback(self):
        base = exact_values((1,2,3,4,5), start=30.0)
        chosen, source = parser.choose_realtime_snapshot({}, base)
        self.assertEqual(chosen, base)
        self.assertEqual(source, "v2_odds_trifecta_fallback_complete")

    def test_final_pipeline_routes_to_safe_collector(self):
        text = (ROOT / "v25_final_realtime_pipeline_pg.py").read_text(encoding="utf-8")
        self.assertIn('[sys.executable, "v21_realtime_collector_pg_safe.py"]', text)
        self.assertNotIn('[sys.executable, "v21_realtime_collector_pg.py"]', text)

    def test_learning_pipeline_routes_to_safe_collector(self):
        text = (ROOT / "run_learning_all_realtime_pg.py").read_text(encoding="utf-8")
        self.assertIn('collector = base_dir / "v21_realtime_collector_pg_safe.py"', text)
        self.assertNotIn('collector = base_dir / "v21_realtime_collector_pg.py"', text)

    def test_safe_collector_has_no_old_len80_fallback(self):
        text = (ROOT / "v21_realtime_collector_pg_safe.py").read_text(encoding="utf-8")
        self.assertIn("choose_realtime_snapshot", text)
        self.assertNotIn("len(od)<80", text.replace(" ", ""))
        self.assertNotIn("len(od) < 80", text)
        self.assertIn("unavailable_incomplete", (ROOT / "official_odds3t_parser.py").read_text(encoding="utf-8"))

    def test_safe_collector_uses_dynamic_persistence_path(self):
        text = (ROOT / "v21_realtime_collector_pg_safe.py").read_text(encoding="utf-8")
        self.assertIn("def _save_complete_odds", text)
        self.assertIn("complete_snapshot_ticket_set(odds)", text)
        self.assertIn("_save_complete_odds(race, odds, source)", text)
        self.assertNotIn("legacy.save_odds(race, odds, source)", text)


if __name__ == "__main__":
    unittest.main()
