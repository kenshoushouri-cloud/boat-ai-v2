"""Offline fail-closed tests for V5 native official racelist single-race canary.

Only pure validators and mocked I/O: no database, HTTP, timers or writes.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from v5 import native_stage_race_entries_pg as module

JST = timezone(timedelta(hours=9))


def entries(rid="20261027_01_01"):
    return [{"race_id": rid, "lane": lane, "racer_number": 4000 + lane}
            for lane in range(1, 7)]


class NativeCoreContractTests(unittest.TestCase):
    def test_valid_race_id(self):
        self.assertEqual(module.race_parts("20261027_24_12"),
                         ("2026-10-27", "24", 12))

    def test_reject_bad_ids(self):
        for rid in ("20261027_25_01", "20261027_01_13", "20261027_1_1",
                    "20261027_01_01;DROP", "20261027_01_00"):
            with self.subTest(rid=rid), self.assertRaises(ValueError):
                module.race_parts(rid)

    def test_exactly_six_entries(self):
        module.validate_entries("20261027_01_01", entries())

    def test_reject_missing_lane(self):
        with self.assertRaisesRegex(RuntimeError, "SIX_UNIQUE_LANES"):
            module.validate_entries("20261027_01_01", entries()[:5])

    def test_reject_duplicate_lane(self):
        rows = entries()
        rows[5]["lane"] = 1
        with self.assertRaisesRegex(RuntimeError, "SIX_UNIQUE_LANES"):
            module.validate_entries("20261027_01_01", rows)

    def test_reject_duplicate_racer(self):
        rows = entries()
        rows[5]["racer_number"] = rows[0]["racer_number"]
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE_RACER"):
            module.validate_entries("20261027_01_01", rows)

    def test_reject_mismatched_race_id(self):
        rows = entries()
        rows[2]["race_id"] = "20261027_01_02"
        with self.assertRaisesRegex(RuntimeError, "BAD_RACE_ID"):
            module.validate_entries("20261027_01_01", rows)

    def test_reject_invalid_racer_number(self):
        rows = entries()
        rows[0]["racer_number"] = None
        with self.assertRaisesRegex(RuntimeError, "INVALID_RACER_NUMBER"):
            module.validate_entries("20261027_01_01", rows)

    def test_only_fixed_stage_identifiers(self):
        self.assertEqual(set(module.ALLOWED_COLUMNS), {"races", "entries"})
        self.assertEqual(module.KEYS["races"], ("race_id",))
        self.assertEqual(module.KEYS["entries"], ("race_id", "lane"))
        self.assertEqual(module.LOCK, 2026102503)

    def test_apply_requires_local_database_before_any_connection(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://badhost/railway"}):
            with self.assertRaisesRegex(RuntimeError, "CONOHA_LOCAL_PG_ONLY"):
                module.apply_one({}, [], datetime.now(JST))

    def test_apply_requires_explicit_approval_before_any_connection(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql:///railway"},
                        clear=True):
            with self.assertRaisesRegex(RuntimeError, "NO_EXPLICIT_CORE_WRITE_APPROVAL"):
                module.apply_one({}, [], datetime.now(JST))

    def test_buy_flag_blocks_pre_db(self):
        env = {"DATABASE_URL": "postgresql:///railway",
               "V5_NATIVE_CORE_STAGE_WRITE_APPROVED": "YES",
               "BUY_ENABLED": "YES"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BUY_FLAG_PRESENT"):
                module.apply_one({}, [], datetime.now(JST))

    def test_stage_delta_pending_blocks(self):
        class FrozenTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 26, 22, 25, tzinfo=JST)
        with patch.object(module, "datetime", FrozenTime):
            with self.assertRaisesRegex(RuntimeError, "DELTA_PENDING"):
                module.blocked_by_stage_delta()

    def test_preview_never_calls_apply(self):
        rid = "20261027_01_01"
        fake_now = datetime(2026, 10, 26, 22, 25, tzinfo=JST)
        payload = ({"race_id": rid, "deadline_at": "2026-10-27T10:00:00+09:00"},
                   entries(rid))
        with patch.object(module, "official_fetch", return_value=("<html/>", fake_now)), \
             patch.object(module, "official_payload", return_value=payload), \
             patch.object(module, "apply_one") as apply:
            self.assertEqual(module.main(["--race-id", rid]), 0)
            apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
