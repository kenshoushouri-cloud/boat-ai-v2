"""Offline contract tests for the one-shot realtime snapshot audit."""
import contextlib
import io
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import odds_evidence_realtime_snapshot_audit as rt


class RealtimeSnapshotAuditTests(unittest.TestCase):
    def env(self):
        return {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REPOSITORY": rt.REPO,
            "GITHUB_REF": "refs/heads/" + rt.BRANCH,
            "GITHUB_ACTOR": rt.OWNER,
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "a" * 40,
            "REALTIME_SNAPSHOT_AUDIT_CONFIRMATION": rt.CONFIRMATION,
            "REALTIME_SNAPSHOT_AUDIT_COMMIT_MESSAGE": rt.COMMIT_MESSAGE,
            "ADMIN_DATABASE_URL": "postgresql://admin:secret@x.proxy.rlwy.net:1234/railway",
        }

    def test_authorization_is_exact_and_single_attempt(self):
        rt.authorize(self.env())
        for key in self.env():
            with self.subTest(key=key):
                bad = self.env()
                bad.pop(key)
                with self.assertRaises(rt.RealtimeSnapshotAuditError):
                    rt.authorize(bad)
        bad = self.env()
        bad["GITHUB_RUN_ATTEMPT"] = "2"
        with self.assertRaises(rt.RealtimeSnapshotAuditError):
            rt.authorize(bad)

    def test_scope_is_fixed_and_minimal(self):
        self.assertEqual(set(rt.ALLOWED_COLUMNS), {
            "v2_races", "v2_realtime_odds_snapshots"
        })
        self.assertEqual(rt.ALLOWED_COLUMNS["v2_races"], ("race_id", "deadline_at"))
        self.assertEqual(rt.ALLOWED_COLUMNS["v2_realtime_odds_snapshots"],
                         ("race_id", "snapshot_label", "snapshot_at", "ticket"))
        self.assertEqual(len(rt.audit.TARGET_RACES), 19)
        self.assertNotEqual(rt.ROLE_NAME, rt.base_guard.ROLE_NAME)

    def test_safe_datetime_requires_timezone(self):
        value = datetime(2026, 9, 8, tzinfo=timezone.utc)
        self.assertTrue(rt._safe_dt(value).endswith("+00:00"))
        with self.assertRaises(rt.RealtimeSnapshotAuditError):
            rt._safe_dt(datetime(2026, 9, 8))

    def test_unauthorized_fails_before_admin_connection(self):
        with patch.object(rt.base_executor, "admin_connection") as admin, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rt.main({}), 1)
        admin.assert_not_called()

    def test_failure_output_is_sanitized(self):
        with patch.object(rt.base_executor, "admin_connection",
                          side_effect=RuntimeError("private-secret")), \
             patch.object(rt, "_write_result") as write, \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rt.main(self.env()), 1)
        self.assertNotIn("private-secret", err.getvalue())
        payload = write.call_args.args[0]
        self.assertEqual(payload["execution_status"], "BLOCKED")
        self.assertEqual(payload["historical_roi_approval"], "BLOCKED")
        self.assertEqual(payload["production_promotion"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
