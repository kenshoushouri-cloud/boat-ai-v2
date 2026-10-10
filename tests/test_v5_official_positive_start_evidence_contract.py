# -*- coding: utf-8 -*-
"""Real pilot aggregate METADATA regression, no raw official body/network/DB."""
from __future__ import annotations

from copy import deepcopy
import unittest

from v5.official_positive_start_evidence_contract import (
    APPROVED_POSITIVE_SOURCE_SCHEMAS,
    review_positive_start_evidence,
)

RACE = "20261010_03_01"
DEADLINE = "2026-10-10T11:14:00+09:00"
CUTOFF = "2026-10-10T11:09:00+09:00"
EMPTY_HEADERS = {"出走確定":0, "出走状況":0, "出走予定":0, "欠場":0}


def real_metadata_fixture():
    # These byte lengths, hashes, clocks and header counts come from the
    # GitHub Actions bot's 2026-10-10 Edogawa 1R one-off actual observation.
    # NO actual HTML, names or credentials are present in this fixture.
    items=[
        ("official_racelist",69156,
         "02a949aca1b3d93c11eb3bd909dcd2ae2a13e19699f202fc41f770df9e96e7a2",
         "2026-10-10T02:03:19.635077+00:00",False),
        ("official_beforeinfo",48264,
         "1e2c13a0aba55f00c46981af5d53a1c6454c85809a94b7f91823b2a7af533dd9",
         "2026-10-10T02:03:29.932653+00:00",True),
    ]
    return {
        "status":"READ_ONLY_DISCOVERY_COMPLETE_NOT_VERIFIED",
        "attempted_gets":2,
        "max_gets":4,
        "persistence_performed":False,
        "all_six_active_confirmed":False,
        "forward_eligible":False,
        "observations":[{
            "race_id":RACE,
            "source":kind,
            "status":"OBSERVED_CONTENT_NOT_AUTHENTICATED",
            "raw_sha256":digest,
            "raw_size_bytes":size,
            "response_completed_at":completed,
            "hints":{
                "html_parse":"LABEL_COUNTS_ONLY",
                "potential_status_labels":deepcopy(EMPTY_HEADERS),
                "structured_exhibition_complete":exhibition,
            },
            "all_six_active_confirmed":False,
            "first_observed_at":None,
            "forward_eligible":False,
        } for kind,size,digest,completed,exhibition in items],
    }


def review(report=None, **kw):
    params={
        "report": real_metadata_fixture() if report is None else report,
        "expected_race_id":RACE,
        "official_deadline_at":DEADLINE,
        "decision_cutoff_at":CUTOFF,
    }
    params.update(kw)
    return review_positive_start_evidence(**params)


class TestOfficialPositiveStartEvidenceContract(unittest.TestCase):
    def denied(self, why, report=None, **kwargs):
        result=review(report,**kwargs)
        self.assertEqual(result["reason"],why)
        self.assertFalse(result["six_active_starts_confirmed"])
        self.assertFalse(result["beforeinfo_first_write_eligible"])
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(result["positive_schema_approved"])
        self.assertFalse(result["original_first_observation_proven"])
        return result

    def test_live_metadata_finds_no_positive_in_scanned_headings_only(self):
        r=self.denied("NO_POSITIVE_HEADER_IN_SCANNED_TH_DT_ONLY")
        self.assertTrue(r["reviewed_summary_consistent"])
        self.assertFalse(r["source_bytes_independently_authenticated"])
        self.assertIn("official source-specific",r["required_next_evidence"])

    def test_positive_schema_allowlist_is_empty_not_guessable(self):
        self.assertEqual(APPROVED_POSITIVE_SOURCE_SCHEMAS,frozenset())

    def test_keyword_outside_known_html_not_proof(self):
        r=real_metadata_fixture()
        # Even all headings can contain the word 出走確定: no lane-level
        # positive source schema or frozen official body was identified.
        r["observations"][1]["hints"]["potential_status_labels"]["出走確定"]=6
        self.denied("HEADER_KEYWORD_CANDIDATE_ONLY_NOT_OFFICIAL_PROOF",r)

    def test_withdrawal_heading_not_six_active_proof(self):
        r=real_metadata_fixture()
        r["observations"][0]["hints"]["potential_status_labels"]["欠場"]=1
        self.denied("HEADER_KEYWORD_CANDIDATE_ONLY_NOT_OFFICIAL_PROOF",r)

    def test_partial_six_exhibition_is_not_positive(self):
        r=real_metadata_fixture()
        r["observations"][1]["hints"]["structured_exhibition_complete"]=False
        self.denied("EXHIBITION_NOT_COMPLETE_AND_NO_POSITIVE_HEADER",r)

    def test_missing_report_rejected(self):
        self.denied("MISSING_OBSERVATION_REPORT",{})

    def test_unfinished_or_failed_report_rejected(self):
        r=real_metadata_fixture();r["status"]="INCOMPLETE_STOPPED"
        self.denied("REPORT_SCOPE_OR_SAFETY_INVALID",r)

    def test_three_or_missing_gets_rejected(self):
        r=real_metadata_fixture();r["attempted_gets"]=3
        self.denied("REPORT_SCOPE_OR_SAFETY_INVALID",r)
        r["attempted_gets"]=1
        self.denied("REPORT_SCOPE_OR_SAFETY_INVALID",r)

    def test_any_persistence_is_not_valid_readonly_report(self):
        r=real_metadata_fixture();r["persistence_performed"]=True
        self.denied("REPORT_SCOPE_OR_SAFETY_INVALID",r)

    def test_spoofed_active_flag_cannot_promote(self):
        r=real_metadata_fixture()
        r["all_six_active_confirmed"]=True
        self.denied("REPORT_SCOPE_OR_SAFETY_INVALID",r)
        r=real_metadata_fixture()
        r["observations"][1]["all_six_active_confirmed"]=True
        self.denied("UNVERIFIED_OR_REORDERED_SOURCE_RECORD",r)

    def test_wrong_source_or_order_fails(self):
        r=real_metadata_fixture();r["observations"].reverse()
        self.denied("UNVERIFIED_OR_REORDERED_SOURCE_RECORD",r)

    def test_wrong_race_in_pilot_record_rejected(self):
        r=real_metadata_fixture();r["observations"][0]["race_id"]="20261010_03_02"
        self.denied("UNVERIFIED_OR_REORDERED_SOURCE_RECORD",r)

    def test_synthetic_wrong_race_for_review(self):
        self.denied("INVALID_RACE_ID",expected_race_id="20261010_03_99")

    def test_incorrect_report_date_rejected(self):
        r=real_metadata_fixture()
        r["observations"][0]["response_completed_at"]="2026-10-09T02:03:19+00:00"
        self.denied("OBSERVATION_ON_DIFFERENT_RACE_DAY",r)

    def test_naive_capture_time_refused(self):
        r=real_metadata_fixture()
        r["observations"][0]["response_completed_at"]="2026-10-10T11:03:19"
        self.denied("RESPONSE_COMPLETION_TIME_UNVERIFIED",r)

    def test_after_cutoff_does_not_grant_predeadline(self):
        self.denied("SOURCE_CAPTURE_NOT_AS_OF_CUTOFF",
                    decision_cutoff_at="2026-10-10T11:03:00+09:00")

    def test_cutoff_later_than_deadline_invalid(self):
        self.denied("INVALID_OFFICIAL_DEADLINE_OR_CUTOFF",
                    decision_cutoff_at="2026-10-10T11:20:00+09:00")

    def test_missing_second_source_invalid(self):
        r=real_metadata_fixture();r["observations"].pop()
        self.denied("TWO_SOURCE_RECORDS_REQUIRED",r)

    def test_bad_hash_cannot_be_source_proof(self):
        r=real_metadata_fixture();r["observations"][0]["raw_sha256"]="0"*63
        self.denied("ORIGINAL_HASH_OR_SIZE_INVALID",r)

    def test_bad_source_size_cannot_be_source_proof(self):
        r=real_metadata_fixture();r["observations"][1]["raw_size_bytes"]=0
        self.denied("ORIGINAL_HASH_OR_SIZE_INVALID",r)

    def test_missing_header_counts_denied(self):
        r=real_metadata_fixture()
        del r["observations"][1]["hints"]["potential_status_labels"]["欠場"]
        self.denied("HEADER_KEYWORD_AGGREGATES_INVALID",r)

    def test_unknown_charset_cannot_certify_headings(self):
        r=real_metadata_fixture();r["observations"][1]["hints"]["html_parse"]="UNKNOWN_CHARSET"
        self.denied("HEADER_SCAN_NOT_VERIFIABLE",r)

    def test_type_spoofed_keyword_count_rejected(self):
        r=real_metadata_fixture()
        r["observations"][0]["hints"]["potential_status_labels"]["出走確定"]=True
        self.denied("HEADER_KEYWORD_AGGREGATES_INVALID",r)

    def test_missing_exhibition_flag_denied(self):
        r=real_metadata_fixture()
        del r["observations"][1]["hints"]["structured_exhibition_complete"]
        self.denied("SIX_EXHIBITION_FIELD_MISSING",r)


if __name__=="__main__":
    unittest.main()
