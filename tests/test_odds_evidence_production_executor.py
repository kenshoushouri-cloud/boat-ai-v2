"""Offline contract tests for the one-shot production audit executor."""
import contextlib
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import odds_evidence_privilege_guard as guard
import odds_evidence_production_executor as executor


class ProductionExecutorTests(unittest.TestCase):
    URL = "postgresql://postgres:p%40ss@x.proxy.rlwy.net:1234/railway"

    def env(self):
        return {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REPOSITORY": executor.REPO,
            "GITHUB_REF": "refs/heads/" + executor.BRANCH,
            "GITHUB_ACTOR": executor.OWNER,
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "a" * 40,
            "PRODUCTION_EXECUTION_CONFIRMATION": executor.CONFIRMATION,
            "PRODUCTION_EXECUTION_COMMIT_MESSAGE": executor.COMMIT_MESSAGE,
            "ADMIN_DATABASE_URL": self.URL,
        }

    def test_authorization_is_single_attempt_and_exact(self):
        executor.authorize(self.env())
        for key in self.env():
            with self.subTest(key=key):
                bad = self.env()
                bad.pop(key)
                with self.assertRaises(executor.ProductionExecutionError):
                    executor.authorize(bad)
        bad = self.env()
        bad["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(executor.ProductionExecutionError):
            executor.authorize(bad)

    def test_admin_url_is_rebuilt_with_pinned_tls_and_no_url_options(self):
        seen = {}
        fake_psycopg = types.ModuleType("psycopg")
        conninfo = types.ModuleType("psycopg.conninfo")

        def make_conninfo(*args, **kwargs):
            seen.update(kwargs)
            return "safe-admin"

        conninfo.make_conninfo = make_conninfo
        with patch.dict(sys.modules, {
            "psycopg": fake_psycopg,
            "psycopg.conninfo": conninfo,
        }):
            value, host, port, database = executor.admin_connection(
                self.URL + "?sslmode=disable&options=unsafe"
            )
        self.assertEqual(value, "safe-admin")
        self.assertEqual((host, port, database),
                         ("x.proxy.rlwy.net", 1234, "railway"))
        self.assertEqual(seen["sslmode"], "verify-full")
        self.assertEqual(seen["gssencmode"], "disable")
        self.assertNotIn("unsafe", str(seen))
        self.assertEqual(seen["user"], "postgres")
        self.assertEqual(seen["password"], "p@ss")

    def test_admin_url_rejects_dedicated_role_and_nonrailway_hosts_before_driver_import(self):
        bad = [
            self.URL.replace("postgres:", guard.ROLE_NAME + ":"),
            self.URL.replace("x.proxy.rlwy.net", "localhost"),
            self.URL.replace(":1234", ""),
            self.URL.replace("/railway", "/bad/name"),
            self.URL + "#fragment",
            "mysql://postgres:p@x.proxy.rlwy.net:1234/railway",
        ]
        with patch.dict(sys.modules, {
            "psycopg": None,
            "psycopg.conninfo": None,
        }):
            for url in bad:
                with self.subTest(url=url):
                    with self.assertRaises(executor.ProductionExecutionError):
                        executor.admin_connection(url)

    def test_audit_connection_pins_role_and_readonly_defaults(self):
        seen = {}
        fake_psycopg = types.ModuleType("psycopg")
        conninfo = types.ModuleType("psycopg.conninfo")

        def make_conninfo(*args, **kwargs):
            seen.update(kwargs)
            return "safe-audit"

        conninfo.make_conninfo = make_conninfo
        with patch.dict(sys.modules, {
            "psycopg": fake_psycopg,
            "psycopg.conninfo": conninfo,
        }):
            value = executor.audit_connection(
                host="x.proxy.rlwy.net", port=1234,
                database="railway", password="x" * 32
            )
        self.assertEqual(value, "safe-audit")
        self.assertEqual(seen["user"], guard.ROLE_NAME)
        self.assertEqual(seen["sslmode"], "verify-full")
        self.assertIn("default_transaction_read_only=on", seen["options"])

    def test_failure_output_is_sanitized(self):
        with patch.object(executor, "admin_connection",
                          side_effect=RuntimeError("private-secret")), \
             patch.object(executor, "_write_execution"), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(executor.main(self.env()), 1)
        self.assertNotIn("private-secret", err.getvalue())
        self.assertIn("PRODUCTION_AUDIT_FAILED=admin_connection_validation",
                      err.getvalue())


if __name__ == "__main__":
    unittest.main()
