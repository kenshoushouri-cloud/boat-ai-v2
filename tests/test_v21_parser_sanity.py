# -*- coding: utf-8 -*-
import unittest

import v21_realtime_collector_pg as v21


class V21ParserSanityTests(unittest.TestCase):
    def test_norm_ticket_ascii_and_fullwidth_hyphen(self):
        self.assertEqual(v21._norm_ticket("1-2-3"), "1-2-3")
        self.assertEqual(v21._norm_ticket("1－2－3"), "1-2-3")
        self.assertEqual(v21._norm_ticket("1-1-2"), "")

    def test_no_data_japanese_phrase(self):
        self.assertTrue(v21._looks_no_data("<html><body>データがありません</body></html>"))
        self.assertFalse(v21._looks_no_data("<html><body>1-2-3 12.4</body></html>"))

    def test_parse_weather_japanese_labels(self):
        html = "<html><body>晴 気温 30.5℃ 水温 28.0℃ 風速 4m 北東 波高 3cm</body></html>"
        row = v21.parse_weather(html)
        self.assertEqual(row["weather"], "晴")
        self.assertEqual(row["temperature_c"], 30.5)
        self.assertEqual(row["water_temperature_c"], 28.0)
        self.assertEqual(row["wind_speed_m"], 4.0)
        self.assertEqual(row["wind_direction"], "北東")
        self.assertEqual(row["wave_height_cm"], 3.0)

    def test_parse_odds3t_ascii_and_fullwidth_hyphen(self):
        html = "<html><body>1-2-3 12.4 2－1－3 9.8</body></html>"
        odds = v21.parse_odds3t(html)
        self.assertEqual(odds.get("1-2-3"), 12.4)
        self.assertEqual(odds.get("2-1-3"), 9.8)


if __name__ == "__main__":
    unittest.main()
