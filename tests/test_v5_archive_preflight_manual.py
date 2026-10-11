"""Tests never launch psql or touch a live database."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "ops" / "v5_archive_preflight_manual.py"
spec = importlib.util.spec_from_file_location("v5_archive_preflight_manual", MODULE)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class FakeRun:
    calls = None

    def __call__(self, args, **kw):
        self.calls = (args, kw)
        return subprocess.CompletedProcess(args, 0, stdout="PRESENT\nINDEX_FALSE\n", stderr="")


class PreflightManualTests(unittest.TestCase):
    def test_default_no_connection_even_with_connection_profile(self):
        with patch.object(preflight.subprocess, "run", side_effect=AssertionError("CALLED")):
            self.assertEqual(preflight.execute_once({"PGHOST": "db", "PGDATABASE": "x", "PGUSER": "u"})["status"],
                             "DISABLED_BY_DEFAULT")

    def test_only_single_opt_in_is_not_enough(self):
        with patch.object(preflight.subprocess, "run", side_effect=AssertionError("CALLED")):
            result = preflight.execute_once({"V5_PREFLIGHT_OPT_IN": preflight.ENABLE,
                                             "PGSERVICE": "archive-ro"})
            self.assertEqual(result["status"], "DISABLED_BY_DEFAULT")

    def test_url_only_profile_rejected(self):
        with self.assertRaisesRegex(ValueError, "LIBPQ_PROFILE_REQUIRED"):
            preflight.connection_profile({"DATABASE_URL": "password-secret"})

    def test_libpq_credentials_kept_out_of_command_and_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp)/"catalog.sql"
            fp.write_bytes(b"BEGIN TRANSACTION READ ONLY;\nCOMMIT;\n")
            sha = hashlib.sha1(b"blob " + str(fp.stat().st_size).encode()
                               + b"\0" + fp.read_bytes()).hexdigest()
            env = {"V5_PREFLIGHT_OPT_IN": preflight.ENABLE,
                   "V5_PREFLIGHT_DB_TARGET": preflight.TARGET,
                   "PGSERVICE": "archive-ro", "PGPASSWORD": "dont-log-me",
                   "DATABASE_URL": "postgres://dont-print-me"}
            fake = FakeRun()
            with patch.object(preflight, "SQL_BLOB_SHA", sha):
                result = preflight.execute_once(env, sql_path=fp, run_command=fake)
            args, kw = fake.calls
            self.assertEqual(result["status"], "CATALOG_RESULTS_REQUIRE_MANUAL_REVIEW")
            self.assertEqual(result["catalog_output"], "PRESENT\nINDEX_FALSE\n")
            self.assertNotIn("dont-log-me", repr(args))
            self.assertNotIn("dont-print-me", repr(kw))
            self.assertTrue(kw["env"]["PGOPTIONS"].startswith("-c default_transaction_read_only=on"))
            self.assertNotIn("DATABASE_URL", kw["env"])
            self.assertFalse(result["buy_eligible"])

    def test_modified_sql_is_rejected_before_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp)/"catalog.sql"
            fp.write_text("DROP TABLE public.v2_races;", encoding="utf-8")
            fake = FakeRun()
            with self.assertRaisesRegex(ValueError, "PREFLIGHT_SQL_HASH_MISMATCH"):
                preflight.execute_once({"V5_PREFLIGHT_OPT_IN": preflight.ENABLE,
                    "V5_PREFLIGHT_DB_TARGET": preflight.TARGET,
                    "PGSERVICE": "archive-ro"}, sql_path=fp, run_command=fake)
            self.assertIsNone(fake.calls)

    def test_psql_errors_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp)/"catalog.sql"
            fp.write_bytes(b"BEGIN READ ONLY;\n")
            sha=hashlib.sha1(b"blob " + str(fp.stat().st_size).encode() + b"\0" + fp.read_bytes()).hexdigest()
            def fake(_args, **_kw):
                return subprocess.CompletedProcess([], 1, stdout="", stderr="password=SECRETPASS")
            with patch.object(preflight, "SQL_BLOB_SHA", sha):
                result=preflight.execute_once({"V5_PREFLIGHT_OPT_IN": preflight.ENABLE,
                    "V5_PREFLIGHT_DB_TARGET": preflight.TARGET,
                    "PGSERVICE": "archive-ro"}, sql_path=fp, run_command=fake)
            self.assertEqual(result["status"], "LOCAL_PREFLIGHT_SQL_FAILED")
            self.assertNotIn("SECRETPASS", repr(result))

    def test_lock_and_statement_limits(self):
        x=preflight.connection_profile({"PGHOST":"host","PGDATABASE":"archive","PGUSER":"readonly"})
        self.assertIn("statement_timeout=2000",x["PGOPTIONS"])
        self.assertIn("lock_timeout=250",x["PGOPTIONS"])
        self.assertEqual(x["PGCONNECT_TIMEOUT"],"3")


if __name__ == "__main__":
    unittest.main()
