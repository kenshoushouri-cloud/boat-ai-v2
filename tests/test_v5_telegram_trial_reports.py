"""No network or DB access: telegram send guards and trial-stat integrity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from v5.telegram_trial_transport import get_retry_after, send_message
from v5.telegram_trial_performance import (
    aggregate, load_ledger, parse_record, render_report,
)

RECEIPT = "a" * 64
EVENT = {
    "race_id": "20261020_01_06",
    "mode": "shadow",
    "decision_at": "2026-10-20T17:30:00+09:00",
    "deadline_at": "2026-10-20T17:50:00+09:00",
    "prediction_receipt_sha256": RECEIPT,
    "stake_yen": 300,
    "status": "verified",
    "hit": True,
    "return_yen": 1200,
    "official_result_receipt_sha256": "b"*64,
    "official_payout_receipt_sha256": "c"*64,
}


class TestTrialMessageAndStats(unittest.TestCase):
    def test_dry_run_does_not_send(self):
        post = Mock(side_effect=AssertionError("must not send"))
        self.assertEqual(send_message("V5試験中", http_post=post), "DRY_RUN")
        post.assert_not_called()

    def test_explicit_send_authorization_required(self):
        with self.assertRaisesRegex(ValueError, "disabled"):
            send_message("test", allow_send=True, environ={})

    def test_real_send_is_one_message_and_credentials_are_not_logged(self):
        post = Mock(return_value=Mock(status_code=200, json=lambda: {"ok": True}))
        env = {"V5_TELEGRAM_SEND": "YES", "TELEGRAM_BOT_TOKEN": "example",
               "TELEGRAM_CHAT_ID": "12345"}
        self.assertEqual(send_message("hello", allow_send=True,
                                      environ=env, http_post=post), "SENT")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["json"]["text"], "hello")
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 20))

    def test_rate_limit_backoff_is_bounded(self):
        responses = [Mock(status_code=429,
                          json=lambda: {"parameters": {"retry_after": 2}}),
                     Mock(status_code=200, json=lambda: {"ok": True})]
        post = Mock(side_effect=responses)
        waits = []
        env = {"V5_TELEGRAM_SEND": "YES", "TELEGRAM_BOT_TOKEN": "example",
               "TELEGRAM_CHAT_ID": "12345"}
        self.assertEqual(send_message("test", allow_send=True, environ=env,
                                      http_post=post, sleep=waits.append), "SENT")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(waits, [2])
        self.assertEqual(get_retry_after({"parameters": {"retry_after": 100}}), 0)

    def test_valid_shadow_ledger_metrics(self):
        data = parse_record(dict(EVENT))
        metrics = aggregate([data], period="daily", target="2026-10-20", mode="shadow")
        self.assertEqual((metrics["total"], metrics["verified"], metrics["hit"]), (1, 1, 1))
        msg = render_report(metrics, period="daily", target="2026-10-20", mode="shadow")
        self.assertIn("的中率: 100.0%", msg)
        self.assertIn("回収率: 400.0%", msg)
        self.assertIn("収支: +900円", msg)
        self.assertIn("仮想", msg)

    def test_pending_is_not_counted_as_loss(self):
        pending = dict(EVENT)
        pending.update({"race_id": "20261020_01_07", "status": "pending",
                        "hit": None, "return_yen": None})
        pending.pop("official_result_receipt_sha256")
        pending.pop("official_payout_receipt_sha256")
        x = aggregate([parse_record(EVENT), parse_record(pending)],
                      period="monthly", target="2026-10", mode="shadow")
        self.assertEqual((x["total"], x["verified"], x["pending"]), (2, 1, 1))
        self.assertIn("暫定", render_report(x, period="monthly", target="2026-10", mode="shadow"))

    def test_no_data_is_unavailable_not_zero_roi(self):
        summary = aggregate([], period="daily", target="2026-10-20", mode="shadow")
        msg = render_report(summary, period="daily", target="2026-10-20", mode="shadow")
        self.assertIn("算出不可", msg)
        self.assertNotIn("回収率: 0", msg)

    def test_fail_closed_for_leakage_unverified_result_actual(self):
        not_before = dict(EVENT, decision_at="2026-10-20T17:55:00+09:00")
        with self.assertRaisesRegex(ValueError, "before deadline"):
            parse_record(not_before)
        missing_receipt = dict(EVENT)
        del missing_receipt["official_payout_receipt_sha256"]
        with self.assertRaisesRegex(ValueError, "official_payout_receipt"):
            parse_record(missing_receipt)
        actual = dict(EVENT, mode="actual")
        with self.assertRaisesRegex(ValueError, "purchase_receipt"):
            parse_record(actual)

    def test_duplicate_ledger_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            data = json.dumps(EVENT) + "\n"
            path.write_text(data + data, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_ledger(path)


if __name__ == "__main__":
    unittest.main()
