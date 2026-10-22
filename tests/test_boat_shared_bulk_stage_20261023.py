"""Offline sanity tests: staging cannot silently become live V5/V6."""
import datetime as dt
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from deploy.conoha import boat_shared_bulk_stage_20261023 as m

class CopyGuardTests(unittest.TestCase):
    def test_source_count_unique(self):
        self.assertEqual(len(m.SOURCES), 12)
        self.assertEqual(len({x for x, _ in m.SOURCES}), 12)
        self.assertEqual(len({x for _, x in m.SOURCES}), 12)

    def test_no_results_in_mixed_database(self):
        self.assertTrue(all(not name.startswith("v5_") for _, name in m.SOURCES))
        self.assertNotIn("v2_venues", {old for old, _ in m.SOURCES})

    def test_outside_overnight_hours_blocked(self):
        for hour in (0, 1, 7, 12, 19, 23):
            when = dt.datetime(2026, 10, 23, hour, 5, tzinfo=ZoneInfo("Asia/Tokyo"))
            with patch.object(m, "now", return_value=when):
                self.assertEqual(m.remaining_seconds(), 0)

    def test_protect_0700(self):
        for hour, minute in ((2, 0), (5, 59), (6, 14)):
            when = dt.datetime(2026, 10, 23, hour, minute, tzinfo=ZoneInfo("Asia/Tokyo"))
            with patch.object(m, "now", return_value=when):
                self.assertGreater(m.remaining_seconds(), 0)

    def test_abort_before_0620(self):
        when = dt.datetime(2026, 10, 23, 6, 15, tzinfo=ZoneInfo("Asia/Tokyo"))
        with patch.object(m, "now", return_value=when):
            self.assertEqual(m.remaining_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
