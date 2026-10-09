# -*- coding: utf-8 -*-
"""Synthetic-only tests, no official fetch, DB, Railway or purchase."""
import base64
import copy
import hashlib
import unittest

from research.v5_strong_core_entry_form_freeze_plan import EvidenceNotReady
from research.v5_strong_core_entry_recent_form_predeadline_gate import FREEZE_CONTRACT
from research.v5_strong_core_official_capture_receipt_adapter import (
    prepare_from_official_capture_receipts,
)

RACE = "20261009_09_04"
DAY = "2026-10-09"
BUILT = "2026-10-09T11:50:00+09:00"
CAPTURE = "2026-10-09T11:52:00+09:00"
DEADLINE = "2026-10-09T12:00:00+09:00"
CUTOFF = "2026-10-09T11:55:00+09:00"
K_OBS = "2026-10-08T19:00:00+09:00"
SCAN_TIME = "2026-10-09T11:49:00+09:00"


def receipt(source, time_key, time_value, name, **extra):
    raw = f"synthetic-{source}-{name}".encode()
    sha = hashlib.sha256(raw).hexdigest()
    return {
        "source": source, time_key: time_value,
        "receipt_ref": "synthetic-receipt-" + name,
        "raw_base64": base64.b64encode(raw).decode("ascii"),
        "raw_sha256": sha, "readback_sha256": sha,
        "first_write_confirmed": True, "readback_confirmed": True,
        **extra,
    }


def fixtures():
    entries, scans, ks = [], [], []
    for lane in range(1, 7):
        racer = 1000 + lane
        prior = f"20261008_09_{lane:02d}"
        entries.append({
            "race_id": RACE, "lane": lane, "racer_number": racer,
            "racer_class": "A1", "active": True,
            "recent_form_complete_asof": True,
            "recent_form": [{
                "source": "official_k_file", "race_id": prior,
                "race_date": "2026-10-08", "racer_number": racer,
                "finish_position": lane,
            }],
        })
        scans.append(receipt("official_k_file", "checked_at", SCAN_TIME,
                             "scan-" + str(racer), racer_number=racer,
                             complete_asof=True, result_race_ids=[prior]))
        ks.append(receipt("official_k_file", "first_observed_at", K_OBS,
                          "k-" + prior, racer_number=racer, race_id=prior))
    return dict(
        snapshot={
            "contract": FREEZE_CONTRACT, "race_id": RACE,
            "race_date": DAY, "source": "official_beforeinfo",
            "captured_at": CAPTURE, "feature_built_at": BUILT,
            "deadline_at": DEADLINE, "entries": entries,
        },
        beforeinfo_receipt=receipt("official_beforeinfo",
                                   "first_observed_at", CAPTURE, "before"),
        racelist_receipt=receipt("official_racelist",
                                "first_observed_at",
                                "2026-10-09T11:45:00+09:00", "racelist",
                                parsed_lane_racer_ids=[[i, 1000 + i] for i in range(1, 7)]),
        history_scan_receipts=scans,
        k_result_receipts=ks,
        official_deadline_at=DEADLINE,
        prediction_cutoff_at=CUTOFF,
    )


class TestOfficialReceiptAdapter(unittest.TestCase):
    def denied(self, expected, values):
        with self.assertRaises(EvidenceNotReady) as caught:
            prepare_from_official_capture_receipts(**values)
        self.assertEqual(str(caught.exception), expected)

    def test_good_synthetic_receipts_propose_only_not_forward(self):
        data = fixtures()
        plan = prepare_from_official_capture_receipts(**data)
        self.assertEqual(plan["status"], "PREPARED_ONLY_NO_DB_WRITE")
        self.assertFalse(plan["forward_eligible"])
        self.assertIn("first OBSERVED", plan["limitations"])
        self.assertNotIn("published_at", str(data["snapshot"]))
        self.assertIn(K_OBS, plan["params"][3])

    def test_first_write_storage_attestation_required(self):
        data=fixtures();data["beforeinfo_receipt"]["first_write_confirmed"]=False
        self.denied("FIRST_WRITE_READBACK_UNPROVEN",data)

    def test_readback_digest_consistency_required(self):
        data=fixtures();data["racelist_receipt"]["readback_sha256"]="0"*64
        self.denied("SOURCE_DIGEST_OR_READBACK_MISMATCH",data)

    def test_missing_payload_cannot_invent_receipt(self):
        data=fixtures();data["beforeinfo_receipt"].pop("raw_base64")
        self.denied("SOURCE_RAW_BYTES_MISSING",data)

    def test_bad_base64_not_a_capture(self):
        data=fixtures();data["beforeinfo_receipt"]["raw_base64"]="$$$"
        self.denied("SOURCE_RAW_BYTES_INVALID",data)

    def test_mutable_realtime_snapshot_not_official_fetch_receipt(self):
        data=fixtures();data["beforeinfo_receipt"]["source"]="v2_realtime_entry_snapshots"
        self.denied("SOURCE_RECEIPT_WRONG_SOURCE",data)

    def test_k_updated_at_not_initial_observation(self):
        data=fixtures();data["k_result_receipts"][0].pop("first_observed_at")
        data["k_result_receipts"][0]["updated_at"]=K_OBS
        self.denied("SOURCE_RECEIPT_MISSING_OR_LATE_TIME",data)

    def test_no_guess_from_prior_date_if_k_source_missing(self):
        data=fixtures();data["k_result_receipts"].pop()
        self.denied("K_OBSERVATION_NOT_AVAILABLE",data)

    def test_k_result_after_feature_build_is_rejected(self):
        data=fixtures();data["k_result_receipts"][0]["first_observed_at"]="2026-10-09T11:51:00+09:00"
        self.denied("SOURCE_RECEIPT_MISSING_OR_LATE_TIME",data)

    def test_scan_without_first_write_is_rejected(self):
        data=fixtures();data["history_scan_receipts"][0]["readback_confirmed"]=False
        self.denied("FIRST_WRITE_READBACK_UNPROVEN",data)

    def test_six_racer_scans_required(self):
        data=fixtures();data["history_scan_receipts"].pop()
        self.denied("NO_COMPLETE_SCAN_RECEIPTS",data)

    def test_beforeinfo_first_observation_cannot_be_later_than_capture(self):
        data=fixtures();data["beforeinfo_receipt"]["first_observed_at"]="2026-10-09T11:53:00+09:00"
        self.denied("SOURCE_RECEIPT_MISSING_OR_LATE_TIME",data)

    def test_official_racelist_roster_must_match(self):
        data=fixtures();data["racelist_receipt"]["parsed_lane_racer_ids"][0][1]=9999
        self.denied("OFFICIAL_RACELIST_ENTRY_MISMATCH",data)

    def test_existing_publication_claim_must_match_first_observation(self):
        data=fixtures()
        data["snapshot"]["entries"][0]["recent_form"][0]["published_at"]="2026-10-08T18:00:00+09:00"
        self.denied("CONFLICTING_K_PUBLICATION_ASSERTION",data)

    def test_same_day_recent_form_is_rejected_by_existing_gate(self):
        data=fixtures();data["snapshot"]["entries"][0]["recent_form"][0]["race_date"]=DAY
        self.denied("ENTRY_GATE:NOT_STRICT_PRIOR_DAY",data)

    def test_late_capture_is_rejected_by_existing_gate(self):
        data=fixtures();data["prediction_cutoff_at"]="2026-10-09T11:51:00+09:00"
        self.denied("ENTRY_GATE:NOT_FROZEN_BEFORE_PREDICTION_CUTOFF",data)


if __name__ == "__main__":
    unittest.main()
