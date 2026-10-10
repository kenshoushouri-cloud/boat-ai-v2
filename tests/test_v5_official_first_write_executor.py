# -*- coding: utf-8 -*-
"""Synthetic transactional DB regression; no psycopg/Railway/network used."""
from __future__ import annotations

import copy
import unittest

from v5.official_http_receipt import prepare_official_http_receipt
from v5.official_first_write_storage import prepare_first_write_storage, INSERT_FIRST, READ_FIRST
from v5.official_first_write_executor import persist_first_http_capture, FirstWriteRejected

URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
K_URL = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
RACE = "20261010_09_04"
START = "2026-10-10T11:49:59+09:00"
END = "2026-10-10T11:50:00+09:00"


def make_plan(*, payload=b"first-beforeinfo-data", url=URL, expected=RACE):
    source = "official_k_file" if url == K_URL else "official_beforeinfo"
    proposed = prepare_official_http_receipt(
        requested_url=url, final_url=url, expected_source=source,
        http_status=200, response_body=payload,
        request_started_at=START, response_completed_at=END,
    )
    return prepare_first_write_storage(proposed, expected_race_id=expected)


class FakeTransaction:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.events.append("begin")
        self.db.staged = copy.deepcopy(self.db.rows)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.db.events.append("rollback")
            self.db.staged = None
            return False
        if self.db.fail_commit:
            self.db.events.append("rollback_on_commit_failure")
            self.db.staged = None
            raise RuntimeError("synthetic commit failure")
        self.db.rows = self.db.staged
        self.db.staged = None
        self.db.events.append("commit")
        return False


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        if sql == INSERT_FIRST:
            self.db.events.append("insert")
            if self.db.fail_insert:
                raise RuntimeError("synthetic insert failure with hidden credentials")
            (key, kind, race_id, url, start, end, raw, sha) = params
            if key not in self.db.staged:
                self.db.staged[key] = {
                    "resource_key": key, "source_kind": kind,
                    "race_id": race_id, "source_url": url,
                    "request_started_at": start,
                    "response_completed_at": end,
                    "raw_bytes": bytes(raw), "raw_sha256": sha,
                    "stored_at": end,
                }
                self.result = ("other-resource",) if self.db.wrong_returning_key else (key,)
            else:
                self.result = None
        elif sql == READ_FIRST:
            self.db.events.append("readback")
            if self.db.fail_read:
                raise RuntimeError("synthetic read failure with hidden SQL")
            if self.db.force_missing_read:
                self.result = None
                return
            row = (self.db.staged if self.db.staged is not None else self.db.rows).get(params[0])
            if row is None:
                self.result = None
            elif self.db.tuple_read:
                names = ("resource_key", "source_kind", "race_id", "source_url",
                         "request_started_at", "response_completed_at", "raw_bytes", "raw_sha256",
                         "stored_at")
                self.result = tuple(row[k] for k in names)
            else:
                self.result = row
        else:
            raise AssertionError("unexpected SQL: DDL/UPDATE not permitted")

    def fetchone(self):
        return self.result


class FakeDB:
    def __init__(self):
        self.rows = {}
        self.staged = None
        self.events = []
        self.fail_insert = False
        self.fail_read = False
        self.fail_commit = False
        self.force_missing_read = False
        self.wrong_returning_key = False
        self.tuple_read = False

    def transaction(self):
        return FakeTransaction(self)

    def cursor(self):
        return FakeCursor(self)


class TestV5FirstWriteExecutor(unittest.TestCase):
    def denied(self, expected, conn, plan):
        with self.assertRaises(FirstWriteRejected) as error:
            persist_first_http_capture(conn, plan)
        self.assertEqual(str(error.exception), expected)

    def test_new_insert_select_commit(self):
        db = FakeDB()
        result = persist_first_http_capture(db, make_plan())
        self.assertEqual(result["status"], "INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED")
        self.assertTrue(result["inserted_this_attempt"])
        self.assertTrue(result["storage_consistent"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertIsNone(result["first_observed_at"])
        self.assertFalse(result["forward_eligible"])
        self.assertEqual(db.events, ["begin", "insert", "readback", "commit"])
        self.assertEqual(len(db.rows), 1)

    def test_second_identical_read_no_overwrite(self):
        db = FakeDB(); plan = make_plan()
        persist_first_http_capture(db, plan)
        before = copy.deepcopy(db.rows)
        result = persist_first_http_capture(db, plan)
        self.assertFalse(result["inserted_this_attempt"])
        self.assertEqual(result["status"], "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertEqual(db.rows, before)
        self.assertEqual(db.events[-4:], ["begin", "insert", "readback", "commit"])

    def test_divergent_body_rollback_keeps_first(self):
        db=FakeDB()
        persist_first_http_capture(db,make_plan())
        saved=copy.deepcopy(db.rows)
        self.denied("FIRST_WRITE_COLLISION_OR_TAMPERING",db,
                    make_plan(payload=b"different later value"))
        self.assertEqual(db.events[-4:],["begin","insert","readback","rollback"])
        self.assertEqual(db.rows,saved)

    def test_reordered_query_collision_preserves_initial_row(self):
        db=FakeDB();persist_first_http_capture(db,make_plan())
        old=copy.deepcopy(db.rows)
        reordered="https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20261010&jcd=09&rno=4"
        self.denied("FIRST_WRITE_COLLISION_OR_TAMPERING",db,
                    make_plan(url=reordered))
        self.assertEqual(db.rows,old)

    def test_readback_missing_rolls_back_own_insert(self):
        db=FakeDB();db.force_missing_read=True
        self.denied("FIRST_WRITE_READBACK_MISSING",db,make_plan())
        self.assertEqual(db.rows,{})
        self.assertEqual(db.events[-1],"rollback")

    def test_db_insert_exception_rolls_back_and_scrubs_error(self):
        db=FakeDB();db.fail_insert=True
        self.denied("DATABASE_TRANSACTION_FAILED",db,make_plan())
        self.assertEqual(db.rows,{})
        self.assertEqual(db.events,["begin","insert","rollback"])

    def test_db_read_exception_rolls_back(self):
        db=FakeDB();db.fail_read=True
        self.denied("DATABASE_TRANSACTION_FAILED",db,make_plan())
        self.assertEqual(db.rows,{})
        self.assertEqual(db.events,["begin","insert","readback","rollback"])

    def test_commit_failure_not_reported_as_success(self):
        db=FakeDB();db.fail_commit=True
        self.denied("DATABASE_TRANSACTION_FAILED",db,make_plan())
        self.assertEqual(db.rows,{})
        self.assertEqual(db.events[-1],"rollback_on_commit_failure")

    def test_wrong_insert_returned_resource_rolls_back(self):
        db=FakeDB();db.wrong_returning_key=True
        self.denied("INSERT_RETURNING_WRONG_RESOURCE",db,make_plan())
        self.assertEqual(db.rows,{})
        self.assertEqual(db.events,["begin","insert","rollback"])

    def test_default_tuple_db_row_shape_supported(self):
        db=FakeDB();db.tuple_read=True
        r=persist_first_http_capture(db,make_plan())
        self.assertTrue(r["storage_consistent"])

    def test_corrupt_stored_bytes_refused(self):
        db=FakeDB();p=make_plan()
        persist_first_http_capture(db,p)
        db.rows[p["resource_key"]]["raw_bytes"]=b"bad"
        before=copy.deepcopy(db.rows)
        self.denied("FIRST_WRITE_COLLISION_OR_TAMPERING",db,p)
        self.assertEqual(db.rows,before)

    def test_corrupt_stored_url_refused(self):
        db=FakeDB();p=make_plan()
        persist_first_http_capture(db,p)
        db.rows[p["resource_key"]]["source_url"]="https://fake.invalid"
        self.denied("FIRST_WRITE_COLLISION_OR_TAMPERING",db,p)

    def test_wrong_race_frozen_refused(self):
        db=FakeDB();p=make_plan()
        persist_first_http_capture(db,p)
        db.rows[p["resource_key"]]["race_id"]="20261010_09_05"
        self.denied("FIRST_WRITE_COLLISION_OR_TAMPERING",db,p)

    def test_no_connection_never_attempts_db(self):
        self.denied("EXPLICIT_TRANSACTION_CONNECTION_REQUIRED",None,make_plan())

    def test_plan_sql_tamper_rejected_without_transaction(self):
        db=FakeDB();p=make_plan();p["sql"]="UPDATE v2_results SET payout=0"
        self.denied("UNVERIFIED_OR_TAMPERED_STORAGE_PLAN",db,p)
        self.assertEqual(db.events,[])

    def test_plan_read_sql_tamper_rejected_without_transaction(self):
        db=FakeDB();p=make_plan();p["read_sql"]="SELECT * FROM v2_results"
        self.denied("UNVERIFIED_OR_TAMPERED_STORAGE_PLAN",db,p)
        self.assertEqual(db.events,[])

    def test_plan_digest_tamper_rejected_without_db(self):
        db=FakeDB();p=make_plan();p["params"]=(*p["params"][:-1],"0"*64)
        self.denied("STORAGE_PARAMETER_INTEGRITY_FAILED",db,p)
        self.assertEqual(db.events,[])

    def test_plan_source_identity_tamper_rejected(self):
        db=FakeDB();p=make_plan()
        # Internal tuple changed as well as advertised values; fail against URL.
        values=list(p["params"]);values[0]="official_beforeinfo:wrong"
        p["params"]=tuple(values);p["resource_key"]=values[0]
        p["read_params"]=(values[0],)
        self.denied("STORAGE_IDENTITY_OR_CLOCK_FAILED",db,p)
        self.assertEqual(db.events,[])

    def test_claimed_first_write_or_forward_rejected(self):
        db=FakeDB();p=make_plan();p["first_write_confirmed"]=True
        self.denied("UNVERIFIED_OR_TAMPERED_STORAGE_PLAN",db,p)
        p=make_plan();p["forward_eligible"]=True
        self.denied("UNVERIFIED_OR_TAMPERED_STORAGE_PLAN",db,p)
        self.assertEqual(db.events,[])

    def test_k_daily_bundle_first_write(self):
        db=FakeDB()
        r=persist_first_http_capture(db,make_plan(url=K_URL,expected=None))
        self.assertEqual(r["resource_key"],"official_k_file:261009")
        self.assertEqual(len(db.rows),1)
        self.assertFalse(r["forward_eligible"])

    def test_transaction_uses_exactly_two_fixed_statements(self):
        db=FakeDB();persist_first_http_capture(db,make_plan())
        self.assertEqual(db.events.count("insert"),1)
        self.assertEqual(db.events.count("readback"),1)
        self.assertEqual(db.events.count("commit"),1)


if __name__=="__main__":
    unittest.main()
