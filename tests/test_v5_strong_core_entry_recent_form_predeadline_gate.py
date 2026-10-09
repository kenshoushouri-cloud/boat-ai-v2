# -*- coding: utf-8 -*-
"""Offline checks; fixtures are synthetic, NOT official forward records."""
from __future__ import annotations

import copy
import unittest

from research.v5_strong_core_entry_recent_form_predeadline_gate import (
    FREEZE_CONTRACT, check_frozen_entries_recent_form,
)

RACE = "20261009_09_04"
DAY = "2026-10-09"
DEADLINE = "2026-10-09T12:00:00+09:00"
CUTOFF = "2026-10-09T11:55:00+09:00"


def row():
    entries = []
    for lane in range(1, 7):
        racer = 1000 + lane
        entries.append({
            "race_id": RACE, "lane": lane, "racer_number": racer,
            "racer_class": "A1", "active": True, "recent_form_complete_asof": True,
            "recent_form": [{
                "source": "official_k_file", "race_id": f"20261008_09_{lane:02d}",
                "race_date": "2026-10-08", "racer_number": racer,
                "finish_position": lane,
                "published_at": "2026-10-08T19:00:00+09:00",
            }],
        })
    return {
        "contract": FREEZE_CONTRACT, "race_id": RACE,
        "race_date": DAY, "source": "official_beforeinfo",
        "captured_at": "2026-10-09T11:52:00+09:00",
        "feature_built_at": "2026-10-09T11:50:00+09:00",
        "deadline_at": DEADLINE, "entries": entries,
    }


def check(snapshot=None, **kwargs):
    params = dict(race_id=RACE, race_date=DAY,
                  frozen_snapshot=row() if snapshot is None else snapshot,
                  official_deadline_at=DEADLINE,
                  prediction_cutoff_at=CUTOFF,
                  immutable_provenance_verified=True)
    params.update(kwargs)
    return check_frozen_entries_recent_form(**params)


class TestV5EntryRecentFormForwardGate(unittest.TestCase):
    def reject(self, reason, snapshot=None, **kwargs):
        x=check(snapshot, **kwargs)
        self.assertFalse(x["eligible"], x)
        self.assertEqual(x["reason"], reason)
        self.assertEqual(x["scope"], "entries_recent_form_only")

    def test_six_active_official_entries_and_prior_day_results_pass(self):
        x=check()
        self.assertTrue(x["eligible"])
        self.assertEqual(x["scope"], "entries_recent_form_only")

    def test_no_caller_attestation_fails_closed(self):
        self.reject("IMMUTABLE_CAPTURE_NOT_ATTESTED", immutable_provenance_verified=False)

    def test_mutable_or_untrusted_contract(self):
        x=row();x["contract"]="v2_race_entries"
        self.reject("UNVERIFIED_FREEZE_CONTRACT",x)

    def test_no_frozen_snapshot_and_wrong_race(self):
        self.reject("MISSING_FROZEN_ENTRY_SNAPSHOT",{})
        x=row();x["race_id"]="20261009_09_05"
        self.reject("RACE_ID_MISMATCH",x)

    def test_unsupported_entry_source(self):
        x=row();x["source"]="historical_reconstruction"
        self.reject("UNVERIFIED_ENTRY_SOURCE",x)

    def test_race_date_must_match(self):
        self.reject("RACE_DATE_MISMATCH",race_date="2026-10-10")

    def test_missing_or_naive_timestamp(self):
        x=row();x["captured_at"]="2026-10-09T11:52:00"
        self.reject("MISSING_OR_UNZONED_TIMESTAMPS",x)

    def test_deadline_mismatch(self):
        self.reject("DEADLINE_MISMATCH",official_deadline_at="2026-10-09T12:01:00+09:00")

    def test_no_capture_after_prediction_cutoff(self):
        x=row();x["captured_at"]="2026-10-09T11:56:00+09:00"
        self.reject("NOT_FROZEN_BEFORE_PREDICTION_CUTOFF",x)
        x=row();x["feature_built_at"]="2026-10-09T11:53:00+09:00"
        x["captured_at"]="2026-10-09T11:52:00+09:00"
        self.reject("NOT_FROZEN_BEFORE_PREDICTION_CUTOFF",x)

    def test_require_exactly_six_entry_rows(self):
        x=row();x["entries"].pop()
        self.reject("NOT_SIX_ENTRY_ROWS",x)

    def test_missing_or_duplicate_lane_or_racer(self):
        x=row();x["entries"][0]["lane"]=7
        self.reject("INVALID_LANE",x)
        x=row();x["entries"][0]["racer_number"]=0
        self.reject("INVALID_RACER",x)
        x=row();x["entries"][1]["racer_number"]=1001
        self.reject("DUPLICATE_LANE_OR_RACER",x)

    def test_frozen_entry_must_match_race(self):
        x=row();x["entries"][0]["race_id"]="other"
        self.reject("ENTRY_RACE_MISMATCH",x)

    def test_all_six_active_and_classified(self):
        x=row();x["entries"][3]["active"]=None
        self.reject("ACTIVE_STATUS_NOT_VERIFIED",x)
        x=row();x["entries"][3]["racer_class"]=""
        self.reject("MISSING_RACER_CLASS",x)

    def test_recent_form_requires_complete_asof_proof(self):
        x=row();x["entries"][0]["recent_form_complete_asof"]=False
        self.reject("RECENT_FORM_ASOF_NOT_ATTESTED",x)
        x=row();x["entries"][0]["recent_form"]=None
        self.reject("INVALID_RECENT_FORM",x)

    def test_zero_prior_races_allowed_only_if_verified_complete(self):
        x=row();x["entries"][0]["recent_form"]=[]
        self.assertTrue(check(x)["eligible"])
        x["entries"][0]["recent_form_complete_asof"]=False
        self.reject("RECENT_FORM_ASOF_NOT_ATTESTED",x)

    def test_future_and_same_day_results_rejected(self):
        x=row();x["entries"][0]["recent_form"][0]["race_date"]=DAY
        self.reject("NOT_STRICT_PRIOR_DAY",x)
        x=row();x["entries"][0]["recent_form"][0]["race_date"]="2026-10-10"
        self.reject("NOT_STRICT_PRIOR_DAY",x)

    def test_prior_result_publication_must_precede_feature_build(self):
        x=row();x["entries"][0]["recent_form"][0]["published_at"]="2026-10-09T11:51:00+09:00"
        self.reject("PRIOR_RESULT_NOT_PUBLISHED_ASOF_BUILD",x)
        x=row();x["entries"][0]["recent_form"][0]["published_at"]=None
        self.reject("PRIOR_RESULT_NOT_PUBLISHED_ASOF_BUILD",x)

    def test_prior_item_source_identity_and_finish(self):
        x=row();x["entries"][0]["recent_form"][0]["source"]="unverified"
        self.reject("UNVERIFIED_PRIOR_SOURCE",x)
        x=row();x["entries"][0]["recent_form"][0]["racer_number"]=1002
        self.reject("PRIOR_RACER_MISMATCH",x)
        x=row();x["entries"][0]["recent_form"][0]["finish_position"]=0
        self.reject("INVALID_PRIOR_FINISH",x)

    def test_duplicate_previous_race_rejected(self):
        x=row();prev=copy.deepcopy(x["entries"][0]["recent_form"][0])
        x["entries"][0]["recent_form"].append(prev)
        self.reject("MISSING_OR_DUPLICATE_PRIOR_RACE",x)

    def test_more_than_five_history_items_rejected(self):
        x=row();x["entries"][0]["recent_form"]*=6
        self.reject("INVALID_RECENT_FORM",x)


if __name__ == "__main__":
    unittest.main()
