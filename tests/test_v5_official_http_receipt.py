# -*- coding: utf-8 -*-
"""V5 mainline HTTP receipt offline regression; zero network or DB use."""
from __future__ import annotations

import base64
import hashlib
import unittest

from v5.official_http_receipt import (
    MAX_PAGE_BYTES, UnverifiedCapture, prepare_official_http_receipt,
)

BEFORE = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
RACELIST = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=09&hd=20261010"
K = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
START = "2026-10-10T11:49:59+09:00"
END = "2026-10-10T11:50:00+09:00"
RAW = b"\x00\x01some non-utf8 \xff raw bytes"


def prepare(**changes):
    arg = dict(
        requested_url=BEFORE, final_url=BEFORE,
        expected_source="official_beforeinfo", http_status=200,
        response_body=RAW, request_started_at=START, response_completed_at=END,
    )
    arg.update(changes)
    return prepare_official_http_receipt(**arg)


class TestV5OfficialHTTPReceipt(unittest.TestCase):
    def rejected(self, reason, **changes):
        with self.assertRaises(UnverifiedCapture) as caught:
            prepare(**changes)
        self.assertEqual(str(caught.exception), reason)

    def test_valid_beforeinfo_byte_exact_provisional_only(self):
        p=prepare()
        self.assertEqual(base64.b64decode(p["raw_base64"]), RAW)
        self.assertEqual(p["raw_sha256"],hashlib.sha256(RAW).hexdigest())
        self.assertEqual(p["observed_at"],END)
        self.assertIsNone(p["first_observed_at"])
        self.assertIsNone(p["receipt_ref"])
        self.assertFalse(p["first_write_confirmed"])
        self.assertFalse(p["readback_confirmed"])
        self.assertFalse(p["forward_eligible"])

    def test_racelist_and_k_expected_names(self):
        a=prepare(requested_url=RACELIST,final_url=RACELIST,
                  expected_source="official_racelist")
        self.assertEqual(a["source"],"official_racelist")
        b=prepare(requested_url=K,final_url=K,expected_source="official_k_file")
        self.assertEqual(b["source"],"official_k_file")

    def test_proposal_hash_is_stable_but_not_receipt_id(self):
        first=prepare();second=prepare()
        self.assertEqual(first["provisional_receipt_key"],second["provisional_receipt_key"])
        changed=prepare(response_body=RAW+b".")
        self.assertNotEqual(first["provisional_receipt_key"],changed["provisional_receipt_key"])
        self.assertIsNone(first["receipt_ref"])

    def test_redirect_never_accepted_even_if_official(self):
        self.rejected("REDIRECT_OR_URL_MISMATCH",final_url=RACELIST)

    def test_wrong_kind_cannot_be_relabelled(self):
        self.rejected("SOURCE_KIND_MISMATCH",expected_source="official_k_file")

    def test_http_errors_not_captured_as_valid_official_pages(self):
        self.rejected("HTTP_RESPONSE_NOT_OK",http_status=404)
        self.rejected("HTTP_RESPONSE_NOT_OK",http_status=True)

    def test_missing_body_not_proof(self):
        self.rejected("MISSING_RAW_RESPONSE",response_body=b"")
        self.rejected("MISSING_RAW_RESPONSE",response_body="decoded text")

    def test_request_must_be_aware_and_ordered(self):
        self.rejected("UNZONED_CAPTURE_CLOCK",
                      response_completed_at="2026-10-10T11:50:00")
        self.rejected("INVALID_OR_STALE_RESPONSE_CLOCK",
                      response_completed_at="2026-10-10T11:48:00+09:00")

    def test_old_response_cannot_be_recast_as_newly_observed(self):
        self.rejected("INVALID_OR_STALE_RESPONSE_CLOCK",
                      request_started_at="2026-10-10T11:40:00+09:00")

    def test_giant_page_rejected_before_encoding(self):
        self.rejected("SOURCE_RESPONSE_TOO_LARGE",
                      response_body=b"x"*(MAX_PAGE_BYTES+1))

    def test_nonofficial_domain_and_insecure_http_fail(self):
        self.rejected("UNTRUSTED_SOURCE_URL",
                      requested_url="https://www.boatrace.jp.evil.test/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010")
        self.rejected("UNTRUSTED_SOURCE_URL",
                      requested_url=BEFORE.replace("https:", "http:"))

    def test_wrong_page_queries_rejected(self):
        self.rejected("INVALID_OFFICIAL_RACE_QUERY",
                      requested_url=BEFORE+"&admin=true")
        self.rejected("INVALID_OFFICIAL_RACE_QUERY",
                      requested_url=BEFORE+"&rno=4")
        self.rejected("INVALID_OFFICIAL_RACE_QUERY",
                      requested_url=BEFORE.replace("jcd=09","jcd=25"))

    def test_impossible_date_rejected(self):
        self.rejected("INVALID_OFFICIAL_RACE_DATE",
                      requested_url=BEFORE.replace("20261010","20260230"))

    def test_credentials_fragments_ports_disallowed(self):
        self.rejected("UNTRUSTED_SOURCE_URL",
                      requested_url=BEFORE.replace("www.boatrace.jp","user:secret@www.boatrace.jp"))
        self.rejected("UNTRUSTED_SOURCE_URL",requested_url=BEFORE+"#abc")
        self.rejected("UNTRUSTED_SOURCE_URL",
                      requested_url=BEFORE.replace("www.boatrace.jp","www.boatrace.jp:444"))

    def test_k_wrong_folder_and_query_not_allowed(self):
        self.rejected("INVALID_OFFICIAL_K_DATE",
                      requested_url=K.replace("/202610/", "/202609/"))
        self.rejected("INVALID_OFFICIAL_K_PATH",requested_url=K+"?foo=1")

    def test_k_bad_calendar_file_not_allowed(self):
        self.rejected("INVALID_OFFICIAL_K_DATE",
                      requested_url=K.replace("k261009","k261032"))


if __name__ == "__main__":
    unittest.main()
