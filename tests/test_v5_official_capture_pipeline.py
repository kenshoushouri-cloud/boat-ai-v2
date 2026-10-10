# -*- coding: utf-8 -*-
"""V5 mainline end-to-end tests: synthetic HTTP + synthetic transactional DB."""
from __future__ import annotations

import copy
import unittest

from v5.official_capture_pipeline import (
    CapturePipelineNotReady, capture_and_store_v5_official_source,
)
from test_v5_official_first_write_executor import FakeDB
from test_v5_official_http_transport import FakeResponse, FakeSession
from v5_beforeinfo_test_fixtures import six_boat_html, racelist_evidence, DEADLINE, CUTOFF

BEFORE = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
RACELIST = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=09&hd=20261010"
KFILE = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
RACE = "20261010_09_04"
START = "2026-10-10T11:49:59+09:00"
END = "2026-10-10T11:50:00+09:00"


def fake_clock():
    iterator = iter((START, END))
    return lambda: next(iterator)


def call(*, db=None, response=None, session=None, **overrides):
    db = FakeDB() if db is None else db
    session = FakeSession(FakeResponse(chunks=[six_boat_html()]) if response is None else response) if session is None else session
    settings = {
        "session": session,
        "connection": db,
        "requested_url": BEFORE,
        "expected_source": "official_beforeinfo",
        "expected_race_id": RACE,
        "storage_enabled": True,
        "clock": fake_clock(),
        "official_deadline_at": DEADLINE,
        "prediction_cutoff_at": CUTOFF,
        "racelist_evidence": racelist_evidence(),
    }
    settings.update(overrides)
    return capture_and_store_v5_official_source(**settings)


class TestV5OfficialCapturePipeline(unittest.TestCase):
    def deny(self, reason, **params):
        with self.assertRaises(CapturePipelineNotReady) as context:
            call(**params)
        self.assertEqual(str(context.exception), reason)

    def test_disabled_by_default_before_any_io(self):
        db = FakeDB()
        session = FakeSession()
        self.deny("V5_STORAGE_NOT_ENABLED", db=db, session=session,
                  storage_enabled=False)
        self.assertEqual(db.events, [])
        self.assertEqual(session.calls, [])

    def test_missing_explicit_connection_before_get(self):
        session = FakeSession()
        self.deny("EXPLICIT_ISOLATED_DB_CONNECTION_REQUIRED",
                  session=session, connection=None)
        self.assertEqual(session.calls, [])

    def test_missing_session_before_db(self):
        db = FakeDB()
        self.deny("EXPLICIT_HTTP_SESSION_REQUIRED", db=db, session=object())
        self.assertEqual(db.events, [])

    def test_one_official_capture_to_insert_and_readback(self):
        db, response = FakeDB(), FakeResponse(chunks=[six_boat_html()])
        result = call(db=db, response=response)
        self.assertEqual(result["status"],
                         "STORED_SOURCE_CONSISTENT_FORWARD_UNVERIFIED")
        self.assertEqual(result["storage_status"],
                         "INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED")
        self.assertEqual(result["resource_key"],"official_beforeinfo:"+RACE)
        self.assertEqual(result["response_completed_at"], END)
        self.assertTrue(result["storage_consistent"])
        self.assertTrue(result["inserted_this_attempt"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertIsNone(result["first_observed_at"])
        self.assertFalse(result["forward_eligible"])
        self.assertTrue(response.closed)
        self.assertEqual(db.events,["begin","insert","readback","commit"])
        self.assertEqual(len(db.rows), 1)
        self.assertNotIn("raw_base64", result)

    def test_identical_repeat_keeps_first(self):
        db = FakeDB()
        call(db=db)
        first = copy.deepcopy(db.rows)
        second = call(db=db)
        self.assertFalse(second["inserted_this_attempt"])
        self.assertEqual(second["storage_status"],
                         "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertEqual(db.rows, first)
        self.assertFalse(second["forward_eligible"])

    def test_changed_response_body_collides_and_rolls_back(self):
        db = FakeDB()
        call(db=db)
        first = copy.deepcopy(db.rows)
        updated = FakeResponse(chunks=[six_boat_html(variation="changed official page")])
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED", db=db, response=updated)
        self.assertEqual(db.events[-1], "rollback")
        self.assertEqual(db.rows,first)

    def test_http_transport_timeout_never_touches_db(self):
        db = FakeDB()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED", db=db,
                  session=FakeSession(error=TimeoutError("synthetic timeout")))
        self.assertEqual(db.events,[])

    def test_http_status_failure_does_not_store(self):
        db = FakeDB()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db,
                  response=FakeResponse(status=503))
        self.assertEqual(db.events,[])

    def test_redirect_does_not_store(self):
        db = FakeDB()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db,
                  response=FakeResponse(status=302))
        self.assertEqual(db.events,[])

    def test_url_source_rejected_before_http_or_db(self):
        db,sess=FakeDB(),FakeSession()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED", db=db,session=sess,
                  requested_url="https://malicious.invalid/racelist")
        self.assertEqual(db.events,[])
        self.assertEqual(sess.calls,[])

    def test_wrong_race_id_fails_before_db(self):
        db=FakeDB()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db,
                  expected_race_id="20261010_09_05")
        self.assertEqual(db.events,[])

    def test_db_insert_error_fails_closed(self):
        db=FakeDB()
        db.fail_insert=True
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db)
        self.assertEqual(db.events[-1],"rollback")
        self.assertEqual(db.rows,{})

    def test_db_readback_error_fails_closed(self):
        db=FakeDB()
        db.fail_read=True
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db)
        self.assertEqual(db.events[-1],"rollback")
        self.assertEqual(db.rows,{})

    def test_missing_readback_rolls_back(self):
        db=FakeDB()
        db.force_missing_read=True
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db)
        self.assertEqual(db.events[-1],"rollback")
        self.assertEqual(db.rows,{})

    def test_stored_tampering_never_marks_verified(self):
        db=FakeDB()
        call(db=db)
        first_key=next(iter(db.rows))
        db.rows[first_key]["raw_bytes"]=b"tampered-by-owner"
        before=copy.deepcopy(db.rows)
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db)
        self.assertEqual(db.rows,before)
        self.assertEqual(db.events[-1],"rollback")

    def test_racelist_with_matching_id(self):
        db=FakeDB()
        result=call(db=db,requested_url=RACELIST,
                    expected_source="official_racelist",
                    response=FakeResponse(url=RACELIST))
        self.assertEqual(result["resource_key"],"official_racelist:"+RACE)
        self.assertFalse(result["forward_eligible"])

    def test_k_daily_bundle_never_becomes_race_specific(self):
        db=FakeDB()
        result=call(db=db,requested_url=KFILE,
                    expected_source="official_k_file",expected_race_id=None,
                    response=FakeResponse(url=KFILE))
        self.assertEqual(result["resource_key"],"official_k_file:261009")
        self.assertFalse(result["forward_eligible"])

    def test_unsupported_k_race_id_never_stored(self):
        db=FakeDB()
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",
                  db=db,requested_url=KFILE,expected_source="official_k_file",
                  expected_race_id=RACE,response=FakeResponse(url=KFILE))
        self.assertEqual(db.events,[])

    def test_invalid_time_fails_without_db_write(self):
        db=FakeDB()
        bad_clock=iter((END, START))
        self.deny("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED",db=db,
                  clock=lambda:next(bad_clock))
        self.assertEqual(db.events,[])

    def test_old_source_is_never_forward_eligible(self):
        db=FakeDB()
        result=call(db=db)
        self.assertIn("independent", result["limitations"].lower())
        self.assertIsNone(result["first_observed_at"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertFalse(result["forward_eligible"])


if __name__ == "__main__":
    unittest.main()
