# -*- coding: utf-8 -*-
"""V5 complete six-lane beforeinfo pre-first-write gate: synthetic fixtures."""
from __future__ import annotations

import copy
import unittest

from v5.beforeinfo_prewrite_gate import check_beforeinfo_prewrite
from v5.official_http_receipt import prepare_official_http_receipt
from v5_beforeinfo_test_fixtures import (
    RACE, URL, RACELIST_URL, START, CAPTURE, CUTOFF, DEADLINE,
    six_boat_html, racelist_evidence,
)


def proposal(raw=None):
    return prepare_official_http_receipt(
        requested_url=URL, final_url=URL,
        expected_source="official_beforeinfo", http_status=200,
        response_body=six_boat_html() if raw is None else raw,
        request_started_at=START, response_completed_at=CAPTURE,
    )


def result(*, receipt=None, roster=None, **kw):
    values=dict(
        receipt=proposal() if receipt is None else receipt,
        expected_race_id=RACE,
        official_deadline_at=DEADLINE,
        prediction_cutoff_at=CUTOFF,
        racelist_evidence=racelist_evidence() if roster is None else roster,
    )
    values.update(kw)
    return check_beforeinfo_prewrite(**values)


class TestV5BeforeinfoPrewrite(unittest.TestCase):
    def deny(self, why, **kw):
        x=result(**kw)
        self.assertFalse(x["prewrite_eligible"],x)
        self.assertFalse(x["forward_eligible"],x)
        self.assertEqual(x["reason"],why)

    def test_exact_structured_six_active_racers_and_predeadline_pass(self):
        x=result()
        self.assertTrue(x["prewrite_eligible"])
        self.assertEqual(x["race_id"],RACE)
        self.assertFalse(x["forward_eligible"])

    def test_no_proposal_is_not_accepted(self):
        self.deny("NO_VERIFIED_HTTP_PROPOSAL",receipt={})

    def test_reconstructed_or_wrong_source_never_passes(self):
        rec=proposal();rec["source"]="historical"
        self.deny("WRONG_SOURCE_OR_PREMATURE_FORWARD",receipt=rec)

    def test_premature_first_write_claim_rejected(self):
        rec=proposal();rec["first_write_confirmed"]=True
        self.deny("PREMATURE_FIRST_CAPTURE_ASSERTION",receipt=rec)

    def test_race_id_mismatch(self):
        self.deny("BEFOREINFO_RACE_ID_MISMATCH",expected_race_id="20261010_09_05")

    def test_missing_or_unzoned_deadline(self):
        self.deny("MISSING_OR_UNZONED_CLOCK",official_deadline_at=None)
        self.deny("MISSING_OR_UNZONED_CLOCK",official_deadline_at="2026-10-10T12:00:00")

    def test_capture_after_prediction_cutoff(self):
        self.deny("NOT_BEFORE_DECISION_CUTOFF",
                  prediction_cutoff_at="2026-10-10T11:49:59+09:00")

    def test_prediction_cutoff_after_deadline(self):
        self.deny("NOT_BEFORE_DECISION_CUTOFF",
                  prediction_cutoff_at="2026-10-10T12:01:00+09:00")

    def test_too_early_and_too_late_window(self):
        self.deny("OUTSIDE_EXHIBITION_CAPTURE_WINDOW",
                  official_deadline_at="2026-10-10T12:20:00+09:00")
        self.deny("OUTSIDE_EXHIBITION_CAPTURE_WINDOW",
                  official_deadline_at="2026-10-10T11:57:00+09:00")

    def test_modified_bytes_after_digest_rejected(self):
        rec=proposal();rec["raw_sha256"]="0"*64
        self.deny("UNVERIFIED_BEFOREINFO_BYTES",receipt=rec)

    def test_invalid_base64_rejected(self):
        rec=proposal();rec["raw_base64"]="%%bad"
        self.deny("INVALID_BEFOREINFO_ENCODING",receipt=rec)

    def test_five_structured_boats_cannot_freeze_first_capture(self):
        rec=proposal(six_boat_html(omit_lane=2))
        self.deny("NOT_EXACTLY_SIX_STRUCTURED_LANES",receipt=rec)

    def test_duplicate_lanes_do_not_collapse_silently(self):
        rec=proposal(six_boat_html(duplicate_lane=4))
        self.deny("NOT_EXACTLY_SIX_STRUCTURED_LANES",receipt=rec)

    def test_official_partial_exhibition_rejected(self):
        rec=proposal(six_boat_html(missing_time_lane=3))
        self.deny("INCOMPLETE_OR_FALLBACK_EXHIBITION",receipt=rec)

    def test_generic_fallback_six_times_not_accepted(self):
        rec=proposal(b"<html><body>6.71 6.72 6.73 6.74 6.75 6.76</body></html>")
        self.deny("NOT_EXACTLY_SIX_STRUCTURED_LANES",receipt=rec)

    def test_missing_active_racelist_refuses_prewrite(self):
        self.deny("ACTIVE_RACELIST_EVIDENCE_MISSING",roster={})

    def test_unverified_first_capture_roster_is_not_enough(self):
        rec=racelist_evidence();rec["first_write_confirmed"]=False
        self.deny("UNVERIFIED_ACTIVE_RACELIST",roster=rec)

    def test_racelist_different_race_refused(self):
        rec=racelist_evidence();rec["race_id"]="20261010_09_05"
        self.deny("UNVERIFIED_ACTIVE_RACELIST",roster=rec)

    def test_racelist_observed_after_beforeinfo_cannot_authorize(self):
        rec=racelist_evidence();rec["captured_at"]="2026-10-10T11:51:00+09:00"
        self.deny("UNVERIFIED_ACTIVE_RACELIST",roster=rec)

    def test_racelist_bad_url_refused(self):
        rec=racelist_evidence();rec["source_url"]=rec["source_url"].replace("rno=4","rno=5")
        self.deny("UNVERIFIED_ACTIVE_RACELIST",roster=rec)

    def test_six_active_boats_mandatory(self):
        rec=racelist_evidence();rec["entries"][2]["active"]=False
        self.deny("NOT_SIX_ACTIVE_RACERS",roster=rec)
        rec=racelist_evidence();rec["entries"].pop()
        self.deny("NOT_SIX_ACTIVE_RACERS",roster=rec)

    def test_no_duplicate_racer_ids_or_lanes(self):
        rec=racelist_evidence();rec["entries"][2]["racer_number"]=1002
        self.deny("DUPLICATE_OR_MISSING_RACERS",roster=rec)
        rec=racelist_evidence();rec["entries"][3]["lane"]=2
        self.deny("DUPLICATE_OR_MISSING_RACERS",roster=rec)

    def test_non_numeric_racer_id_refused(self):
        rec=racelist_evidence();rec["entries"][0]["racer_number"]=None
        self.deny("INVALID_RACER_IDENTITY",roster=rec)


if __name__=="__main__":
    unittest.main()
