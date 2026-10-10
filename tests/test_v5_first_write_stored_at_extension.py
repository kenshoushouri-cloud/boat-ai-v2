"""Targeted OFFLINE injected-cursor tests; no SQL execution/DB/network."""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.official_first_write_storage import (
    INSERT_FIRST, READ_FIRST, verify_first_write_readback,
)
from v5.official_first_write_executor import (
    READ_COLUMNS, FirstWriteRejected, persist_first_http_capture,
)

JST = timezone(timedelta(hours=9))
START = datetime(2026, 10, 11, 11, 0, tzinfo=JST)
DONE = START + timedelta(seconds=3)
STORED = DONE + timedelta(seconds=1)
RAW = b"synthetic-stored-at-fixture"
HASH = hashlib.sha256(RAW).hexdigest()
RACE = "20261011_03_02"
KEY = f"official_beforeinfo:{RACE}"
URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=2&jcd=03&hd=20261011"


def plan():
    params = (KEY, "official_beforeinfo", RACE, URL, START, DONE, RAW, HASH)
    return dict(status="PREPARED_ONLY_NO_DB_WRITE", resource_key=KEY,
                race_id=RACE, source_kind="official_beforeinfo",
                raw_sha256=HASH, sql=INSERT_FIRST, params=params,
                read_sql=READ_FIRST, read_params=(KEY,),
                first_observed_at=None, first_write_confirmed=False,
                forward_eligible=False)


def frozen():
    return dict(zip(READ_COLUMNS, (*plan()["params"], STORED)))


class FakeCursor:
    def __init__(self, rows, *, tuple_row=False, duplicate=False):
        self.rows = rows
        self.tuple_row = tuple_row
        self.duplicate = duplicate
        self.events = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.events.append(sql)
        if sql == INSERT_FIRST:
            self.result = None if self.duplicate else (KEY,)
        elif sql == READ_FIRST:
            self.result = (
                tuple(self.rows[col] for col in READ_COLUMNS)
                if self.tuple_row and isinstance(self.rows, dict)
                else self.rows
            )
        else:
            raise AssertionError("Unexpected SQL / prohibited DDL")

    def fetchone(self):
        return self.result


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.conn.rolled_back = exc_type is not None
        return False


class FakeConnection:
    def __init__(self, rows, *, tuple_row=False, duplicate=False):
        self.fake_cursor = FakeCursor(rows, tuple_row=tuple_row, duplicate=duplicate)
        self.entered = False
        self.rolled_back = False

    def transaction(self):
        return FakeTransaction(self)

    def cursor(self):
        return self.fake_cursor


class StoredAtExtensionTests(unittest.TestCase):
    def assert_safe(self, verdict):
        self.assertIsNone(verdict["first_observed_at"])
        self.assertFalse(verdict["first_write_confirmed"])
        self.assertFalse(verdict["forward_eligible"])

    def test_select_column_contract_has_stored_at_last(self):
        self.assertEqual(len(READ_COLUMNS), 9)
        self.assertEqual(READ_COLUMNS[-1], "stored_at")
        self.assertIn("raw_bytes,raw_sha256,stored_at", READ_FIRST.replace("\n", ""))
        self.assertNotIn("UPDATE ", INSERT_FIRST.upper())

    def test_mapping_readback_success_never_approves(self):
        conn = FakeConnection(frozen())
        result = persist_first_http_capture(conn, plan())
        self.assertTrue(result["storage_consistent"])
        self.assertTrue(result["db_stored_at_readback_consistent"])
        self.assert_safe(result)
        self.assertEqual(conn.fake_cursor.events, [INSERT_FIRST, READ_FIRST])

    def test_tuple_readback_success_never_approves(self):
        conn = FakeConnection(frozen(), tuple_row=True)
        result = persist_first_http_capture(conn, plan())
        self.assertTrue(result["db_stored_at_readback_consistent"])
        self.assert_safe(result)

    def test_duplicate_identical_readback_is_not_first_observed(self):
        conn = FakeConnection(frozen(), duplicate=True)
        result = persist_first_http_capture(conn, plan())
        self.assertFalse(result["inserted_this_attempt"])
        self.assertEqual(result["status"], "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assert_safe(result)

    def test_missing_stored_at_rejected(self):
        bad = frozen()
        bad.pop("stored_at")
        conn = FakeConnection(bad)
        with self.assertRaisesRegex(FirstWriteRejected, "DB_STORED_AT_MISSING_OR_INVALID"):
            persist_first_http_capture(conn, plan())
        self.assertTrue(conn.rolled_back)

    def test_stored_at_wrong_types_or_timezone_rejected(self):
        for value in (None, "2026-10-11T11:00:04+09:00", STORED.replace(tzinfo=None)):
            with self.subTest(value=value):
                bad = frozen()
                bad["stored_at"] = value
                result = verify_first_write_readback(plan(), bad, inserted_this_attempt=True)
                self.assertEqual(result["status"], "DB_STORED_AT_MISSING_OR_INVALID")
                self.assert_safe(result)

    def test_transaction_start_before_finished_response_rejected(self):
        bad = frozen()
        bad["stored_at"] = START
        result = verify_first_write_readback(plan(), bad, inserted_this_attempt=True)
        self.assertEqual(result["status"], "DB_STORED_AT_BEFORE_RESPONSE_COMPLETION")
        self.assertFalse(result["db_stored_at_readback_consistent"])
        self.assert_safe(result)

    def test_mutated_raw_bytes_or_digest_still_rejected(self):
        for field, value in (("raw_bytes", b"tampered"), ("raw_sha256", "0" * 64)):
            with self.subTest(field=field):
                bad = frozen()
                bad[field] = value
                result = verify_first_write_readback(plan(), bad, inserted_this_attempt=False)
                self.assertEqual(result["status"], "FIRST_WRITE_COLLISION_OR_TAMPERING")
                self.assert_safe(result)

    def test_legacy_eight_column_tuple_fails_closed(self):
        conn = FakeConnection(tuple(frozen()[key] for key in READ_COLUMNS[:-1]))
        with self.assertRaisesRegex(FirstWriteRejected, "READBACK_SHAPE_INVALID"):
            persist_first_http_capture(conn, plan())
        self.assertTrue(conn.rolled_back)

    def test_bad_mapping_storage_clock_fails_closed(self):
        bad = frozen()
        bad["response_completed_at"] = DONE + timedelta(seconds=2)
        result = verify_first_write_readback(plan(), bad, inserted_this_attempt=True)
        self.assertEqual(result["status"], "FIRST_WRITE_COLLISION_OR_TAMPERING")
        self.assert_safe(result)


if __name__ == "__main__":
    unittest.main()
