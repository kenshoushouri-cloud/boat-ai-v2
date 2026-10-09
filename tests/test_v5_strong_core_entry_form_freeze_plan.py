# -*- coding: utf-8 -*-
"""All-synthetic offline tests: no public site, Postgres or Railway."""
from __future__ import annotations

import copy
import json
import unittest

from research.v5_strong_core_entry_form_freeze_plan import (
    DDL, INSERT_IF_ABSENT, READ_FROZEN, EvidenceNotReady,
    prepare_entry_form_freeze, verify_frozen_readback,
)
from research.v5_strong_core_entry_recent_form_predeadline_gate import FREEZE_CONTRACT

RACE="20261009_09_04"
DAY="2026-10-09"
DEADLINE="2026-10-09T12:00:00+09:00"
CUTOFF="2026-10-09T11:55:00+09:00"
BUILT="2026-10-09T11:50:00+09:00"
CAPTURED="2026-10-09T11:52:00+09:00"
OBSERVED="2026-10-08T19:00:00+09:00"
SCAN_AT="2026-10-09T11:49:00+09:00"


def fixtures():
    rows=[]; scans=[]; results=[]
    for lane in range(1,7):
        racer=1000+lane
        result_id=f"20261008_09_{lane:02d}"
        rows.append(dict(
            race_id=RACE,lane=lane,racer_number=racer,racer_class="A1",active=True,
            recent_form_complete_asof=True,
            recent_form=[dict(
                source="official_k_file",race_id=result_id,race_date="2026-10-08",
                racer_number=racer,finish_position=lane,published_at=OBSERVED
            )]
        ))
        scans.append(dict(
            source="official_k_file",racer_number=racer,checked_at=SCAN_AT,
            receipt_ref=f"official-k-scanned-{racer}",complete_asof=True,
            result_race_ids=[result_id]
        ))
        results.append(dict(
            source="official_k_file",racer_number=racer,race_id=result_id,
            first_observed_at=OBSERVED,receipt_ref=f"official-k-seen-{result_id}"
        ))
    snap=dict(contract=FREEZE_CONTRACT,race_id=RACE,race_date=DAY,
              source="official_beforeinfo",captured_at=CAPTURED,feature_built_at=BUILT,
              deadline_at=DEADLINE,entries=rows)
    entry=dict(source="official_beforeinfo",first_observed_at=CAPTURED,
               receipt_ref="official-entry-request-proof-1")
    return dict(snapshot=snap,entry_receipt=entry,history_scan_receipts=scans,
                official_result_receipts=results,official_deadline_at=DEADLINE,
                prediction_cutoff_at=CUTOFF)


def make(**changes):
    data=fixtures()
    data.update(changes)
    return prepare_entry_form_freeze(**data)


class TestEntryFormFirstWritePlan(unittest.TestCase):
    def denied(self, expected, data):
        with self.assertRaises(EvidenceNotReady) as context:
            prepare_entry_form_freeze(**data)
        self.assertEqual(str(context.exception),expected)

    def test_frozen_six_racer_credible_receipts_make_proposal_only(self):
        plan=make()
        self.assertEqual(plan["status"],"PREPARED_ONLY_NO_DB_WRITE")
        self.assertFalse(plan["forward_eligible"])
        self.assertEqual(len(plan["digest"]),64)
        self.assertEqual(plan["race_id"],RACE)
        self.assertEqual(plan["read_params"],(RACE,))
        self.assertIn("ON CONFLICT (race_id) DO NOTHING",plan["sql"].upper() if False else plan["sql"])
        self.assertNotIn("UPDATE ",plan["sql"].upper())

    def test_storage_schema_is_own_isolated_research_table(self):
        self.assertIn("PRIMARY KEY",DDL)
        self.assertIn("research_v5_entry_form_first_write",DDL)
        self.assertIn("WHERE race_id=%s",READ_FROZEN)
        self.assertNotIn("v2_race_entries",DDL)

    def test_entry_first_observation_required(self):
        d=fixtures();d["entry_receipt"]["first_observed_at"]=None
        self.denied("MISSING_FIRST_OFFICIAL_ENTRY_OBSERVATION",d)

    def test_entry_source_and_receipt_must_exist(self):
        d=fixtures();d["entry_receipt"]["source"]="mutable_db"
        self.denied("MISSING_FIRST_OFFICIAL_ENTRY_OBSERVATION",d)
        d=fixtures();d["entry_receipt"]["receipt_ref"]=""
        self.denied("MISSING_FIRST_OFFICIAL_ENTRY_OBSERVATION",d)

    def test_entry_first_observation_must_equal_actual_capture(self):
        d=fixtures();d["entry_receipt"]["first_observed_at"]="2026-10-09T11:51:00+09:00"
        self.denied("MISSING_FIRST_OFFICIAL_ENTRY_OBSERVATION",d)

    def test_prior_history_scan_missing_or_incomplete_rejected(self):
        d=fixtures();d["history_scan_receipts"].pop()
        self.denied("MISSING_PRIOR_HISTORY_SCAN",d)
        d=fixtures();d["history_scan_receipts"][0]["complete_asof"]=False
        self.denied("UNVERIFIED_PRIOR_HISTORY_SCAN",d)

    def test_neutral_no_prior_history_only_with_empty_verified_scan(self):
        d=fixtures();d["snapshot"]["entries"][0]["recent_form"]=[]
        d["history_scan_receipts"][0]["result_race_ids"]=[]
        d["official_result_receipts"].pop(0)
        self.assertEqual(prepare_entry_form_freeze(**d)["status"],"PREPARED_ONLY_NO_DB_WRITE")
        d["history_scan_receipts"][0]["complete_asof"]=False
        self.denied("UNVERIFIED_PRIOR_HISTORY_SCAN",d)

    def test_history_manifest_must_match_exact_frozen_history_ids(self):
        d=fixtures();d["history_scan_receipts"][0]["result_race_ids"]=[]
        self.denied("HISTORY_SCAN_SET_MISMATCH",d)

    def test_official_K_observation_and_identifiable_receipt_required(self):
        d=fixtures();d["official_result_receipts"].pop()
        self.denied("PRIOR_RESULT_OBSERVATION_MISSING",d)
        d=fixtures();d["official_result_receipts"][0]["receipt_ref"]=""
        self.denied("UNVERIFIED_K_RESULT_OBSERVATION",d)

    def test_must_not_make_up_published_at_from_race_day(self):
        d=fixtures();d["snapshot"]["entries"][0]["recent_form"][0].pop("published_at")
        self.denied("UNSUPPORTED_PRIOR_PUBLICATION_TIME",d)

    def test_publication_time_must_match_observed_official_K_time(self):
        d=fixtures();d["snapshot"]["entries"][0]["recent_form"][0]["published_at"]="2026-10-08T18:00:00+09:00"
        self.denied("UNSUPPORTED_PRIOR_PUBLICATION_TIME",d)

    def test_history_scan_must_be_after_first_observed_K_result(self):
        d=fixtures();d["history_scan_receipts"][0]["checked_at"]="2026-10-08T18:59:00+09:00"
        self.denied("SCAN_PRECEDES_OFFICIAL_RESULT_OBSERVATION",d)

    def test_late_or_unzoned_prediction_evidence_rejected(self):
        d=fixtures();d["snapshot"]["captured_at"]="2026-10-09T11:56:00+09:00"
        d["entry_receipt"]["first_observed_at"]="2026-10-09T11:56:00+09:00"
        self.denied("ENTRY_GATE:NOT_FROZEN_BEFORE_PREDICTION_CUTOFF",d)
        d=fixtures();d["snapshot"]["captured_at"]="2026-10-09T11:52:00"
        self.denied("MISSING_CAPTURE_TIME",d)

    def test_no_same_day_or_future_results(self):
        d=fixtures();d["snapshot"]["entries"][0]["recent_form"][0]["race_date"]=DAY
        self.denied("ENTRY_GATE:NOT_STRICT_PRIOR_DAY",d)

    def test_readback_match_checks_original_digest_and_receipt(self):
        p=make()
        stored=dict(race_id=p["race_id"],payload=json.loads(p["params"][3]),
                    payload_sha256=p["digest"],entry_receipt_ref=p["params"][5])
        out=verify_frozen_readback(p,stored)
        self.assertTrue(out["match"])
        self.assertIn("STORAGE_DIGEST_MATCH",out["reason"])

    def test_existing_different_capture_is_not_overwritten(self):
        p=make()
        stored=dict(race_id=p["race_id"],payload=json.loads(p["params"][3]),
                    payload_sha256=p["digest"],entry_receipt_ref=p["params"][5])
        stored["payload"]["feature_built_at"]="2026-10-09T11:49:00+09:00"
        self.assertEqual(verify_frozen_readback(p,stored)["reason"],"FIRST_WRITE_CONFLICT_OR_TAMPERING")
        self.assertIn("DO NOTHING",INSERT_IF_ABSENT)

    def test_missing_or_broken_stored_payload_rejected(self):
        p=make()
        self.assertEqual(verify_frozen_readback(p,None)["reason"],"FROZEN_ROW_MISSING")
        self.assertEqual(verify_frozen_readback(p,{"payload":{"some":float("nan")}})["reason"],"INVALID_STORED_JSON")

    def test_identical_packet_has_identical_hash_and_params(self):
        a,b=make(),make()
        self.assertEqual(a["digest"],b["digest"])
        self.assertEqual(a["params"],b["params"])


if __name__=="__main__":
    unittest.main()
