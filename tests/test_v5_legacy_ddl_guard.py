"""Offline V5 physical migration guard tests. No DB/HTTP/systemd access."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from v5_legacy_ddl_guard import (
    GUARD_FLAG,
    require_legacy_realtime_ddl_allowed,
)


class V5LegacyDdlGuardTests(unittest.TestCase):
    def environment(self, value=None):
        clean = {k: v for k, v in os.environ.items() if k != GUARD_FLAG}
        if value is not None:
            clean[GUARD_FLAG] = value
        return patch.dict(os.environ, clean, clear=True)

    def test_unchanged_default(self):
        with self.environment():
            self.assertIsNone(require_legacy_realtime_ddl_allowed())

    def test_explicit_zero_is_legacy(self):
        with self.environment("0"):
            self.assertIsNone(require_legacy_realtime_ddl_allowed())

    def test_cutover_guard_fails_closed(self):
        with self.environment("YES"):
            with self.assertRaisesRegex(RuntimeError, "STOP: legacy realtime"):
                require_legacy_realtime_ddl_allowed()

    def test_typo_fails_closed(self):
        with self.environment("yes"):
            with self.assertRaisesRegex(RuntimeError, "invalid"):
                require_legacy_realtime_ddl_allowed()

    def test_legacy_collector_calls_guard_before_any_ddl(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "v21_realtime_collector_pg.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        methods = [
            node for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_ensure_realtime_tables"
        ]
        self.assertEqual(len(methods), 1)
        statements = methods[0].body
        # Physical mode does a catalog check and returns without DDL.
        self.assertIsInstance(statements[0], ast.If)
        self.assertIsInstance(statements[0].test, ast.Call)
        self.assertEqual(statements[0].test.func.id, "physical_enabled")
        self.assertIsInstance(statements[0].body[0], ast.Expr)
        self.assertEqual(statements[0].body[0].value.func.id, "verify_physical_targets")
        self.assertIsInstance(statements[0].body[1], ast.Return)
        # Legacy path still checks the guard before the CREATE/ALTER loops.
        self.assertIsInstance(statements[1], ast.Expr)
        self.assertEqual(statements[1].value.func.id, "require_legacy_realtime_ddl_allowed")


if __name__ == "__main__":
    unittest.main()
