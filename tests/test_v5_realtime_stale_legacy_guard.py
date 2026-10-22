"""Offline tests: old realtime DDL is refused after physical staging."""
import ast
import unittest
from pathlib import Path

from v5_legacy_ddl_guard import forbid_legacy_realtime_if_physical_exists


class StaleRealtimeLegacyTests(unittest.TestCase):
    def test_no_physical_target_keeps_legacy_behavior(self):
        calls = []

        def query(sql, args):
            calls.append((sql, args))
            return [{f"target_{i}": None for i in range(len(args))}]

        self.assertIsNone(forbid_legacy_realtime_if_physical_exists(query))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][1]), 6)
        self.assertEqual(calls[0][0].count("to_regclass("), 6)

    def test_any_one_physical_target_prevents_old_ddl(self):
        for index in range(6):
            with self.subTest(index=index):
                def query(sql, args):
                    row = {f"target_{i}": None for i in range(len(args))}
                    row[f"target_{index}"] = "v5_data.raw_example"
                    return [row]
                with self.assertRaisesRegex(RuntimeError, "refusing legacy"):
                    forbid_legacy_realtime_if_physical_exists(query)

    def test_incomplete_catalog_answer_fails_closed(self):
        for answer in (None, [], [{}], {"target_0": None}):
            with self.subTest(answer=answer):
                with self.assertRaisesRegex(RuntimeError, "catalog gate"):
                    forbid_legacy_realtime_if_physical_exists(
                        lambda sql, args: answer
                    )

    def test_guard_runs_before_first_legacy_create(self):
        source = (Path(__file__).resolve().parents[1] /
                  "v21_realtime_collector_pg.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        method = next(n for n in module.body
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "_ensure_realtime_tables")
        statements = method.body
        self.assertEqual(statements[2].value.func.id,
                         "require_legacy_realtime_ddl_allowed")
        self.assertEqual(statements[3].value.func.id,
                         "forbid_legacy_realtime_if_physical_exists")
        self.assertEqual(statements[3].value.args[0].id, "fetch_all")
        self.assertLess(source.index("forbid_legacy_realtime_if_physical_exists(fetch_all)"),
                        source.index("    tables=[\"v2_realtime_weather_snapshots\""))


if __name__ == "__main__":
    unittest.main()
