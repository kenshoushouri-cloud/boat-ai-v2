# -*- coding: utf-8 -*-
"""Beforeinfo gate must reject fabricated active flags and unverified origins.

All payloads are synthetic and NO true official start-status evidence exists.
"""
from __future__ import annotations

import unittest

from v5.beforeinfo_prewrite_gate import check_beforeinfo_prewrite
from v5.official_http_receipt import prepare_official_http_receipt
from v5_beforeinfo_test_fixtures import (
    RACE, URL, RACELIST_URL, START, CAPTURE, CUTOFF, DEADLINE,
    six_boat_html,
)


def proposal(raw=None):
    return prepare_official_http_receipt(
        requested_url=URL, final_url=URL,
        expected_source="official_beforeinfo", http_status=200,
        response_body=six_boat_html() if raw is None else raw,
        request_started_at=START, response_completed_at=CAPTURE,
    )


def binder_like_candidate():
    # This is a fake binder-shaped map, NOT evidence. Even its internally
    # plausible six racer IDs MUST NOT authorize a first-write INSERT.
    return {
        "contract": "V5_RACELIST_ORIGINAL_READBACK_V1",
        "source": "official_racelist",
        "race_id": RACE,
        "source_url": RACELIST_URL,
        "captured_at": "2026-10-10T11:48:00+09:00",
        "raw_sha256": "a" * 64,
        "readback_consistent": True,
        "first_write_confirmed": False,
        "all_active_verified": False,
        "forward_eligible": False,
        "entries": [
            {"lane": i, "racer_number": 1000 + i, "racer_class": "A1",
             "no_cancellation_marker": True, "active_verified": False}
            for i in range(1, 7)
        ],
    }


def result(*, receipt=None, roster=None, **kw):
    values = {
        "receipt": proposal() if receipt is None else receipt,
        "expected_race_id": RACE,
        "official_deadline_at": DEADLINE,
        "prediction_cutoff_at": CUTOFF,
        "racelist_evidence": binder_like_candidate() if roster is None else roster,
    }
    values.update(kw)
    return check_beforeinfo_prewrite(**values)


class TestV5BeforeinfoPrewrite(unittest.TestCase):
    def denied(self, why, **kw):
        r=result(**kw)
        self.assertFalse(r["prewrite_eligible"],r)
        self.assertFalse(r["forward_eligible"],r)
        self.assertEqual(r["reason"],why)

    def test_complete_six_boat_candidate_still_not_active_proof(self):
        self.denied("ACTIVE_START_STATUS_NOT_PROVEN")

    def test_reject_missing_http_proposal(self):
        self.denied("NO_VERIFIED_HTTP_PROPOSAL",receipt={})

    def test_reject_reconstructed_beforeinfo(self):
        p=proposal();p["source"]="historical"
        self.denied("WRONG_SOURCE_OR_PREMATURE_FORWARD",receipt=p)

    def test_reject_premature_source_proof(self):
        p=proposal();p["first_write_confirmed"]=True
        self.denied("PREMATURE_FIRST_CAPTURE_ASSERTION",receipt=p)

    def test_reject_wrong_race_id(self):
        self.denied("BEFOREINFO_RACE_ID_MISMATCH",
                    expected_race_id="20261010_09_05")

    def test_missing_or_naive_deadline(self):
        self.denied("MISSING_OR_UNZONED_CLOCK",official_deadline_at=None)
        self.denied("MISSING_OR_UNZONED_CLOCK",
                    official_deadline_at="2026-10-10T12:00:00")

    def test_capture_after_cutoff(self):
        self.denied("NOT_BEFORE_DECISION_CUTOFF",
                    prediction_cutoff_at="2026-10-10T11:49:59+09:00")

    def test_cutoff_after_deadline(self):
        self.denied("NOT_BEFORE_DECISION_CUTOFF",
                    prediction_cutoff_at="2026-10-10T12:01:00+09:00")

    def test_too_early_or_late_capture(self):
        self.denied("OUTSIDE_EXHIBITION_CAPTURE_WINDOW",
                    official_deadline_at="2026-10-10T12:20:00+09:00")
        self.denied("OUTSIDE_EXHIBITION_CAPTURE_WINDOW",
                    official_deadline_at="2026-10-10T11:57:00+09:00")

    def test_modified_bytes_rejected(self):
        p=proposal();p["raw_sha256"]="0"*64
        self.denied("UNVERIFIED_BEFOREINFO_BYTES",receipt=p)

    def test_invalid_base64_rejected(self):
        p=proposal();p["raw_base64"]="@@@"
        self.denied("INVALID_BEFOREINFO_ENCODING",receipt=p)

    def test_five_structured_lanes_refused(self):
        self.denied("NOT_EXACTLY_SIX_STRUCTURED_LANES",
                    receipt=proposal(six_boat_html(omit_lane=2)))

    def test_duplicate_structured_lane_refused(self):
        self.denied("NOT_EXACTLY_SIX_STRUCTURED_LANES",
                    receipt=proposal(six_boat_html(duplicate_lane=4)))

    def test_partial_exhibition_refused(self):
        self.denied("INCOMPLETE_OR_FALLBACK_EXHIBITION",
                    receipt=proposal(six_boat_html(missing_time_lane=3)))

    def test_text_only_exhibition_fallback_refused(self):
        self.denied("NOT_EXACTLY_SIX_STRUCTURED_LANES",
                    receipt=proposal(b"<html>6.71 6.72 6.73 6.74 6.75 6.76</html>"))

    def test_missing_racelist_readback_refused(self):
        self.denied("RACELIST_ORIGINAL_READBACK_MISSING",roster={})

    def test_old_self_asserted_racelist_claims_refused(self):
        old={"source":"official_racelist","race_id":RACE,
             "first_write_confirmed":True,"readback_confirmed":True,
             "entries":[{"lane":i,"racer_number":1000+i,"active":True}
                        for i in range(1,7)]}
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=old)

    def test_lied_first_write_or_all_active_flag_rejected(self):
        r=binder_like_candidate();r["first_write_confirmed"]=True
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)
        r=binder_like_candidate();r["all_active_verified"]=True
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)

    def test_mismatched_racelist_race_or_url_rejected(self):
        r=binder_like_candidate();r["race_id"]="20261010_09_05"
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)
        r=binder_like_candidate();r["source_url"]=RACELIST_URL.replace("rno=4","rno=5")
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)

    def test_late_racelist_observation_rejected(self):
        r=binder_like_candidate();r["captured_at"]="2026-10-10T11:51:00+09:00"
        self.denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED",roster=r)

    def test_five_candidates_refused(self):
        r=binder_like_candidate();r["entries"].pop()
        self.denied("RACELIST_NOT_SIX_CANDIDATES",roster=r)

    def test_incorrect_candidate_registration_or_cancellation_refused(self):
        r=binder_like_candidate();r["entries"][1]["racer_number"]=None
        self.denied("RACELIST_CANDIDATE_INVALID",roster=r)
        r=binder_like_candidate();r["entries"][1]["no_cancellation_marker"]=False
        self.denied("RACELIST_CANDIDATE_INVALID",roster=r)

    def test_forged_entry_active_verified_true_rejected(self):
        r=binder_like_candidate()
        for row in r["entries"]:
            row["active"]=True
        self.denied("ACTIVE_START_STATUS_NOT_PROVEN",roster=r)
        r["entries"][0]["active_verified"]=True
        self.denied("ACTIVE_STATUS_CLAIM_UNVERIFIED",roster=r)

    def test_duplicate_racers_or_lanes_refused(self):
        r=binder_like_candidate();r["entries"][1]["racer_number"]=1001
        self.denied("RACELIST_DUPLICATE_OR_MISSING_CANDIDATES",roster=r)
        r=binder_like_candidate();r["entries"][1]["lane"]=1
        self.denied("RACELIST_DUPLICATE_OR_MISSING_CANDIDATES",roster=r)


if __name__=="__main__":
    unittest.main()
