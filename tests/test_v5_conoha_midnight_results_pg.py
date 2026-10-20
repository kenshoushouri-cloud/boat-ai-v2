"""Stdlib-only tests for fail-closed midnight result catcher; no DB or HTTP."""
from datetime import date, timedelta
from types import ModuleType
import unittest
from unittest.mock import patch

from v5.conoha_midnight_results_pg import recover_one, resolved, target_date


def _fake_parser(page):
    module = ModuleType("repair_month_all_pg")
    calls = []
    module._fetch = lambda _url: "OFFICIAL_HTML"
    module._looks_no_race = lambda _html: False
    module._official_url = lambda *args: "https://example.invalid/"
    module.parse_result = lambda _html: dict(page)

    def save(*args, **kwargs):
        calls.append((args, kwargs))
        return 1

    module.upsert_rows = save
    return module, calls


class TestMidnightResults(unittest.TestCase):
    def test_verified_payout_only(self):
        self.assertTrue(resolved("official", "1-2-3", 6180))
        for status, ticket, payout in (
            ("official", "1-1-2", 6180),
            ("official", "1-2-3", 0),
            ("official", "1-2-3", None),
            ("official", "1-2-3", "6180"),
            ("official", "7-2-3", 6180),
            ("no_result_page", None, 0),
            ("parse_error", None, 0),
            ("", None, 0),
        ):
            with self.subTest(status=status, ticket=ticket, payout=payout):
                self.assertFalse(resolved(status, ticket, payout))
        self.assertTrue(resolved("cancelled", None, 0))
        self.assertTrue(resolved("trifecta_invalid", None, 0))

    def test_previous_day_default(self):
        today = date(2026, 10, 20)
        self.assertEqual(target_date(None, today), today - timedelta(days=1))
        self.assertEqual(target_date("2026-10-18", today), date(2026, 10, 18))

    def test_reject_today_future_or_invalid_date(self):
        today = date(2026, 10, 20)
        for raw in ("2026-10-20", "2026-10-21", "20261019",
                    "2026-02-30", "2025-06-30"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    target_date(raw, today)

    def test_never_write_unverified_responses(self):
        for page in (
            {"result_status": "no_result_page", "race_status": "no_result_page"},
            {"result_status": "parse_error", "race_status": "parse_error"},
            {"result_status": "official", "trifecta_ticket": "1-2-3",
             "trifecta_payout_yen": 0},
        ):
            with self.subTest(page=page):
                fake, calls = _fake_parser(page)
                with patch.dict("sys.modules", {"repair_month_all_pg": fake}):
                    outcome = recover_one("20261019_19_12", date(2026, 10, 19))
                self.assertEqual(outcome, "PENDING_UNVERIFIED")
                self.assertEqual(calls, [])

    def test_only_verified_results_upserted(self):
        fake, calls = _fake_parser({
            "result_status": "official", "race_status": "official",
            "trifecta_ticket": "1-2-3", "trifecta_payout_yen": 6180,
        })
        with patch.dict("sys.modules", {"repair_month_all_pg": fake}):
            outcome = recover_one("20261019_19_12", date(2026, 10, 19))
        self.assertEqual(outcome, "SAVED_OFFICIAL")
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args[0], "v2_results")
        self.assertEqual(args[1][0]["race_date"], "2026-10-19")
        self.assertEqual(args[1][0]["race_id"], "20261019_19_12")
        self.assertEqual(args[2], "race_id")
        self.assertEqual(kwargs["chunk_size"], 1)

    def test_official_cancellation_may_be_saved(self):
        fake, calls = _fake_parser({
            "result_status": "cancelled", "race_status": "cancelled",
            "trifecta_ticket": None, "trifecta_payout_yen": 0,
        })
        with patch.dict("sys.modules", {"repair_month_all_pg": fake}):
            outcome = recover_one("20261019_19_12", date(2026, 10, 19))
        self.assertEqual(outcome, "SAVED_CANCELLED")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
