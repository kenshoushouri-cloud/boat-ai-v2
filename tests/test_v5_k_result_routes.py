"""No-I/O unit tests for six-lane K result source migration guard."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from v5_k_result_routes import (
    k_targets, result_columns_location, validate_physical_targets,
    forbid_legacy_after_physical_exists,
)

MODE = "V5_DAILY_WRITE_ROUTE_PROFILE"
CONFIRM = "CONFIRM_V5_PHYSICAL_WRITER_ROUTE"


class KResultRouteTests(unittest.TestCase):
    def env(self, mode=None, confirmed=None):
        environ = {
            k: v for k, v in os.environ.items() if k not in (MODE, CONFIRM)
        }
        if mode is not None:
            environ[MODE] = mode
        if confirmed is not None:
            environ[CONFIRM] = confirmed
        return patch.dict(os.environ, environ, clear=True)

    def test_default_k_results_both_legacy(self):
        with self.env():
            r, e, physical = k_targets()
            self.assertFalse(physical)
            self.assertEqual(r.as_string(), '"public"."v2_results"')
            self.assertEqual(e.as_string(), '"public"."v2_result_entries"')
            self.assertEqual(result_columns_location(), ("public", "v2_results"))

    def test_core_mode_routes_both_k_results(self):
        with self.env("core", "YES"):
            r, e, physical = k_targets()
            self.assertTrue(physical)
            self.assertEqual(r.as_string(), '"v5_data"."raw_results"')
            self.assertEqual(e.as_string(), '"v5_data"."raw_racer_results"')
            self.assertEqual(result_columns_location(), ("v5_data", "raw_results"))

    def test_other_profile_does_not_split_results(self):
        for profile in ("venues", "odds", "venues_odds"):
            with self.subTest(profile=profile), self.env(profile, "YES"):
                r, e, physical = k_targets()
                self.assertFalse(physical)
                self.assertEqual(r.as_string(), '"public"."v2_results"')
                self.assertEqual(e.as_string(), '"public"."v2_result_entries"')

    def test_missing_second_gate_blocks_core(self):
        with self.env("core"):
            with self.assertRaises(RuntimeError):
                k_targets()

    def test_invalid_profile_blocks_core(self):
        with self.env("invalid", "YES"):
            with self.assertRaises(RuntimeError):
                k_targets()

    def test_physical_catalog_check_accepts_real_tables(self):
        class Cursor:
            def __init__(self):
                self.parameters = []
            def execute(self, statement, parameters):
                self.assert_sql = statement
                self.parameters.append(parameters[0])
            def fetchone(self):
                return ("r",)
        cursor = Cursor()
        validate_physical_targets(cursor)
        self.assertEqual(cursor.parameters,
                         ["v5_data.raw_results", "v5_data.raw_racer_results"])

    def test_missing_or_view_physical_targets_stop(self):
        class Cursor:
            def execute(self, *args):
                pass
            def fetchone(self):
                return ("v",)
        with self.assertRaisesRegex(RuntimeError, "missing/non-table"):
            validate_physical_targets(Cursor())

    def test_offline_k_writer_requires_coupled_route_and_no_physical_ddl(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "save_k_day_results_pg.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("result_ident, entry_ident, physical = k_targets()", source)
        self.assertIn("if physical:", source)
        self.assertIn("validate_physical_targets(cur)", source)
        self.assertIn("forbid_legacy_after_physical_exists(cur)", source)
        self.assertLess(source.index("forbid_legacy_after_physical_exists(cur)"),
                        source.index("cur.execute(DDL)"))
        self.assertIn("format(entry_ident)", source)
        self.assertIn("format(result_ident)", source)
        self.assertIn("result_columns_location()", source)

    def test_no_legacy_direct_result_dml_in_k_writer(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "save_k_day_results_pg.py").read_text(encoding="utf-8")
        self.assertNotIn("insert into v2_result_entries(", source.lower())
        self.assertNotIn('cur.execute("update v2_results set "', source)
        self.assertNotIn("from v2_result_entries\n", source.lower())

    def test_legacy_allowed_only_when_both_physical_targets_absent(self):
        class Cursor:
            def __init__(self):
                self.names = []
            def execute(self, q, args):
                self.names.append(args[0])
            def fetchone(self):
                return (None,)
        cur = Cursor()
        forbid_legacy_after_physical_exists(cur)
        self.assertEqual(cur.names,
                         ["v5_data.raw_results", "v5_data.raw_racer_results"])

    def test_legacy_stops_if_first_physical_target_exists(self):
        class Cursor:
            def execute(self, q, args):
                pass
            def fetchone(self):
                return ("v5_data.raw_results",)
        with self.assertRaisesRegex(RuntimeError, "refusing legacy"):
            forbid_legacy_after_physical_exists(Cursor())

    def test_legacy_stops_if_second_physical_target_exists(self):
        class Cursor:
            def __init__(self):
                self.pos = 0
            def execute(self, q, args):
                self.pos += 1
            def fetchone(self):
                return (None,) if self.pos == 1 else ("v5_data.raw_racer_results",)
        cur = Cursor()
        with self.assertRaisesRegex(RuntimeError, "refusing legacy"):
            forbid_legacy_after_physical_exists(cur)
        self.assertEqual(cur.pos, 2)

    def test_legacy_stops_on_incomplete_catalog_answer(self):
        class Cursor:
            def execute(self, q, args):
                pass
            def fetchone(self):
                return None
        with self.assertRaisesRegex(RuntimeError, "cannot establish"):
            forbid_legacy_after_physical_exists(Cursor())



if __name__ == "__main__":
    unittest.main()
