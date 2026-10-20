# -*- coding: utf-8 -*-
"""Local read-only checks for daily/monthly notification reports."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v5.ntfy_trial_performance_report import main, prepare_report


class TestV5NtfyTrialReports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / "trial.jsonl"

    def make_record(self, *, status="verified", mode="shadow"):
        r = {
            "race_id": "20261020_01_01",
            "mode": mode,
            "decision_at": "2026-10-20T11:00:00+09:00",
            "deadline_at": "2026-10-20T12:00:00+09:00",
            "prediction_receipt_sha256": "a" * 64,
            "stake_yen": 200,
            "status": status,
        }
        if mode == "actual":
            r["purchase_receipt_sha256"] = "b" * 64
        if status == "verified":
            r.update({
                "hit": True, "return_yen": 400,
                "official_result_receipt_sha256": "c" * 64,
                "official_payout_receipt_sha256": "d" * 64,
            })
        return r

    def write(self, *records):
        self.ledger.write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8",
        )

    def test_missing_ledger_fails_closed_without_sending(self):
        with patch("v5.ntfy_trial_performance_report.publish") as send:
            with contextlib.redirect_stderr(io.StringIO()):
                rc = main(["--ledger", str(self.ledger), "--period", "daily",
                           "--date", "2026-10-20", "--send"])
        self.assertEqual(rc, 2)
        send.assert_not_called()

    def test_daily_preview_uses_verified_shadow_evidence(self):
        self.write(self.make_record())
        text, verified = prepare_report(
            self.ledger, period="daily", target="2026-10-20",
        )
        self.assertTrue(verified)
        self.assertIn("的中率: 100.0%", text)
        self.assertIn("回収率: 200.0%", text)
        self.assertIn("収支: +200円", text)
        self.assertIn("実際の購入・利益を示す数字ではありません", text)

    def test_monthly_preview_and_no_actual_purchase_claim(self):
        self.write(self.make_record())
        report, verified = prepare_report(
            self.ledger, period="monthly", target="2026-10",
            mode="actual",
        )
        self.assertFalse(verified)
        self.assertIn("算出不可", report)

    def test_pending_only_holds_real_send(self):
        self.write(self.make_record(status="pending"))
        with patch("v5.ntfy_trial_performance_report.publish") as send:
            with contextlib.redirect_stderr(io.StringIO()):
                rc = main(["--ledger", str(self.ledger), "--period", "daily",
                           "--date", "2026-10-20", "--send"])
        self.assertEqual(rc, 2)
        send.assert_not_called()

    def test_valid_preview_never_sends(self):
        self.write(self.make_record())
        with patch("v5.ntfy_trial_performance_report.publish") as send:
            send.return_value = "DRY_RUN"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--ledger", str(self.ledger), "--period", "daily",
                           "--date", "2026-10-20"])
        self.assertEqual(rc, 0)
        self.assertFalse(send.call_args.kwargs["allow_send"])

    def test_real_send_still_requires_explicit_transport_authorization(self):
        self.write(self.make_record())
        with patch("v5.ntfy_trial_performance_report.publish") as send:
            send.return_value = "SENT"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--ledger", str(self.ledger), "--period", "daily",
                           "--date", "2026-10-20", "--send"])
        self.assertEqual(rc, 0)
        self.assertTrue(send.call_args.kwargs["allow_send"])

    def test_bad_decision_time_fails_closed(self):
        invalid = self.make_record()
        invalid["decision_at"] = "2026-10-20T12:15:00+09:00"
        self.write(invalid)
        with patch("v5.ntfy_trial_performance_report.publish") as send:
            with contextlib.redirect_stderr(io.StringIO()):
                rc = main(["--ledger", str(self.ledger), "--period", "daily",
                           "--date", "2026-10-20", "--send"])
        self.assertEqual(rc, 2)
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
