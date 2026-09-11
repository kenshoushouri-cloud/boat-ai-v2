from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import importlib.util
from pathlib import Path
import unittest

JST = ZoneInfo("Asia/Tokyo")
SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "racer_course_required_coverage_audit.py"
spec = importlib.util.spec_from_file_location("racer_course_required_coverage_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
classify_required_coverage = module.classify_required_coverage


class RequiredCourseCoverageAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.race_date = date(2026, 9, 11)
        self.deadline = datetime(2026, 9, 11, 10, 0, tzinfo=JST)
        self.created = datetime(2026, 9, 11, 7, 30, tzinfo=JST)

    def race(self, race_id: str = "r1") -> list[dict]:
        return [
            {
                "race_id": race_id,
                "deadline_at": self.deadline,
                "lane": lane,
                "racer_number": 1000 + lane,
                "snapshot_racer_number": 1000 + lane,
                "course": lane,
                "course_top3_rate": 40.0 + lane,
                "snapshot_created_at": self.created,
            }
            for lane in range(1, 7)
        ]

    def test_exact_six_required_rows_pass(self) -> None:
        result = classify_required_coverage(self.race(), self.race_date)
        self.assertEqual(result["ready_races"], 1)
        self.assertEqual(result["blocked_races"], 0)
        self.assertEqual(result["ready_lanes"], 6)

    def test_missing_exact_racer_course_row_blocks_race(self) -> None:
        rows = self.race()
        rows[2]["snapshot_racer_number"] = None
        result = classify_required_coverage(rows, self.race_date)
        self.assertEqual(result["ready_races"], 0)
        self.assertEqual(result["reasons"]["missing_required_row"], 1)

    def test_missing_top3_blocks_even_when_row_exists(self) -> None:
        rows = self.race()
        rows[4]["course_top3_rate"] = None
        result = classify_required_coverage(rows, self.race_date)
        self.assertEqual(result["reasons"]["missing_or_invalid_top3"], 1)

    def test_exact_0815_snapshot_is_allowed(self) -> None:
        rows = self.race()
        rows[0]["snapshot_created_at"] = datetime(2026, 9, 11, 8, 15, tzinfo=JST)
        result = classify_required_coverage(rows, self.race_date)
        self.assertEqual(result["ready_races"], 1)

    def test_after_0815_snapshot_blocks(self) -> None:
        rows = self.race()
        rows[0]["snapshot_created_at"] = datetime(2026, 9, 11, 8, 15, 0, 1, tzinfo=JST)
        result = classify_required_coverage(rows, self.race_date)
        self.assertEqual(result["reasons"]["created_after_0815"], 1)

    def test_post_deadline_snapshot_blocks(self) -> None:
        rows = self.race()
        # deadline reason is checked after fixed-cutoff reason; use an earlier race deadline.
        rows[0]["deadline_at"] = datetime(2026, 9, 11, 7, 20, tzinfo=JST)
        rows[0]["snapshot_created_at"] = datetime(2026, 9, 11, 7, 30, tzinfo=JST)
        result = classify_required_coverage(rows, self.race_date)
        self.assertEqual(result["reasons"]["created_at_or_after_deadline"], 1)

    def test_not_exactly_six_entries_blocks(self) -> None:
        result = classify_required_coverage(self.race()[:-1], self.race_date)
        self.assertEqual(result["reasons"]["entries_not_exactly_6"], 1)


if __name__ == "__main__":
    unittest.main()
