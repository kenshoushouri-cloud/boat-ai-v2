"""Offline contract tests for the base-vs-realtime ticket-set comparison."""
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import odds_evidence_realtime_set_compare as cmp


class RealtimeSetCompareTests(unittest.TestCase):
    def env(self):
        return {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REPOSITORY": cmp.REPO,
            "GITHUB_REF": "refs/heads/" + cmp.BRANCH,
            "GITHUB_ACTOR": cmp.OWNER,
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "a" * 40,
            "REALTIME_SET_COMPARE_CONFIRMATION": cmp.CONFIRMATION,
            "REALTIME_SET_COMPARE_COMMIT_MESSAGE": cmp.COMMIT_MESSAGE,
            "ADMIN_DATABASE_URL": "postgresql://admin:secret@x.proxy.rlwy.net:1234/railway",
        }

    def test_authorization_is_exact(self):
        cmp.authorize(self.env())
        for key in self.env():
            with self.subTest(key=key):
                bad = self.env()
                bad.pop(key)
                with self.assertRaises(cmp.RealtimeSetCompareError):
                    cmp.authorize(bad)

    def test_scope_is_fixed_and_no_odds_values_are_read(self):
        self.assertEqual(set(cmp.ALLOWED_COLUMNS), {
            "v2_races", "v2_odds_trifecta", "v2_realtime_odds_snapshots"
        })
        self.assertNotIn("odds", cmp.ALLOWED_COLUMNS["v2_odds_trifecta"])
        self.assertNotIn("odds", cmp.ALLOWED_COLUMNS["v2_realtime_odds_snapshots"])
        self.assertIn("source", cmp.ALLOWED_COLUMNS["v2_realtime_odds_snapshots"])
        self.assertEqual(len(cmp.audit.TARGET_RACES), 19)

    def test_shared_scope_configuration_is_explicit(self):
        old_role = cmp.shared.ROLE_NAME
        old_columns = cmp.shared.ALLOWED_COLUMNS
        try:
            cmp._configure_shared_scope()
            self.assertEqual(cmp.shared.ROLE_NAME, cmp.ROLE_NAME)
            self.assertEqual(cmp.shared.ALLOWED_COLUMNS, cmp.ALLOWED_COLUMNS)
        finally:
            cmp.shared.ROLE_NAME = old_role
            cmp.shared.ALLOWED_COLUMNS = old_columns

    def test_unauthorized_stops_before_admin_connection(self):
        with patch.object(cmp.shared.base_executor, "admin_connection") as admin, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cmp.main({}), 1)
        admin.assert_not_called()

    def test_failure_is_sanitized_and_blocked(self):
        old_role = cmp.shared.ROLE_NAME
        old_columns = cmp.shared.ALLOWED_COLUMNS
        try:
            with patch.object(cmp.shared.base_executor, "admin_connection",
                              side_effect=RuntimeError("private-secret")), \
                 patch.object(cmp, "_write") as write, \
                 contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cmp.main(self.env()), 1)
            self.assertNotIn("private-secret", err.getvalue())
            payload = write.call_args.args[0]
            self.assertEqual(payload["execution_status"], "BLOCKED")
            self.assertEqual(payload["root_cause"], "UNDETERMINED")
            self.assertEqual(payload["historical_roi_approval"], "BLOCKED")
        finally:
            cmp.shared.ROLE_NAME = old_role
            cmp.shared.ALLOWED_COLUMNS = old_columns


if __name__ == "__main__":
    unittest.main()
