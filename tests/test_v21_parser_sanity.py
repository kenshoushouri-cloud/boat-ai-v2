# -*- coding: utf-8 -*-
import unittest

import v21_realtime_collector_pg as v21
import backfill_historical_beforeinfo_pg as historical_beforeinfo


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

    def test_parse_weather_normalized_degree_c(self):
        html = "<html><body>晴 気温 26.0°C 水温 22.0°C 風速 1m 波高 1cm</body></html>"
        row = v21.parse_weather(html)
        self.assertEqual(row["temperature_c"], 26.0)
        self.assertEqual(row["water_temperature_c"], 22.0)

    def test_historical_parse_weather_celsius_after_nfkc(self):
        html = "<html><body>晴 気温 26.0℃ 水温 22.0℃ 風速 1m 波高 1cm</body></html>"
        row = historical_beforeinfo.parse_weather_v2(html)
        self.assertEqual(row["temperature_c"], 26.0)
        self.assertEqual(row["water_temperature_c"], 22.0)

    def test_beforeinfo_quality_detects_weather_missing(self):
        weather = {
            "temperature_c": None,
            "water_temperature_c": 22.0,
            "wind_speed_m": 1.0,
            "wave_height_cm": 1.0,
        }
        q = v21.inspect_beforeinfo_quality("<html></html>", weather, [])
        self.assertIn("temperature_c", q["weather_missing"])

    def test_beforeinfo_quality_classifies_official_partial(self):
        rows = []
        for lane, value in ((1, "6.78"), (2, "6.75"), (3, "6.86"), (4, "6.77"), (5, ""), (6, "6.85")):
            rows.append(
                f'<tbody class="is-fs12"><tr><td>{lane}</td><td></td><td>r</td>'
                f'<td>52.0kg</td><td>{value}</td><td>0.0</td></tr></tbody>'
            )
        html = "<html><body>" + "".join(rows) + "</body></html>"
        weather = {
            "temperature_c": 26.0,
            "water_temperature_c": 22.0,
            "wind_speed_m": 1.0,
            "wave_height_cm": 1.0,
        }
        q = v21.inspect_beforeinfo_quality(html, weather, [])
        self.assertEqual(q["exhibition_status"], "official_partial")
        self.assertEqual(q["exhibition_valid_time_count"], 5)

    def test_parse_odds3t_ascii_and_fullwidth_hyphen(self):
        html = "<html><body>1-2-3 12.4 2－1－3 9.8</body></html>"
        odds = v21.parse_odds3t(html)
        self.assertEqual(odds.get("1-2-3"), 12.4)
        self.assertEqual(odds.get("2-1-3"), 9.8)


if __name__ == "__main__":
    unittest.main()
