"""Offline migration routing tests; no DB, HTTP, systemd or file writes."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from v5_realtime_table_routes import (
    PROFILE_KEY, CONFIRM_KEY, TARGETS, physical_enabled,
    resolve_realtime_table, verify_physical_targets,
)


class RealtimeRoutesTest(unittest.TestCase):
    def config(self, profile=None, confirm=None):
        env = {k: v for k, v in os.environ.items()
               if k not in (PROFILE_KEY, CONFIRM_KEY)}
        if profile is not None:
            env[PROFILE_KEY] = profile
        if confirm is not None:
            env[CONFIRM_KEY] = confirm
        return patch.dict(os.environ, env, clear=True)

    def test_default_keeps_all_six_legacy_tables(self):
        with self.config():
            self.assertFalse(physical_enabled())
            for old in TARGETS:
                self.assertEqual(resolve_realtime_table(old), old)

    def test_explicit_legacy_ignores_confirmation(self):
        with self.config("legacy", "YES"):
            self.assertFalse(physical_enabled())

    def test_physical_requires_second_gate(self):
        with self.config("physical"):
            with self.assertRaisesRegex(RuntimeError, "not confirmed"):
                physical_enabled()

    def test_typo_fails_closed(self):
        with self.config("phyiscal", "YES"):
            with self.assertRaisesRegex(RuntimeError, "invalid"):
                physical_enabled()

    def test_physical_has_six_unique_fixed_table_routes(self):
        with self.config("physical", "YES"):
            self.assertTrue(physical_enabled())
            self.assertEqual(len(TARGETS), 6)
            self.assertEqual(len(set(TARGETS.values())), 6)
            for old, target in TARGETS.items():
                self.assertEqual(resolve_realtime_table(old), target)
                self.assertTrue(target.startswith("v5_data.raw_"))

    def test_unknown_table_fails_closed(self):
        with self.config():
            with self.assertRaises(ValueError):
                resolve_realtime_table("v2_results")

    def test_physical_target_catalog_check(self):
        seen = []
        def fake_fetch(sql, params):
            self.assertIn("to_regclass", sql)
            seen.append(params[0])
            return [{"relkind": "r"}]
        with self.config("physical", "YES"):
            verify_physical_targets(fake_fetch)
        self.assertEqual(seen, list(TARGETS.values()))

    def test_missing_physical_target_stops(self):
        with self.config("physical", "YES"):
            with self.assertRaisesRegex(RuntimeError, "missing"):
                verify_physical_targets(lambda *_: [])

    def test_view_is_not_a_physical_target(self):
        with self.config("physical", "YES"):
            with self.assertRaisesRegex(RuntimeError, "non-table"):
                verify_physical_targets(lambda *_: [{"relkind": "v"}])

    def test_default_does_not_touch_db(self):
        with self.config():
            def forbidden_fetch(*_):
                self.fail("default mode must not access DB")
            verify_physical_targets(forbidden_fetch)

    def test_collector_links_read_and_write_with_route(self):
        src = (Path(__file__).resolve().parents[1] / "v21_realtime_collector_pg.py").read_text(encoding="utf-8")
        ast.parse(src)
        self.assertIn("upsert_rows(resolve_realtime_table(t),", src)
        self.assertIn('resolve_realtime_table("v2_realtime_odds_snapshots")', src)
        self.assertIn("verify_physical_targets(fetch_all)", src)


if __name__ == "__main__":
    unittest.main()
