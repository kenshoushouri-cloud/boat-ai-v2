import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v5.forward_shadow_freeze import prepare_candidate, append_once


class FreezeTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, 9, 0, tzinfo=timezone(timedelta(hours=9)))
        self.row = {
            "race_id": "20261021_01_01",
            "deadline_at": (self.now + timedelta(minutes=12)).isoformat(),
            "model_family": "V5", "model_version": "frozen-test",
            "exhibition": {"complete_items": 6, "sha256": "a"*64,
                           "captured_at": (self.now - timedelta(minutes=1)).isoformat()},
            "odds": {"complete_items": 120, "sha256": "b"*64,
                     "captured_at": (self.now - timedelta(seconds=30)).isoformat()},
            "selected_tickets": ["1-2-3", "1-3-2"],
            "stake_per_ticket_yen": 100,
        }

    def test_preview_never_verifies_roi_or_buy(self):
        record = prepare_candidate(self.row, now=self.now)
        self.assertFalse(record["forward_eligible"])
        self.assertFalse(record["buy_eligible"])
        self.assertEqual(record["settlement_status"], "PENDING_NO_REAL_ROI")
        self.assertEqual(record["hypothetical_stake_yen"], 200)
        self.assertEqual(len(record["manifest_sha256"]), 64)

    def test_no_late_backfill(self):
        with self.assertRaises(ValueError):
            prepare_candidate(self.row, now=self.now + timedelta(minutes=10))

    def test_no_incomplete_odds(self):
        self.row["odds"]["complete_items"] = 119
        with self.assertRaises(ValueError):
            prepare_candidate(self.row, now=self.now)

    def test_no_future_snapshot(self):
        self.row["exhibition"]["captured_at"] = (self.now + timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):
            prepare_candidate(self.row, now=self.now)

    def test_no_duplicate_tickets(self):
        self.row["selected_tickets"] = ["1-2-3", "1-2-3"]
        with self.assertRaises(ValueError):
            prepare_candidate(self.row, now=self.now)

    def test_append_once_and_reject_duplicate(self):
        record = prepare_candidate(self.row, now=self.now)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pending.jsonl"
            append_once(path, record)
            data = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(len(data), 1)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                append_once(path, record)
            self.assertEqual(len(path.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
