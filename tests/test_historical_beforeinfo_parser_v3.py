# -*- coding: utf-8 -*-
import unittest

import historical_beforeinfo_parser_v3 as parser


def make_html(order=(1, 2, 3, 4, 5, 6)):
    boat_rows = []
    for lane in range(1, 7):
        exhibition_time = 6.70 + lane / 100
        tilt = -0.5 if lane % 2 == 0 else 0.0
        boat_rows.append(
            f"""
            <tbody class="is-fs12">
              <tr>
                <td>{lane}</td><td></td><td>選手{lane}</td>
                <td>52.0kg</td><td>{exhibition_time:.2f}</td><td>{tilt:.1f}</td>
                <td></td><td></td><td></td>
              </tr>
            </tbody>
            """
        )

    start_rows = []
    st_by_lane = {1: ".03", 2: ".01", 3: ".07", 4: ".04", 5: "F.11", 6: ".08"}
    for lane in order:
        start_rows.append(
            f"<tr><td>{lane}</td><td><img alt='Image'></td><td>{st_by_lane[lane]}</td></tr>"
        )

    return f"""
    <html><body>
      <table>{''.join(boat_rows)}</table>
      <h3>スタート展示</h3>
      <table><tr><th>コース</th><th>並び</th><th>ST</th></tr>{''.join(start_rows)}</table>
      <h3>水面気象情報</h3>
      <div>気温 20.0℃ 晴 風速 3m 水温 14.0℃ 波高 3cm</div>
    </body></html>
    """


class HistoricalBeforeinfoParserV3Tests(unittest.TestCase):
    def test_parses_exhibition_time_and_tilt(self):
        rows = parser.parse_exhibition(make_html())
        self.assertEqual(len(rows), 6)
        by_lane = {row["lane"]: row for row in rows}
        self.assertAlmostEqual(by_lane[1]["exhibition_time"], 6.71)
        self.assertAlmostEqual(by_lane[2]["exhibition_time"], 6.72)
        self.assertEqual(by_lane[1]["tilt"], 0.0)
        self.assertEqual(by_lane[2]["tilt"], -0.5)

    def test_parses_reordered_start_exhibition_as_course_order(self):
        rows = parser.parse_exhibition(make_html(order=(2, 1, 3, 4, 5, 6)))
        by_lane = {row["lane"]: row for row in rows}
        self.assertEqual(by_lane[2]["exhibition_course"], 1)
        self.assertEqual(by_lane[1]["exhibition_course"], 2)
        self.assertEqual(by_lane[3]["exhibition_course"], 3)
        self.assertAlmostEqual(by_lane[2]["start_timing"], 0.01)
        self.assertAlmostEqual(by_lane[1]["start_timing"], 0.03)

    def test_normal_order_is_not_marked_as_course_change(self):
        rows = parser.parse_exhibition(make_html())
        for row in rows:
            self.assertEqual(row["lane"], row["exhibition_course"])

    def test_ranks_and_diffs_are_populated(self):
        rows = parser.parse_exhibition(make_html())
        by_lane = {row["lane"]: row for row in rows}
        self.assertEqual(by_lane[1]["exhibition_time_rank"], 1)
        self.assertAlmostEqual(by_lane[2]["exhibition_time_diff"], 0.01)
        self.assertEqual(by_lane[2]["start_timing_rank"], 1)


if __name__ == "__main__":
    unittest.main()
