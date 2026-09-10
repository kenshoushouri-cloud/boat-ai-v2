# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

import collect_racer_course_stats_pg as collector


def page(entry, top3, avg):
    def rows(values, suffix=""):
        return "".join(f"<tr><td>{i}</td><td>{v}{suffix if v != '-' else ''}</td></tr>" for i, v in enumerate(values, 1))

    return f"""
    <html><body>
      <h2>コース別進入率</h2><table>{rows(entry, '%')}</table>
      <h2>コース別3連対率</h2>
      <p>：1着率 ：2着率 ：3着率</p>
      <table>{rows(top3, '%')}</table>
      <h2>コース別平均スタートタイミング</h2><table>{rows(avg)}</table>
      <h2>コース別スタート順</h2>
    </body></html>
    """


class RacerCoursePartialParserTests(unittest.TestCase):
    def test_complete_six_course_page_is_unchanged(self):
        html = page(
            ["10.0", "20.0", "30.0", "40.0", "50.0", "60.0"],
            ["11.0", "22.0", "33.0", "44.0", "55.0", "66.0"],
            ["0.11", "0.12", "0.13", "0.14", "0.15", "0.16"],
        )
        rows, debug = collector.parse_course_stats(html, 4000)
        self.assertEqual(6, len(rows))
        self.assertEqual([11.0, 22.0, 33.0, 44.0, 55.0, 66.0], [r["top3_rate"] for r in rows])
        self.assertEqual(6, debug["top3_count"])
        self.assertEqual(6, debug["top3_slots"])

    def test_official_dash_is_none_and_course_position_is_preserved(self):
        html = page(
            ["32.6", "67.4", "-", "-", "-", "-"],
            ["78.6", "51.7", "-", "-", "-", "-"],
            ["0.16", "0.14", "-", "-", "-", "-"],
        )
        rows, debug = collector.parse_course_stats(html, 3265)
        self.assertEqual(6, len(rows))
        self.assertEqual([78.6, 51.7, None, None, None, None], [r.get("top3_rate") for r in rows])
        self.assertEqual([1, 2, 3, 4, 5, 6], [r["course"] for r in rows])
        self.assertEqual(2, debug["top3_count"])
        self.assertEqual(6, debug["top3_slots"])

    def test_middle_gaps_do_not_shift_later_courses_left(self):
        html = page(
            ["10.0", "-", "30.0", "-", "50.0", "60.0"],
            ["12.0", "-", "34.0", "-", "56.0", "67.0"],
            ["0.11", "-", "0.13", "-", "0.15", "0.16"],
        )
        rows, _ = collector.parse_course_stats(html, 4001)
        self.assertEqual([12.0, None, 34.0, None, 56.0, 67.0], [r.get("top3_rate") for r in rows])
        self.assertEqual(34.0, rows[2]["top3_rate"])
        self.assertEqual(56.0, rows[4]["top3_rate"])

    def test_all_dash_page_preserves_six_null_slots_not_zeroes(self):
        html = page(["-"] * 6, ["-"] * 6, ["-"] * 6)
        rows, debug = collector.parse_course_stats(html, 4999)
        self.assertEqual(6, len(rows))
        self.assertTrue(all("entry_rate" not in r for r in rows))
        self.assertTrue(all("top3_rate" not in r for r in rows))
        self.assertTrue(all("avg_st" not in r for r in rows))
        self.assertTrue(all(r["raw"]["top3_rate"] is None for r in rows))
        self.assertEqual(0, debug["top3_count"])

    def test_missing_values_are_omitted_from_upsert_columns(self):
        html = page(
            ["10.0", "-", "30.0", "40.0", "50.0", "60.0"],
            ["12.0", "-", "34.0", "44.0", "54.0", "64.0"],
            ["0.11", "-", "0.13", "0.14", "0.15", "0.16"],
        )
        rows, _ = collector.parse_course_stats(html, 4003)
        self.assertIn("top3_rate", rows[0])
        self.assertNotIn("top3_rate", rows[1])
        self.assertEqual(34.0, rows[2]["top3_rate"])
        self.assertIsNone(rows[1]["raw"]["top3_rate"])

    def test_missing_course_label_fails_closed_instead_of_realigning(self):
        html = """
        <html><body>
          <h2>コース別進入率</h2>1 10% 2 20% 3 30% 4 40% 5 50%
          <h2>コース別3連対率</h2>1 10% 2 20% 3 30% 4 40% 5 50%
          <h2>コース別平均スタートタイミング</h2>1 0.11 2 0.12 3 0.13 4 0.14 5 0.15
          <h2>コース別スタート順</h2>
        </body></html>
        """
        rows, debug = collector.parse_course_stats(html, 4002)
        self.assertEqual([], rows)
        self.assertLess(debug["top3_slots"], 6)

    def test_collect_one_accepts_partial_six_slot_page(self):
        html = page(
            ["32.6", "67.4", "-", "-", "-", "-"],
            ["78.6", "51.7", "-", "-", "-", "-"],
            ["0.16", "0.14", "-", "-", "-", "-"],
        )
        with patch.object(collector, "_fetch_html", return_value=html), patch.object(collector, "RACER_STATS_SLEEP_SEC", 0.0):
            racer, rows, debug, error = collector._collect_one(3265)
        self.assertEqual(3265, racer)
        self.assertIsNone(error)
        self.assertEqual(6, len(rows))
        self.assertEqual(2, debug["top3_count"])


if __name__ == "__main__":
    unittest.main()
