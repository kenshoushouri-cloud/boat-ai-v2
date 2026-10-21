"""Offline proof that realtime scheduler reads match staged writer table routes.

No HTTP, database connection, cron, systemd or file writes.
"""
import os
import unittest
from unittest.mock import patch

from v5.conoha_realtime_window_pg import build_candidates_query
from v5_realtime_table_routes import PROFILE_KEY, CONFIRM_KEY


class ForwardSnapshotReaderRoutesTest(unittest.TestCase):
    def configured(self, profile=None, confirm=None):
        env = {k: v for k, v in os.environ.items()
               if k not in (PROFILE_KEY, CONFIRM_KEY)}
        if profile is not None:
            env[PROFILE_KEY] = profile
        if confirm is not None:
            env[CONFIRM_KEY] = confirm
        return patch.dict(os.environ, env, clear=True)

    def test_legacy_default_uses_old_read_tables(self):
        with self.configured():
            statement = build_candidates_query().as_string()
        self.assertIn('"public"."v2_realtime_exhibition_snapshots"', statement)
        self.assertIn('"public"."v2_realtime_odds_snapshots"', statement)
        self.assertNotIn('"v5_data"."raw_', statement)

    def test_physical_opt_in_uses_same_read_sources_as_writer(self):
        with self.configured("physical", "YES"):
            statement = build_candidates_query().as_string()
        self.assertIn('"v5_data"."raw_exhibition_snapshots"', statement)
        self.assertIn('"v5_data"."raw_odds_snapshots"', statement)
        self.assertNotIn('"public"."v2_realtime_exhibition_snapshots"', statement)

    def test_unconfirmed_physical_fails_before_database(self):
        with self.configured("physical"):
            with self.assertRaisesRegex(RuntimeError, "not confirmed"):
                build_candidates_query()

    def test_invalid_mode_fails_before_database(self):
        with self.configured("physical;DROP TABLE", "YES"):
            with self.assertRaisesRegex(RuntimeError, "invalid"):
                build_candidates_query()

    def test_core_race_reader_still_requires_separate_cutover(self):
        with self.configured("physical", "YES"):
            statement = build_candidates_query().as_string()
        self.assertIn('FROM "public"."v2_races" r', statement)
        self.assertIn("LIMIT 100", statement)
        self.assertEqual(statement.count("%s"), 3)


if __name__ == "__main__":
    unittest.main()
