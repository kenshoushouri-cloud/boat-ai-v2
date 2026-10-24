"""Offline psql-fallback regression tests. DB is never contacted."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from deploy.conoha import v5_online_stage_batch_copy as stage


class PsqlFallbackTests(TestCase):
    def test_readonly_preview_uses_exact_twelve_stage_pairs(self):
        captured = {}
        def fake_run(args, *, input, **kwargs):
            captured["args"] = args
            captured["sql"] = input
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                returncode=0,
                stdout="V5_STAGE_ALL_12_PREVIEW_READ_ONLY_FINISHED\n",
                stderr="",
            )
        with patch.object(stage.subprocess, "run", side_effect=fake_run):
            with redirect_stdout(StringIO()) as stdout:
                code = stage.psql_fallback_all_preview()
        self.assertEqual(code, 0)
        sql = captured["sql"]
        self.assertEqual(sql.count("('public.v2_"), 12)
        self.assertNotIn("('public.v2_venues'", sql)
        self.assertIn("boat_data_stage.entry_snapshots", sql)
        self.assertNotIn("v5_data.raw_", sql)
        self.assertIn("BEGIN TRANSACTION READ ONLY", sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertNotIn("CREATE TABLE", sql)
        self.assertNotIn("INSERT INTO", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("DELETE FROM", sql)
        self.assertEqual(captured["args"][-1], "railway")
        self.assertIn("COPY_PERFORMED=NO CUTOVER=NO_GO",stdout.getvalue())

    def test_missing_psql_completion_marker_fails_closed(self):
        with patch.object(stage.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout="(12 rows)\n",stderr="")):
            with self.assertRaisesRegex(RuntimeError, "marker"):
                stage.psql_fallback_all_preview()

    def test_psql_error_is_no_go(self):
        with patch.object(stage.subprocess, "run", return_value=SimpleNamespace(
                returncode=2, stdout="", stderr="permission denied")):
            with redirect_stderr(StringIO()):
                self.assertEqual(stage.psql_fallback_all_preview(),2)

    def test_unexpected_stage_identifier_is_rejected(self):
        with patch.dict(stage.TARGETS, {"public.v2_races":("boat_data_stage.races;DROP",1)}):
            with self.assertRaisesRegex(ValueError,"identifier"):
                stage.psql_fallback_all_preview()
