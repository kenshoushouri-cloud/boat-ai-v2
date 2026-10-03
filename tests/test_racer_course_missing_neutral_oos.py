from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
import importlib.util
from pathlib import Path
import unittest

JST = ZoneInfo("Asia/Tokyo")
SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "racer_course_missing_neutral_oos_20260911.py"
spec = importlib.util.spec_from_file_location("racer_course_missing_neutral_oos", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class CourseNeutralFallbackTests(unittest.TestCase):
    def row(self, lane: int, value: float | None, created_hour: int = 7, created_minute: int = 30) -> dict:
        d = date(2026, 9, 10)
        return {
            "lane": lane,
            "race_date": d,
            "deadline_at": datetime(2026, 9, 10, 10, 0, tzinfo=JST),
            "snapshot_racer_number": 1000 + lane if value is not None else None,
            "course_top3_rate": value,
            "snapshot_created_at": datetime(2026, 9, 10, created_hour, created_minute, tzinfo=JST) if value is not None else None,
        }

    def test_missing_lane_gets_zero_adjustment(self) -> None:
        rows = [self.row(i, 40.0 + i) for i in range(1, 7)]
        rows[2] = self.row(3, None)
        zs, n = module.observed_z_by_lane(rows)
        self.assertEqual(n, 5)
        self.assertEqual(zs[3], 0.0)
        self.assertAlmostEqual(sum(zs.values()), 0.0, places=12)

    def test_one_observed_lane_falls_back_to_base(self) -> None:
        rows = [self.row(i, None) for i in range(1, 7)]
        rows[0] = self.row(1, 55.0)
        zs, n = module.observed_z_by_lane(rows)
        self.assertEqual(n, 1)
        self.assertTrue(all(v == 0.0 for v in zs.values()))

    def test_equal_observed_values_fall_back_to_base(self) -> None:
        rows = [self.row(i, 50.0 if i <= 4 else None) for i in range(1, 7)]
        zs, n = module.observed_z_by_lane(rows)
        self.assertEqual(n, 4)
        self.assertTrue(all(v == 0.0 for v in zs.values()))

    def test_exact_0815_is_usable(self) -> None:
        row = self.row(1, 50.0, 8, 15)
        self.assertEqual(module.safe_course_value(row), 50.0)

    def test_after_0815_is_unusable(self) -> None:
        row = self.row(1, 50.0, 8, 16)
        self.assertIsNone(module.safe_course_value(row))

    def test_naive_timestamp_is_unusable(self) -> None:
        row = self.row(1, 50.0)
        row["snapshot_created_at"] = datetime(2026, 9, 10, 7, 30)
        self.assertIsNone(module.safe_course_value(row))


if __name__ == "__main__":
    unittest.main()
