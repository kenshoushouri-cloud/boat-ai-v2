"""Pure synthetic as-of batch coverage; no SQL, official GET or real evidence."""
import dataclasses
import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from v5.offline_asof_batch_report import (
    OfflineAsOfBatchReport, SyntheticRaceCase, summarize_synthetic_asof_batch,
)
from v5.offline_asof_eligibility import (
    AsOfMockVerdict, FeatureSnapshot, REQUIRED_FEATURES, RetrospectiveOutcome,
    _witness_payload,
)

JST = timezone(timedelta(hours=9))
DAY = datetime(2026, 10, 11, 11, 0, tzinfo=JST)
CUTOFF = DAY + timedelta(minutes=30)
KEYS = {"audit-fixture": b"X" * 32}


def fixture(race_no=1, *, issue=None, outcome=None):
    race_id = f"20261011_03_{race_no:02d}"
    snapshots = []
    for feature in sorted(REQUIRED_FEATURES):
        is_k = feature == "prior_day_k"
        first = DAY - timedelta(days=1) if is_k else DAY
        data = FeatureSnapshot(
            feature=feature,
            source_mode="immutable_prior_day_k" if is_k else "immutable_derived_snapshot",
            original_ref="mock:" + feature,
            original_sha256=hashlib.sha256(feature.encode()).hexdigest(),
            source_observed_at=first,
            original_frozen_at=first + timedelta(seconds=1),
            feature_observed_at=first + timedelta(seconds=2),
            audited_at=first + timedelta(seconds=3),
            collector_id="fake-writer", auditor_id="audit-fixture", witness_hmac="",
        )
        if feature == "exhibition_rank" and issue == "late":
            data = dataclasses.replace(data,
                source_observed_at=CUTOFF, original_frozen_at=CUTOFF,
                feature_observed_at=CUTOFF, audited_at=CUTOFF)
        if feature == "exhibition_rank" and issue == "upsert":
            data = dataclasses.replace(data, mutable_or_upsert_only=True)
        sig = hmac.new(KEYS["audit-fixture"],
                       _witness_payload(race_id, CUTOFF, data), hashlib.sha256).hexdigest()
        snapshots.append(dataclasses.replace(data, witness_hmac=sig))
    if issue == "missing":
        snapshots = snapshots[:-1]
    if issue == "bad_witness":
        snapshots[0] = dataclasses.replace(snapshots[0], witness_hmac="0" * 64)
    return SyntheticRaceCase(race_id, CUTOFF, tuple(snapshots), outcome)


class TestSyntheticBatch(unittest.TestCase):
    def assert_hold(self, report):
        self.assertIs(type(report), OfflineAsOfBatchReport)
        for flag in ("independent_source_authenticated", "original_first_observation_verified",
                     "six_active_starts_confirmed", "selection_eligible",
                     "beforeinfo_first_write_eligible", "forward_eligible", "buy_eligible"):
            self.assertIs(getattr(report, flag), False)

    def test_aggregate_pass_missing_late_untrusted_upsert(self):
        races = [fixture(1), fixture(2, issue="missing"), fixture(3, issue="late"),
                 fixture(4, issue="bad_witness"), fixture(5, issue="upsert")]
        report = summarize_synthetic_asof_batch(races, trusted_mock_audit_keys=KEYS)
        self.assertEqual(report.total_races, 5)
        self.assertEqual(report.synthetic_shape_consistent_races, 1)
        self.assertEqual(dict(report.predecision_failure_reasons), {
            "FEATURE_NOT_FROZEN_BEFORE_CUTOFF": 1,
            "INVALID_MOCK_WITNESS": 1,
            "MISSING_OR_DUPLICATE_FEATURE": 1,
            "MUTABLE_UNTRUSTED_OR_POSTRACE_FEATURE": 1,
        })
        self.assert_hold(report)

    def test_retro_outcome_and_void_are_separate(self):
        label = RetrospectiveOutcome("WINNER_2", False, CUTOFF + timedelta(hours=1))
        void = RetrospectiveOutcome("VOID_CLAIM_ONLY", True, CUTOFF + timedelta(hours=2))
        report = summarize_synthetic_asof_batch([
            fixture(1, outcome=label), fixture(2, issue="late", outcome=void),
            fixture(3),
        ], trusted_mock_audit_keys=KEYS)
        self.assertEqual(report.synthetic_shape_consistent_races, 2)
        self.assertEqual(dict(report.predecision_failure_reasons),
                         {"FEATURE_NOT_FROZEN_BEFORE_CUTOFF": 1})
        self.assertEqual((report.retrospective_label_claims, report.retrospective_void_claims,
                          report.retrospective_nonvoid_claims, report.retrospective_missing),
                         (2, 1, 1, 1))
        self.assert_hold(report)

    def test_retro_claim_does_not_change_predecision_status(self):
        r = fixture(1)
        label = RetrospectiveOutcome("POSTRACE_RESULT", False, CUTOFF + timedelta(hours=1))
        a = summarize_synthetic_asof_batch([r], trusted_mock_audit_keys=KEYS)
        b = summarize_synthetic_asof_batch([dataclasses.replace(r, retrospective_outcome=label)],
                                          trusted_mock_audit_keys=KEYS)
        self.assertEqual((a.synthetic_shape_consistent_races, a.predecision_failure_reasons),
                         (b.synthetic_shape_consistent_races, b.predecision_failure_reasons))
        self.assert_hold(b)

    def test_early_or_malformed_retro_label_not_counted_as_verified(self):
        bad = RetrospectiveOutcome("VOID", True, DAY)
        a = summarize_synthetic_asof_batch([fixture(1, outcome=bad)], trusted_mock_audit_keys=KEYS)
        self.assertEqual((a.retrospective_invalid, a.retrospective_void_claims), (1, 0))
        self.assertEqual(a.synthetic_shape_consistent_races, 1)
        self.assert_hold(a)

    def test_duplicate_race_id_rejected_without_double_counting(self):
        x = fixture(1)
        report = summarize_synthetic_asof_batch([x, x], trusted_mock_audit_keys=KEYS)
        self.assertEqual(report.status, "DUPLICATE_OR_INVALID_RACE_ID")
        self.assertEqual(report.total_races, 0)
        self.assert_hold(report)

    def test_malformed_or_excess_batch_rejected(self):
        for cases in ([], [object()], "not-a-list", [fixture(1)] * 501):
            with self.subTest(kind=type(cases).__name__, size=len(cases)):
                r = summarize_synthetic_asof_batch(cases, trusted_mock_audit_keys=KEYS)
                self.assertEqual(r.status, "BATCH_INPUT_INVALID")
                self.assert_hold(r)

    def test_bad_mock_anchor_counts_untrusted_reason(self):
        report = summarize_synthetic_asof_batch([fixture(1)], trusted_mock_audit_keys={})
        self.assertEqual(dict(report.predecision_failure_reasons),
                         {"NO_INDEPENDENT_MOCK_AUDITOR_ANCHOR": 1})
        self.assert_hold(report)

    def test_checker_cannot_sneak_true_forward_flag_into_report(self):
        class MaliciousCheckerVerdict:
            reason = "SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED"
            synthetic_asof_shape_consistent = True
            independent_source_authenticated = False
            original_first_observation_verified = False
            six_active_starts_confirmed = False
            selection_eligible = False
            beforeinfo_first_write_eligible = False
            forward_eligible = True
            buy_eligible = False
        with patch("v5.offline_asof_batch_report.check_offline_asof_eligibility",
                   return_value=MaliciousCheckerVerdict()):
            report = summarize_synthetic_asof_batch([fixture(1)], trusted_mock_audit_keys=KEYS)
        self.assertEqual(dict(report.predecision_failure_reasons),
                         {"UNEXPECTED_CHECKER_AUTHORITY": 1})
        self.assertEqual(report.synthetic_shape_consistent_races, 0)
        self.assert_hold(report)

    def test_missing_cutoff_rejected_by_checker(self):
        x = dataclasses.replace(fixture(1), decision_cutoff_at=None)
        r = summarize_synthetic_asof_batch([x], trusted_mock_audit_keys=KEYS)
        self.assertEqual(dict(r.predecision_failure_reasons), {"INVALID_RACE_OR_CUTOFF": 1})
        self.assertEqual(r.retrospective_missing, 1)
        self.assert_hold(r)


if __name__ == "__main__":
    unittest.main()
