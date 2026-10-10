"""Only synthetic fixtures. Never query Railway, a DB, or an official site."""
import dataclasses
import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_asof_eligibility import (
    FeatureSnapshot, RetrospectiveOutcome, REQUIRED_FEATURES,
    _witness_payload, check_offline_asof_eligibility,
)

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 10, 11, 11, 0, tzinfo=JST)
CUTOFF = DAY + timedelta(minutes=30)
RACE = "20261011_03_02"
MOCK_KEY = b"k" * 32  # fictional verification key; NOT a trusted production root
TRUST = {"independent-test-auditor": MOCK_KEY}


def valid():
    shots = []
    for name in sorted(REQUIRED_FEATURES):
        is_k = name == "prior_day_k"
        first = DAY - timedelta(days=1) if is_k else DAY
        mode = "immutable_prior_day_k" if is_k else "immutable_derived_snapshot"
        draft = FeatureSnapshot(
            feature=name, source_mode=mode, original_ref="fake-capture:" + name,
            original_sha256=hashlib.sha256(name.encode()).hexdigest(),
            source_observed_at=first,
            original_frozen_at=first + timedelta(seconds=1),
            feature_observed_at=first + timedelta(seconds=2),
            audited_at=first + timedelta(seconds=3),
            collector_id="fake-collector", auditor_id="independent-test-auditor",
            witness_hmac="",
        )
        signature = hmac.new(MOCK_KEY, _witness_payload(RACE, CUTOFF, draft), hashlib.sha256).hexdigest()
        shots.append(dataclasses.replace(draft, witness_hmac=signature))
    return shots


def resign(shots):
    return [dataclasses.replace(s, witness_hmac=hmac.new(
        MOCK_KEY, _witness_payload(RACE, CUTOFF, s), hashlib.sha256,
    ).hexdigest()) for s in shots]


class OfflineAsOfEligibilityTest(unittest.TestCase):
    def check(self, reason, shots=None, **overrides):
        args = dict(race_id=RACE, decision_cutoff_at=CUTOFF,
                    snapshots=valid() if shots is None else shots,
                    trusted_mock_audit_keys=TRUST)
        args.update(overrides)
        result = check_offline_asof_eligibility(**args)
        self.assertEqual(result.reason, reason)
        for flag in (
            "original_first_observation_verified", "independent_source_authenticated",
            "six_active_starts_confirmed", "selection_eligible",
            "beforeinfo_first_write_eligible", "forward_eligible", "buy_eligible",
        ):
            self.assertIs(getattr(result, flag), False)
        return result

    def test_synthetic_shape_pass_still_blocks_all_live_actions(self):
        r = self.check("SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED")
        self.assertTrue(r.synthetic_asof_shape_consistent)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.forward_eligible = True

    def test_period_before_july_2025_fails(self):
        self.check("INVALID_RACE_OR_CUTOFF", race_id="20250630_03_02",
                   decision_cutoff_at=datetime(2025, 6, 30, 11, 30, tzinfo=JST))

    def test_wrong_calendar_day_and_naive_cutoff_fail(self):
        self.check("INVALID_RACE_OR_CUTOFF", race_id="20260230_03_02")
        self.check("INVALID_RACE_OR_CUTOFF", decision_cutoff_at=CUTOFF.replace(tzinfo=None))

    def test_required_feature_missing_or_duplicate(self):
        s = valid()
        self.check("MISSING_OR_DUPLICATE_FEATURE", shots=s[:-1])
        self.check("MISSING_OR_DUPLICATE_FEATURE", shots=s[:-1] + [s[0]])

    def test_mutable_upsert_only_and_postrace_features_denied(self):
        for changes in (
            {"mutable_or_upsert_only": True}, {"postrace_derived": True},
            {"source_mode": "upsert_only"},
        ):
            with self.subTest(changes=changes):
                s = valid()
                s[0] = dataclasses.replace(s[0], **changes)
                self.check("MUTABLE_UNTRUSTED_OR_POSTRACE_FEATURE", shots=resign(s))

    def test_original_digest_and_source_reference_must_exist(self):
        for changes in ({"original_ref": ""}, {"original_sha256": "0"}):
            s = valid()
            s[0] = dataclasses.replace(s[0], **changes)
            self.check("ORIGINAL_LINEAGE_NOT_BOUND", shots=s)

    def test_missing_timezone_on_original_freeze_rejected(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], original_frozen_at=DAY.replace(tzinfo=None))
        self.check("UNVERIFIED_FEATURE_CLOCK", shots=s)

    def test_freeze_earlier_than_original_capture_rejected(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], original_frozen_at=s[0].source_observed_at-timedelta(seconds=1))
        self.check("INVALID_SOURCE_FREEZE_ORDER", shots=resign(s))

    def test_observed_frozen_and_audit_must_precede_cutoff(self):
        for key in ("source_observed_at", "original_frozen_at", "feature_observed_at", "audited_at"):
            with self.subTest(key=key):
                s = valid()
                # Keep monotonic clocks for a clean cutoff-only rejection.
                s[0] = dataclasses.replace(s[0], source_observed_at=CUTOFF,
                    original_frozen_at=CUTOFF, feature_observed_at=CUTOFF, audited_at=CUTOFF)
                self.check("FEATURE_NOT_FROZEN_BEFORE_CUTOFF", shots=resign(s))

    def test_prior_day_k_cannot_be_same_day(self):
        s = valid()
        i = next(i for i,x in enumerate(s) if x.feature == "prior_day_k")
        s[i] = dataclasses.replace(s[i], source_observed_at=DAY,
           original_frozen_at=DAY+timedelta(seconds=1), feature_observed_at=DAY+timedelta(seconds=2),
           audited_at=DAY+timedelta(seconds=3))
        self.check("PRIOR_DAY_K_NOT_PRIOR_DAY", shots=resign(s))

    def test_source_kind_for_k_and_non_k_bound(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], source_mode="immutable_prior_day_k")
        self.check("FEATURE_SOURCE_KIND_MISMATCH", shots=s)

    def test_same_collector_and_auditor_rejected_even_if_signed(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], collector_id="independent-test-auditor")
        self.check("NO_DISTINCT_MOCK_AUDITOR", shots=resign(s))

    def test_untrusted_signature_or_missing_anchor_rejected(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], witness_hmac="a"*64)
        self.check("INVALID_MOCK_WITNESS", shots=s)
        self.check("NO_INDEPENDENT_MOCK_AUDITOR_ANCHOR", trusted_mock_audit_keys={})

    def test_tampered_timestamp_after_witness_creation_rejected(self):
        s = valid()
        s[0] = dataclasses.replace(s[0], original_frozen_at=s[0].original_frozen_at+timedelta(seconds=1))
        self.check("INVALID_MOCK_WITNESS", shots=s)

    def test_postrace_labels_and_official_void_do_not_change_decision(self):
        label = RetrospectiveOutcome("WIN_LANE_2", False, CUTOFF+timedelta(hours=1))
        void = RetrospectiveOutcome("OFFICIAL_VOID", True, CUTOFF+timedelta(hours=1))
        for item in (label, void, None):
            with self.subTest(item=item):
                r = self.check("SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED",
                               retrospective_outcome=item)
                self.assertEqual(r.retrospective_outcome_supplied, item is not None)


if __name__ == "__main__":
    unittest.main()
