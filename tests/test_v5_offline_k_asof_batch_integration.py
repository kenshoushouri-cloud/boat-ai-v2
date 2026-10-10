"""Synthetic-only K + seven-feature + cohort joining. Never network/DB."""
import dataclasses
import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from v5.offline_asof_eligibility import (
    FeatureSnapshot, REQUIRED_FEATURES, RetrospectiveOutcome, _witness_payload,
)
from v5.offline_asof_batch_report import SyntheticRaceCase
from v5.offline_prior_day_k_receipt import OfflineKReceipt
from v5.offline_k_asof_batch_integration import (
    KBoundSyntheticRace, summarize_offline_k_asof_batch,
)

JST = timezone(timedelta(hours=9))
RACE_DAY = datetime(2026, 10, 11, 10, 0, tzinfo=JST)
CUTOFF = RACE_DAY + timedelta(hours=1, minutes=30)
K_DAY = datetime(2026, 10, 10, 8, 0, tzinfo=JST)
K_URL = 'https://www1.mbrace.or.jp/od2/K/202610/k261010.lzh'
K_BYTES = b'mock-archive-only-not-actual-source'
KEY = b'A' * 32
KEYS = {'independent-synthetic-witness': KEY}
MOCK_OK = 'SYNTHETIC_JOINT_SHAPE_HARD_HOLD'


def _sign(s, rid):
    return dataclasses.replace(s, witness_hmac=hmac.new(
        KEY, _witness_payload(rid, CUTOFF, s), hashlib.sha256).hexdigest())


def sample(i=1, *, issue=None, outcome=None):
    rid = f'20261011_03_{i:02d}'
    snapshots = []
    for feature in sorted(REQUIRED_FEATURES):
        is_k = feature == 'prior_day_k'
        t = K_DAY if is_k else RACE_DAY
        source = 'immutable_prior_day_k' if is_k else 'immutable_derived_snapshot'
        ref = 'official_k_file:261010' if is_k else 'fictional-derived:' + feature
        digest = hashlib.sha256(K_BYTES if is_k else feature.encode()).hexdigest()
        base = FeatureSnapshot(feature, source, ref, digest,
            t + timedelta(seconds=1), t + timedelta(seconds=2),
            t + timedelta(seconds=3), t + timedelta(seconds=4),
            'fictional-collector', 'independent-synthetic-witness', '')
        if feature == 'exhibition_rank' and issue == 'late':
            base = dataclasses.replace(base, source_observed_at=CUTOFF,
                original_frozen_at=CUTOFF, feature_observed_at=CUTOFF, audited_at=CUTOFF)
        if feature == 'exhibition_rank' and issue == 'upsert':
            base = dataclasses.replace(base, mutable_or_upsert_only=True)
        if is_k and issue == 'k-link-mismatch':
            base = dataclasses.replace(base, original_ref='official_k_file:261009')
        snapshots.append(_sign(base, rid))
    if issue == 'missing-seven-k':
        snapshots = [s for s in snapshots if s.feature != 'prior_day_k']
    k_snapshot = _sign(FeatureSnapshot('prior_day_k', 'immutable_prior_day_k',
        'official_k_file:261010', hashlib.sha256(K_BYTES).hexdigest(),
        K_DAY + timedelta(seconds=1), K_DAY + timedelta(seconds=2),
        K_DAY + timedelta(seconds=3), K_DAY + timedelta(seconds=4),
        'fictional-collector', 'independent-synthetic-witness', ''), rid)
    k = OfflineKReceipt(K_URL, K_BYTES, K_DAY-timedelta(seconds=2), K_DAY, k_snapshot)
    if issue == 'missing-receipt':
        k = None
    if issue == 'bad-digest':
        k = dataclasses.replace(k, original_raw_bytes=b'fake-tamper')
    if issue == 'same-day-k':
        k = dataclasses.replace(k, source_url=K_URL.replace('k261010', 'k261011'))
    return KBoundSyntheticRace(SyntheticRaceCase(rid, CUTOFF, tuple(snapshots), outcome), k)


class TestKAsOfBatchBridge(unittest.TestCase):
    def summarize(self, cases, **options):
        r = summarize_offline_k_asof_batch(cases, trusted_mock_audit_keys=options.get('keys', KEYS))
        for flag in ('original_first_observation_verified', 'independent_source_authenticated',
                     'six_active_starts_confirmed', 'selection_eligible',
                     'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(r, flag), False)
        return r

    def test_joint_mock_pass_still_holds(self):
        r = self.summarize([sample(1)])
        self.assertEqual((r.total_races, r.synthetic_k_receipt_shape_races,
                          r.synthetic_joint_shape_races), (1, 1, 1))
        self.assertEqual(r.predecision_failure_reasons, ())
        self.assertEqual(r.per_race_reason, (('20261011_03_01', MOCK_OK),))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.buy_eligible = True

    def test_missing_k_overrides_otherwise_good_asof(self):
        r = self.summarize([sample(1, issue='missing-receipt')])
        self.assertEqual(r.synthetic_joint_shape_races, 0)
        self.assertEqual(dict(r.predecision_failure_reasons), {
            'K_RECEIPT_K_RAW_RECEIPT_REQUIRED_LEGACY_CLOCKS_NOT_PROOF': 1})

    def test_digest_tamper_and_same_day_k_rejected(self):
        r = self.summarize([sample(1, issue='bad-digest'), sample(2, issue='same-day-k')])
        self.assertEqual(r.synthetic_joint_shape_races, 0)
        self.assertEqual(dict(r.predecision_failure_reasons), {
            'K_RECEIPT_K_ORIGINAL_LINEAGE_OR_DIGEST_INVALID': 1,
            'K_RECEIPT_K_NOT_FROM_PRIOR_RACE_DAY': 1})

    def test_k_snapshot_must_match_seven_feature_k(self):
        r = self.summarize([sample(1, issue='k-link-mismatch'), sample(2, issue='missing-seven-k')])
        self.assertEqual(r.synthetic_k_receipt_shape_races, 2)
        self.assertEqual(dict(r.predecision_failure_reasons), {
            'K_SNAPSHOT_LINK_MISMATCH': 1,
            'K_SNAPSHOT_LINK_MISSING_OR_DUPLICATE': 1})

    def test_other_features_fail_even_when_k_proof_shaped(self):
        r = self.summarize([sample(1, issue='late'), sample(2, issue='upsert')])
        self.assertEqual(r.synthetic_k_receipt_shape_races, 2)
        self.assertEqual(r.synthetic_joint_shape_races, 0)
        self.assertEqual(dict(r.predecision_failure_reasons), {
            'ASOF_FEATURE_NOT_FROZEN_BEFORE_CUTOFF': 1,
            'ASOF_MUTABLE_UNTRUSTED_OR_POSTRACE_FEATURE': 1})

    def test_postrace_void_labels_do_not_select_denominator(self):
        label = RetrospectiveOutcome('POSTRACE_RESULT', False, CUTOFF+timedelta(hours=2))
        void = RetrospectiveOutcome('CLAIMED_VOID', True, CUTOFF+timedelta(hours=2))
        r = self.summarize([sample(1, outcome=label),
                            sample(2, issue='missing-receipt', outcome=void),
                            sample(3)])
        self.assertEqual((r.total_races, r.synthetic_joint_shape_races), (3, 2))
        self.assertEqual((r.retrospective_label_claims, r.retrospective_void_claims,
                          r.retrospective_nonvoid_claims, r.retrospective_missing), (2, 1, 1, 1))
        self.assertEqual(r.per_race_reason[1][1],
                         'K_RECEIPT_K_RAW_RECEIPT_REQUIRED_LEGACY_CLOCKS_NOT_PROOF')

    def test_outcome_change_does_not_change_predecision_reason(self):
        x = sample(1, issue='late')
        y = dataclasses.replace(x, race=dataclasses.replace(x.race,
            retrospective_outcome=RetrospectiveOutcome('VOID', True, CUTOFF+timedelta(hours=1))))
        a, b = self.summarize([x]), self.summarize([y])
        self.assertEqual((a.per_race_reason, a.synthetic_joint_shape_races),
                         (b.per_race_reason, b.synthetic_joint_shape_races))

    def test_duplicate_invalid_and_excess_batches_fail_closed(self):
        x = sample(1)
        for cases, expected in (([x, x], 'DUPLICATE_OR_INVALID_RACE_ID'),
                                ([], 'BATCH_INPUT_INVALID'),
                                ([object()], 'BATCH_INPUT_INVALID'),
                                ([x] * 501, 'BATCH_INPUT_INVALID')):
            with self.subTest(count=len(cases)):
                r = self.summarize(cases)
                self.assertEqual(r.status, expected)
                self.assertEqual(r.total_races, 0)

    def test_missing_auditor_anchor_denies_k(self):
        r = self.summarize([sample(1)], keys={})
        self.assertEqual(dict(r.predecision_failure_reasons),
                         {'K_RECEIPT_K_MOCK_AUDITOR_ANCHOR_MISSING': 1})

    def test_rogue_k_authority_denied_even_when_claim_pass(self):
        fake = SimpleNamespace(reason='SYNTHETIC_K_SHAPE_PASS_NO_AUTHENTICATED_FIRST_OBSERVATION',
                               synthetic_k_receipt_shape_consistent=True, forward_eligible=True)
        with patch('v5.offline_k_asof_batch_integration.check_offline_prior_day_k_receipt', return_value=fake):
            r = self.summarize([sample(1)])
        self.assertEqual(dict(r.predecision_failure_reasons), {'K_UNEXPECTED_AUTHORITY': 1})

    def test_rogue_seven_feature_authority_denied(self):
        fake = SimpleNamespace(reason='SYNTHETIC_ASOF_SHAPE_MATCH_NOT_AUTHENTICATED',
                               synthetic_asof_shape_consistent=True, buy_eligible=True)
        with patch('v5.offline_k_asof_batch_integration.check_offline_asof_eligibility', return_value=fake):
            r = self.summarize([sample(1)])
        self.assertEqual(dict(r.predecision_failure_reasons), {'ASOF_UNEXPECTED_AUTHORITY': 1})


if __name__ == '__main__':
    unittest.main()
