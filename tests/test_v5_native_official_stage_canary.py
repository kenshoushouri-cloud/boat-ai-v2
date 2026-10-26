"""No-network, no-DB guards for V5 official discovery -> stage canary."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from v5 import native_official_stage_canary as m

JST = timezone(timedelta(hours=9))
SAMPLE_TIME = datetime(2026, 10, 27, 6, 30, tzinfo=JST)
RACE = {
    "race_id": "20261027_01_01",
    "race_date": "2026-10-27",
    "deadline_at": "2026-10-27T15:22:00+09:00",
}
ENTRIES = [
    {"race_id": RACE["race_id"], "lane": x, "racer_number": 3000+x}
    for x in range(1,7)
]


class DirectStageCanaryTests(unittest.TestCase):
    def test_preflight_denies_missing_database_before_http(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CONOHA_LOCAL"):
                m.preflight_apply_without_http_or_db()

    def test_preflight_denies_missing_flags(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql:///railway"},
                        clear=True):
            with self.assertRaisesRegex(RuntimeError, "MISSING_CANARY"):
                m.preflight_apply_without_http_or_db()

    def test_preflight_denies_buy(self):
        env = {"DATABASE_URL": "postgresql:///railway", **m.REQUIRED,
               "AUTO_BUY": "YES"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BUY_MUST_BE_OFF"):
                m.preflight_apply_without_http_or_db()

    def test_preflight_must_verify_delta(self):
        env = {"DATABASE_URL": "postgresql:///railway", **m.REQUIRED}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(m, "blocked_by_stage_delta") as block:
            m.preflight_apply_without_http_or_db()
            block.assert_called_once()

    def test_no_official_venues_returns_no_selection(self):
        with patch.object(m, "fetch_official_index", return_value="<html/>"), \
             patch.object(m, "official_venues", return_value=[]), \
             patch.object(m, "official_fetch") as one:
            self.assertIsNone(m.collect_single_official("20261027", 3))
            one.assert_not_called()

    def test_bounded_one_official_race_sample(self):
        with patch.object(m, "fetch_official_index", return_value="INDEX"), \
             patch.object(m, "official_venues", return_value=["01", "02"]), \
             patch.object(m, "official_fetch", return_value=("HTML", SAMPLE_TIME)) as fetch, \
             patch.object(m, "official_payload", return_value=(RACE, ENTRIES)):
            sample = m.collect_single_official("20261027", 3)
            self.assertIsNotNone(sample)
            fetch.assert_called_once_with("20261027_01_01")

    def test_bad_first_race_falls_back_to_next_official_venue(self):
        def download(rid):
            if rid.endswith("_01_01"):
                raise RuntimeError("not yet published")
            return "HTML", SAMPLE_TIME
        second_race = {**RACE, "race_id": "20261027_02_01"}
        with patch.object(m, "fetch_official_index", return_value="INDEX"), \
             patch.object(m, "official_venues", return_value=["01", "02"]), \
             patch.object(m, "official_fetch", side_effect=download) as fetch, \
             patch.object(m, "official_payload", return_value=(second_race, ENTRIES)):
            sample = m.collect_single_official("20261027", 2)
            self.assertEqual(sample[0]["race_id"], "20261027_02_01")
            self.assertEqual(fetch.call_count, 2)

    def test_reject_bad_identity(self):
        wrong = {**RACE, "race_id": "20261027_01_02"}
        with patch.object(m, "fetch_official_index", return_value="INDEX"), \
             patch.object(m, "official_venues", return_value=["01"]), \
             patch.object(m, "official_fetch", return_value=("HTML", SAMPLE_TIME)), \
             patch.object(m, "official_payload", return_value=(wrong, ENTRIES)):
            with self.assertRaisesRegex(RuntimeError, "IDENTITY"):
                m.collect_single_official("20261027", 1)

    def test_reject_unbounded_venue_count(self):
        with self.assertRaisesRegex(ValueError, "MAX_VENUES"):
            m.collect_single_official("20261027", 24)

    def test_preview_uses_no_writes(self):
        with patch.object(m, "collect_single_official",
                          return_value=(RACE, ENTRIES, SAMPLE_TIME)), \
             patch.object(m, "apply_one") as apply, \
             patch.object(m, "preflight_apply_without_http_or_db") as gate, \
             patch.object(m, "choose_day", return_value="20261027"):
            self.assertEqual(m.main(["--day", "20261027"]), 0)
            apply.assert_not_called()
            gate.assert_not_called()

    def test_apply_cannot_fetch_before_gate(self):
        with patch.object(m, "preflight_apply_without_http_or_db",
                          side_effect=RuntimeError("HOLD")), \
             patch.object(m, "collect_single_official") as collect, \
             patch.object(m, "choose_day", return_value="20261027"):
            with self.assertRaisesRegex(RuntimeError, "HOLD"):
                m.main(["--apply", "--day", "20261027"])
            collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
