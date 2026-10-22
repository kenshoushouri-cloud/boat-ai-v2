"""Offline checks for V5 forward selector and strict capture gate. No HTTP/DB."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from v5.conoha_realtime_window_pg import collect_one, eligible, load_candidates
import v21_realtime_collector_pg_safe as safe

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 20, 15, 30, tzinfo=JST)
RID = "20261020_01_02"


class TestForwardSelector(unittest.TestCase):
    def test_pending_race_in_window(self):
        row = {"race_id": RID, "deadline_at": NOW + timedelta(minutes=15),
               "exh_lanes": 0, "odds_tickets": 0}
        self.assertTrue(eligible(row, NOW))

    def test_already_complete_is_skipped(self):
        row = {"race_id": RID, "deadline_at": NOW + timedelta(minutes=15),
               "exh_lanes": 6, "odds_tickets": 120}
        self.assertFalse(eligible(row, NOW))

    def test_predeadline_and_race_identity_gate(self):
        for minutes in (0, 8, 25, 180):
            row = {"race_id": RID, "deadline_at": NOW + timedelta(minutes=minutes),
                   "exh_lanes": 0, "odds_tickets": 0}
            with self.subTest(minutes=minutes):
                self.assertFalse(eligible(row, NOW))
        row = {"race_id": "20261019_01_02",
               "deadline_at": NOW + timedelta(minutes=15),
               "exh_lanes": 0, "odds_tickets": 0}
        self.assertFalse(eligible(row, NOW))
        row["race_id"] = "invalid"
        self.assertFalse(eligible(row, NOW))
        row["race_id"] = RID
        row["deadline_at"] = NOW.replace(tzinfo=None) + timedelta(minutes=15)
        self.assertFalse(eligible(row, NOW))

    def test_late_retry_is_opt_in_only_for_missing_snapshots(self):
        row = {"race_id": RID, "deadline_at": NOW + timedelta(minutes=8),
               "exh_lanes": 0, "odds_tickets": 120}
        # Existing production default unchanged.
        self.assertFalse(eligible(row, NOW))
        self.assertTrue(eligible(row, NOW, min_minutes=5))
        row["deadline_at"] = NOW + timedelta(minutes=5)
        self.assertTrue(eligible(row, NOW, min_minutes=5))
        row["deadline_at"] = NOW + timedelta(minutes=4, seconds=59)
        self.assertFalse(eligible(row, NOW, min_minutes=5))
        row["deadline_at"] = NOW + timedelta(minutes=7)
        row["exh_lanes"] = 6
        self.assertFalse(eligible(row, NOW, min_minutes=5))

    def test_opt_in_query_includes_5_minute_window(self):
        conn = MagicMock()
        cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = []
        with patch("db_pg.get_conn", return_value=conn), patch(
            "v5.conoha_realtime_window_pg.build_candidates_query",
            return_value="SELECT candidate"
        ):
            self.assertEqual(load_candidates(NOW, min_minutes=5), [])
        args = cur.execute.call_args.args[1]
        self.assertEqual(args[0], NOW.date())
        self.assertEqual(args[1], NOW + timedelta(minutes=5))
        self.assertEqual(args[2], NOW + timedelta(minutes=24))

    def test_live_subprocess_env_is_strict_and_isolated(self):
        with patch("v5.conoha_realtime_window_pg.subprocess.run") as runner:
            runner.return_value.returncode = 0
            code = collect_one(RID, at=NOW)
            self.assertEqual(code, 0)
            kwargs = runner.call_args.kwargs
            env = kwargs["env"]
            self.assertEqual(env["V5_STRICT_PREDEADLINE"], "1")
            self.assertEqual(env["V5_DEADLINE_GUARD_SEC"], "180")
            self.assertEqual(env["TARGET_ID_SCOPE"], "none")
            self.assertEqual(env["TARGET_RACE_ID"], RID)
            self.assertIn(RID, env["TARGET_RACE_IDS_FILE"])
            self.assertEqual(kwargs["timeout"], 75)

    def test_strict_capture_guard(self):
        row = {"deadline_at": NOW + timedelta(minutes=4)}
        with patch.object(safe.legacy, "_now", return_value=NOW):
            self.assertTrue(safe._may_save_before_cutoff(row))
            row["deadline_at"] = NOW + timedelta(minutes=3)
            self.assertFalse(safe._may_save_before_cutoff(row))
            row["deadline_at"] = NOW - timedelta(minutes=1)
            self.assertFalse(safe._may_save_before_cutoff(row))
            self.assertFalse(safe._may_save_before_cutoff({}))


if __name__ == "__main__":
    unittest.main()
