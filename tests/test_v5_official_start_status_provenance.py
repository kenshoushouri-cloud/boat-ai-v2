# -*- coding: utf-8 -*-
"""Synthetic official-style records. These NEVER establish all-six active."""
from __future__ import annotations

import base64
import hashlib
import unittest

from v5.official_http_receipt import prepare_official_http_receipt
from v5.official_start_status_provenance import classify_predeadline_start_status
from v5_beforeinfo_test_fixtures import (
    RACE, URL, RACELIST_URL, START, CAPTURE, CUTOFF, DEADLINE,
    six_boat_html,
)


def fake_first_readback():
    return {
        "contract": "V5_RACELIST_ORIGINAL_READBACK_V1",
        "source": "official_racelist", "race_id": RACE,
        "source_url": RACELIST_URL,
        "captured_at": "2026-10-10T11:48:00+09:00",
        "raw_sha256": hashlib.sha256(b"synthetic-racelist").hexdigest(),
        "readback_consistent": True,
        "all_active_verified": False,
        "first_write_confirmed": False,
        "forward_eligible": False,
        "entries": [
            {"lane": i, "racer_number": 1000+i, "racer_class": "A1",
             "active_verified": False}
            for i in range(1, 7)
        ],
    }


def receipt(body=None):
    return prepare_official_http_receipt(
        requested_url=URL, final_url=URL,
        expected_source="official_beforeinfo", http_status=200,
        response_body=six_boat_html() if body is None else body,
        request_started_at=START, response_completed_at=CAPTURE,
    )


def check(*, body=None, raw_receipt=None, roster=None, **kwargs):
    args=dict(
        beforeinfo_receipt=receipt(body) if raw_receipt is None else raw_receipt,
        racelist_readback=fake_first_readback() if roster is None else roster,
        expected_race_id=RACE, official_deadline_at=DEADLINE,
        prediction_cutoff_at=CUTOFF,
    )
    args.update(kwargs)
    return classify_predeadline_start_status(**args)


class TestV5OfficialStartStatusProvenance(unittest.TestCase):
    def denied(self, reason, **kwargs):
        result=check(**kwargs)
        self.assertEqual(result["status"],"UNVERIFIED_SOURCE")
        self.assertEqual(result["reason"],reason)
        self.assertFalse(result["beforeinfo_prewrite_eligible"])
        self.assertFalse(result["forward_eligible"])

    def test_six_exhibition_rows_not_all_active(self):
        r=check()
        self.assertEqual(r["status"],"SIX_EXHIBITION_CANDIDATES_START_UNKNOWN")
        self.assertTrue(r["exhibition_six_complete"])
        self.assertFalse(r["all_six_active_confirmed"])
        self.assertFalse(r["beforeinfo_prewrite_eligible"])
        self.assertFalse(r["forward_eligible"])
        self.assertEqual(r["explicit_withdrawals"],[])

    def test_explicit_lanewise_withdrawal(self):
        html=six_boat_html().replace(b"synthetic",b"synthetic")
        html=html.replace("選手2".encode(),"選手2欠場".encode())
        r=check(body=html)
        self.assertEqual(r["status"],"EXPLICIT_WITHDRAWAL_DISPLAYED")
        self.assertEqual([x["lane"] for x in r["explicit_withdrawals"]],[2])
        self.assertFalse(r["all_six_active_confirmed"])

    def test_whitespace_separated_fullwidth_withdrawal_marker(self):
        html=six_boat_html().replace("選手4".encode(),"選手4　欠　場".encode())
        r=check(body=html)
        self.assertEqual(r["status"],"EXPLICIT_WITHDRAWAL_DISPLAYED")
        self.assertEqual(r["explicit_withdrawals"][0]["lane"],4)

    def test_explicit_cancellation_marker_in_one_row(self):
        html=six_boat_html().replace("選手5".encode(),"選手5出走取消".encode())
        r=check(body=html)
        self.assertEqual(r["status"],"EXPLICIT_WITHDRAWAL_DISPLAYED")
        self.assertEqual(r["explicit_withdrawals"][0]["lane"],5)

    def test_partial_exhibition_not_mistaken_for_active(self):
        r=check(body=six_boat_html(missing_time_lane=2))
        self.assertEqual(r["status"],"INCOMPLETE_EXHIBITION_START_UNKNOWN")
        self.assertFalse(r["all_six_active_confirmed"])

    def test_page_with_missing_structured_lane_denied(self):
        self.denied("BEFOREINFO_NOT_SIX_STRUCTURED_LANES",
                    body=six_boat_html(omit_lane=3))

    def test_page_with_duplicate_lane_denied(self):
        self.denied("BEFOREINFO_NOT_SIX_STRUCTURED_LANES",
                    body=six_boat_html(duplicate_lane=3))

    def test_text_elsewhere_must_not_imply_row_withdrawal(self):
        body=six_boat_html().replace(b"</body>", "お知らせ欠場情報</body>".encode())
        r=check(body=body)
        self.assertEqual(r["status"],"SIX_EXHIBITION_CANDIDATES_START_UNKNOWN")
        self.assertEqual(r["explicit_withdrawals"],[])

    def test_unknown_source_proposal_denied(self):
        self.denied("BEFOREINFO_CAPTURE_PROPOSAL_UNVERIFIED",raw_receipt={})

    def test_spoofed_first_write_flag_denied(self):
        src=receipt();src["first_write_confirmed"]=True
        self.denied("BEFOREINFO_CAPTURE_PROPOSAL_UNVERIFIED",raw_receipt=src)

    def test_missing_independent_readback_denied(self):
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster={})

    def test_spoofed_racelist_active_bool_denied(self):
        r=fake_first_readback();r["all_active_verified"]=True
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)

    def test_readback_race_mismatch_denied(self):
        r=fake_first_readback();r["race_id"]="20261010_09_05"
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)

    def test_url_race_mismatch_denied(self):
        r=fake_first_readback();r["source_url"]=RACELIST_URL.replace("rno=4","rno=5")
        self.denied("SOURCE_RACE_ID_MISMATCH",roster=r)

    def test_tampered_beforeinfo_hash_denied(self):
        src=receipt();src["raw_sha256"]="0"*64
        self.denied("ORIGINAL_BEFOREINFO_SHA256_MISMATCH",raw_receipt=src)

    def test_unparseable_base64_denied(self):
        src=receipt();src["raw_base64"]="invalid####"
        self.denied("ORIGINAL_BEFOREINFO_ENCODING_INVALID",raw_receipt=src)

    def test_bad_unicode_charset_failclosed(self):
        self.denied("ORIGINAL_BEFOREINFO_CHARSET_UNKNOWN",body=b"\xffbad encoding")

    def test_naive_clock_rejected(self):
        self.denied("SOURCE_URL_OR_CLOCK_UNVERIFIED",
                    official_deadline_at="2026-10-10T12:00:00")

    def test_after_prediction_cutoff_denied(self):
        self.denied("NOT_FRESH_PREDEADLINE_EVIDENCE",
                    prediction_cutoff_at="2026-10-10T11:49:00+09:00")

    def test_beforeinfo_outside_predeadline_window_denied(self):
        self.denied("NOT_FRESH_PREDEADLINE_EVIDENCE",
                    official_deadline_at="2026-10-10T12:20:00+09:00")

    def test_stale_or_late_racelist_denied(self):
        r=fake_first_readback();r["captured_at"]="2026-10-09T11:00:00+09:00"
        self.denied("NOT_FRESH_PREDEADLINE_EVIDENCE",roster=r)
        r=fake_first_readback();r["captured_at"]="2026-10-10T11:52:00+09:00"
        self.denied("NOT_FRESH_PREDEADLINE_EVIDENCE",roster=r)

    def test_fake_active_per_racer_not_allowed(self):
        r=fake_first_readback();r["entries"][0]["active_verified"]=True
        self.denied("RACELIST_CANDIDATE_ROSTER_INVALID",roster=r)

    def test_incomplete_racelist_rejected(self):
        r=fake_first_readback();r["entries"].pop()
        self.denied("RACELIST_CANDIDATE_ROSTER_INVALID",roster=r)

    def test_duplicate_racer_denied(self):
        r=fake_first_readback();r["entries"][1]["racer_number"]=1001
        self.denied("RACELIST_CANDIDATE_ROSTER_INVALID",roster=r)

    def test_malformed_lane_denied(self):
        r=fake_first_readback();r["entries"][0]["lane"]="1"
        self.denied("RACELIST_CANDIDATE_ROSTER_INVALID",roster=r)

    def test_even_synthetic_all_entries_positive_text_not_official_active_proof(self):
        html=six_boat_html().replace("選手1".encode(),"選手1出走".encode())
        r=check(body=html)
        self.assertEqual(r["status"],"SIX_EXHIBITION_CANDIDATES_START_UNKNOWN")
        self.assertFalse(r["all_six_active_confirmed"])


if __name__=="__main__":
    unittest.main()
