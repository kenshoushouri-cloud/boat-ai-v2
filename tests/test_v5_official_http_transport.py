# -*- coding: utf-8 -*-
"""Offline only. Fake HTTP transport; neither network nor database is called."""
from __future__ import annotations

import unittest

from v5.official_http_receipt import UnverifiedCapture, MAX_PAGE_BYTES
from v5.official_http_transport import (
    CHUNK_BYTES, capture_v5_official_response,
)

BEFORE = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
RACELIST = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=09&hd=20261010"
KFILE = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
RACE = "20261010_09_04"
NOW = ["2026-10-10T11:49:59+09:00", "2026-10-10T11:50:00+09:00"]


class FakeResponse:
    def __init__(self, url=BEFORE, status=200, chunks=None,
                 headers=None, history=None, read_exception=None):
        self.url = url
        self.status_code = status
        self.chunks = [b"first", b"-actual", b"-bytes"] if chunks is None else chunks
        self.headers = headers or {}
        self.history = [] if history is None else history
        self.read_exception = read_exception
        self.closed = False
        self.read_args = []

    def iter_content(self, *, chunk_size):
        self.read_args.append(chunk_size)
        for chunk in self.chunks:
            yield chunk
        if self.read_exception is not None:
            raise self.read_exception

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = FakeResponse() if response is None else response
        self.error = error
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url,kwargs))
        if self.error:
            raise self.error
        return self.response


def clock(*values):
    it = iter(values)
    return lambda: next(it)


def run(session=None, **kwargs):
    session = FakeSession() if session is None else session
    args = dict(
        session=session, requested_url=BEFORE,
        expected_source="official_beforeinfo",
        expected_race_id=RACE, clock=clock(*NOW),
    )
    args.update(kwargs)
    return capture_v5_official_response(**args)


class TestV5HTTPTransport(unittest.TestCase):
    def deny(self, expected, *, session=None, **changes):
        with self.assertRaises(UnverifiedCapture) as e:
            run(session=session, **changes)
        self.assertEqual(str(e.exception), expected)

    def test_real_bytes_clock_and_storage_plan_proposal_only(self):
        response=FakeResponse()
        session=FakeSession(response)
        result=run(session=session)
        p=result["receipt_proposal"]
        plan=result["storage_plan"]
        self.assertEqual(result["status"],"HTTP_OBSERVED_STORAGE_NOT_EXECUTED")
        self.assertEqual(plan["params"][6],b"first-actual-bytes")
        self.assertEqual(p["response_completed_at"],NOW[1])
        self.assertEqual(p["request_started_at"],NOW[0])
        self.assertIsNone(p["first_observed_at"])
        self.assertIsNone(result["first_observed_at"])
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(plan["first_write_confirmed"])
        self.assertFalse(plan["forward_eligible"])
        self.assertTrue(response.closed)
        self.assertEqual(response.read_args,[CHUNK_BYTES])
        self.assertEqual(session.calls,[(BEFORE,{"allow_redirects":False,
                       "stream":True,"timeout":15.0})])

    def test_racelist_and_k_resource_keys(self):
        for url,source,expected,key in [
            (RACELIST,"official_racelist",RACE,"official_racelist:"+RACE),
            (KFILE,"official_k_file",None,"official_k_file:261009"),
        ]:
            res=FakeResponse(url=url)
            a=run(FakeSession(res),requested_url=url,
                  expected_source=source,expected_race_id=expected)
            self.assertEqual(a["storage_plan"]["resource_key"],key)
            self.assertTrue(res.closed)

    def test_unknown_host_refused_before_get_or_clock(self):
        sess=FakeSession()
        self.deny("UNTRUSTED_SOURCE_URL",session=sess,
                  requested_url="https://not-official.invalid/foo",
                  clock=lambda: self.fail("clock cannot run"))
        self.assertEqual(sess.calls,[])

    def test_wrong_expected_source_refused_without_get(self):
        sess=FakeSession()
        self.deny("SOURCE_KIND_MISMATCH",session=sess,expected_source="official_k_file")
        self.assertEqual(sess.calls,[])

    def test_invalid_timeout_no_network(self):
        sess=FakeSession()
        self.deny("INVALID_TRANSPORT_TIMEOUT",session=sess,timeout_seconds=0)
        self.deny("INVALID_TRANSPORT_TIMEOUT",session=sess,timeout_seconds=61)
        self.assertEqual(sess.calls,[])

    def test_no_session_rejected(self):
        self.deny("HTTP_SESSION_REQUIRED",session=object())

    def test_transport_timeout_no_false_timestamp(self):
        sess=FakeSession(error=TimeoutError("synthetic timeout"))
        self.deny("HTTP_TRANSPORT_FAILED",session=sess)
        self.assertEqual(len(sess.calls),1)

    def test_non_200_response_rejected_and_closed(self):
        r=FakeResponse(status=503)
        self.deny("HTTP_RESPONSE_NOT_OK",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_redirect_refused_and_response_closed(self):
        r=FakeResponse(status=302)
        self.deny("HTTP_RESPONSE_NOT_OK",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_final_url_mismatch_rejected(self):
        r=FakeResponse(url=RACELIST)
        self.deny("REDIRECT_OR_URL_MISMATCH",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_redirect_history_even_same_url_refused(self):
        r=FakeResponse(history=[{"status_code":301}])
        self.deny("REDIRECT_HISTORY_NOT_ALLOWED",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_oversized_content_length_rejected_prestream(self):
        r=FakeResponse(headers={"Content-Length":str(MAX_PAGE_BYTES+1)})
        self.deny("SOURCE_RESPONSE_TOO_LARGE",session=FakeSession(r))
        self.assertEqual(r.read_args,[])
        self.assertTrue(r.closed)

    def test_bad_content_length_rejected(self):
        for declared in ("nan", "-1"):
            r=FakeResponse(headers={"Content-Length":declared})
            self.deny("INVALID_CONTENT_LENGTH",session=FakeSession(r))
            self.assertTrue(r.closed)

    def test_stream_exceed_size_even_without_length_header(self):
        r=FakeResponse(chunks=[b"A"*MAX_PAGE_BYTES,b"B"])
        self.deny("SOURCE_RESPONSE_TOO_LARGE",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_invalid_chunk_is_rejected(self):
        r=FakeResponse(chunks=[b"valid","not bytes"])
        self.deny("INVALID_HTTP_BYTE_CHUNK",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_stream_timeout_or_connection_failure_fails(self):
        r=FakeResponse(read_exception=TimeoutError("stream stopped"))
        self.deny("HTTP_STREAM_FAILED",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_empty_body_does_not_generate_storage_plan(self):
        r=FakeResponse(chunks=[b"",b""])
        self.deny("MISSING_RAW_RESPONSE",session=FakeSession(r))
        self.assertTrue(r.closed)

    def test_finish_clock_must_be_after_start_not_stale(self):
        r=FakeResponse()
        self.deny("INVALID_OR_STALE_RESPONSE_CLOCK",session=FakeSession(r),
                  clock=clock("2026-10-10T11:50:00+09:00",
                              "2026-10-10T11:49:59+09:00"))
        self.assertTrue(r.closed)
        r=FakeResponse()
        self.deny("INVALID_OR_STALE_RESPONSE_CLOCK",session=FakeSession(r),
                  clock=clock("2026-10-10T11:40:00+09:00",
                              "2026-10-10T11:50:00+09:00"))

    def test_timezone_naive_clock_not_proof(self):
        sess=FakeSession()
        self.deny("UNZONED_CAPTURE_CLOCK",session=sess,
                  clock=clock("2026-10-10T11:49:59"))
        self.assertEqual(sess.calls,[])

    def test_storage_identity_collision_protected_by_existing_plan(self):
        r=FakeResponse()
        self.deny("RACE_ID_OR_DAILY_K_MISMATCH",session=FakeSession(r),
                  expected_race_id="20261010_09_05")
        self.assertTrue(r.closed)

    def test_blank_chunk_is_ignored_not_used_as_observation_time(self):
        r=FakeResponse(chunks=[b"",b"A",b"",b"B"])
        res=run(FakeSession(r))
        self.assertEqual(res["storage_plan"]["params"][6],b"AB")
        self.assertEqual(res["receipt_proposal"]["response_completed_at"],NOW[1])


if __name__=="__main__":
    unittest.main()
