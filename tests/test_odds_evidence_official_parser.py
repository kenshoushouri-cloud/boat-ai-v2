"""Offline regression tests for the side-effect-free official 3T parser."""
from __future__ import annotations

import math
import unittest

import official_odds3t_parser as parser


def complete_values(start: float = 10.0) -> dict[str, float]:
    return {
        ticket: start + index / 10.0
        for index, ticket in enumerate(parser.CANONICAL_TICKETS, 1)
    }


def structural_html() -> tuple[str, dict[str, float]]:
    firsts = (1, 2, 3, 4, 5, 6)
    tokens: list[str] = []
    expected: dict[str, float] = {}
    counter = 0
    for second_group in range(5):
        second_by_first = {
            first: [x for x in firsts if x != first][second_group]
            for first in firsts
        }
        for third_row in range(4):
            for first in firsts:
                second = second_by_first[first]
                third = [
                    x for x in firsts if x not in (first, second)
                ][third_row]
                counter += 1
                odd = 10.0 + counter / 10.0
                if third_row == 0:
                    tokens.extend((str(second), str(third), f"{odd:.1f}"))
                else:
                    tokens.extend((str(third), f"{odd:.1f}"))
                expected[f"{first}-{second}-{third}"] = odd
    assert counter == 120
    assert len(tokens) == 270
    html = (
        "<html><body><h2>3連単オッズ</h2><table><tr><td>"
        + "</td><td>".join(tokens)
        + "</td></tr></table><p>締切時オッズは</p></body></html>"
    )
    return html, expected


class OfficialOddsParserTests(unittest.TestCase):
    def test_structural_table_parses_exact_canonical_120(self):
        html, expected = structural_html()
        actual = parser.parse_official_odds3t(html)
        self.assertEqual(len(actual), 120)
        self.assertEqual(set(actual), parser.CANONICAL_SET)
        self.assertEqual(actual, expected)
        self.assertTrue(parser.is_complete_snapshot(actual))

    def test_structural_table_missing_token_fails_closed(self):
        html, _ = structural_html()
        self.assertIn("129.0", html)
        damaged = html.replace("<td>129.0</td>", "", 1)
        self.assertEqual(parser.parse_official_odds3t(damaged), {})

    def test_legacy_contiguous_text_remains_supported(self):
        html = "<h2>3連単オッズ</h2><p>1-2-3 12.4 2－1－3 9.8</p>"
        self.assertEqual(
            parser.parse_official_odds3t(html),
            {"1-2-3": 12.4, "2-1-3": 9.8},
        )

    def test_complete_snapshot_requires_exact_120_input_items(self):
        values = complete_values()
        self.assertTrue(parser.is_complete_snapshot(values))

        missing = dict(values)
        missing.pop(next(iter(missing)))
        self.assertFalse(parser.is_complete_snapshot(missing))

        extra = dict(values)
        extra["bad-ticket"] = 99.9
        self.assertFalse(parser.is_complete_snapshot(extra))

    def test_complete_snapshot_rejects_nonfinite_zero_and_bad_value(self):
        for replacement in (math.nan, math.inf, 0.0, -1.0, "not-a-number"):
            with self.subTest(replacement=replacement):
                values = complete_values()
                values[parser.CANONICAL_TICKETS[0]] = replacement
                self.assertFalse(parser.is_complete_snapshot(values))

    def test_direct_complete_official_wins(self):
        official = complete_values(20.0)
        base = dict(list(complete_values(30.0).items())[:80])
        values, source = parser.choose_realtime_snapshot(official, base)
        self.assertEqual(source, "official_odds3t")
        self.assertEqual(values, official)

    def test_complete_base_is_only_allowed_fallback(self):
        official = dict(list(complete_values(20.0).items())[:80])
        base = complete_values(30.0)
        values, source = parser.choose_realtime_snapshot(official, base)
        self.assertEqual(source, "v2_odds_trifecta_fallback")
        self.assertEqual(values, base)

    def test_partial_or_extra_base_fails_closed(self):
        official = dict(list(complete_values(20.0).items())[:80])
        partial = dict(list(complete_values(30.0).items())[:119])
        values, source = parser.choose_realtime_snapshot(official, partial)
        self.assertEqual((values, source), ({}, "unavailable_incomplete"))

        extra = complete_values(30.0)
        extra["bad-ticket"] = 1.0
        values, source = parser.choose_realtime_snapshot({}, extra)
        self.assertEqual((values, source), ({}, "unavailable_incomplete"))


if __name__ == "__main__":
    unittest.main()
