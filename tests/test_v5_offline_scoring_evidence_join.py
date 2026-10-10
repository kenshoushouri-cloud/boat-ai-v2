"""Fake-only exact-ID V5 evidence overlay regression. No actual DB/GET/BUY."""
from __future__ import annotations

import dataclasses
import unittest
from copy import deepcopy
from types import MappingProxyType

from v5.offline_k_asof_batch_integration import KAsOfCoverageReport
from v5.offline_scoring_evidence_join import (
    SyntheticScoredRace, audit_offline_scoring_evidence,
    MOCK_JOINT_SHAPE,
)

R1 = '20261010_03_01'
R2 = '20261010_03_02'
R3 = '20261010_03_03'
FAIL = 'K_RECEIPT_K_ORIGINAL_LINEAGE_OR_DIGEST_INVALID'


def scores():
    return [SyntheticScoredRace(R1, {'date': '2026-10-10', 'venue': '03',
                                     'base': [0.7, 0.3], 'winner': 1}),
            SyntheticScoredRace(R2, {'date': '2026-10-10', 'venue': '03',
                                     'base': [0.2, 0.8], 'winner': 2})]


def evidence(pairs=None, **updates):
    pairs = ((R2, FAIL), (R1, MOCK_JOINT_SHAPE)) if pairs is None else tuple(pairs)
    failures = tuple(sorted(__import__('collections').Counter(
        reason for _, reason in pairs if reason != MOCK_JOINT_SHAPE).items()))
    shape = sum(reason == MOCK_JOINT_SHAPE for _, reason in pairs)
    options = dict(
        status='OFFLINE_K_ASOF_SYNTHETIC_COUNTS_ALL_HARD_HOLD',
        total_races=len(pairs), synthetic_joint_shape_races=shape,
        synthetic_k_receipt_shape_races=shape,
        per_race_reason=pairs, predecision_failure_reasons=failures,
    )
    options.update(updates)
    return KAsOfCoverageReport(**options)


class TestOfflineScoringEvidenceJoin(unittest.TestCase):
    def review(self, score_rows=None, report=None, expected=None):
        actual = audit_offline_scoring_evidence(
            scores() if score_rows is None else score_rows,
            evidence() if report is None else report,
        )
        if expected is not None:
            self.assertEqual(actual.status, expected)
        for name in ('source_authenticated', 'original_first_observation_verified',
                     'six_active_starts_confirmed', 'selection_eligible',
                     'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(actual, name), False)
        return actual

    def test_exact_join_reordered_evidence_is_not_positional(self):
        x = self.review(expected='SYNTHETIC_SCORING_RACE_ID_AUDIT_NO_LIVE_ELIGIBILITY')
        self.assertEqual(x.joined_race_reasons, ((R1, MOCK_JOINT_SHAPE), (R2, FAIL)))
        self.assertEqual((x.evaluated_races, x.mock_joint_shape_races, x.denied_races), (2, 1, 1))

    def test_score_payload_not_changed_and_not_in_report(self):
        original = scores()
        before = deepcopy(original)
        out = self.review(score_rows=original)
        self.assertEqual(original, before)
        self.assertNotIn('winner', repr(out))
        self.assertNotIn('base', repr(out))

    def test_reject_missing_or_extra_evidence_ids_even_when_venue_same(self):
        report = evidence(((R3, MOCK_JOINT_SHAPE), (R2, FAIL)))
        self.review(report=report, expected='MISSING_OR_EXTRA_EVIDENCE_RACE_ID')

    def test_duplicate_score_id_denied(self):
        self.review(score_rows=[scores()[0], scores()[0]], expected='DUPLICATE_SCORE_RACE_ID')

    def test_duplicate_evidence_id_denied(self):
        report = evidence(((R1, MOCK_JOINT_SHAPE), (R1, FAIL)))
        self.review(report=report, expected='DUPLICATE_EVIDENCE_RACE_ID')

    def test_missing_score_id_and_wrong_score_shape_denied(self):
        self.review(score_rows=[{'date': '2026-10-10'}],
                    expected='INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')
        self.review(score_rows=[SyntheticScoredRace('', {'date': '2026-10-10'})],
                    expected='INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')
        self.review(score_rows=[SyntheticScoredRace('20260230_03_02', {'x': 1})],
                    expected='INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')

    def test_wrong_or_zero_report_denied(self):
        self.review(report=object(), expected='INVALID_OR_UNTRUSTED_EVIDENCE_REPORT')
        self.review(report=evidence(total_races=0), expected='INVALID_OR_UNTRUSTED_EVIDENCE_REPORT')

    def test_empty_and_oversize_scores_denied(self):
        self.review(score_rows=[], expected='INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')
        self.review(score_rows=[SyntheticScoredRace(R1, {'x': 1})] * 501,
                    expected='INVALID_EXPLICITLY_KEYED_SCORE_FIXTURES')

    def test_invalid_evidence_race_id_or_reason_denied(self):
        self.review(report=evidence((('20260230_03_01', MOCK_JOINT_SHAPE), (R2, FAIL))),
                    expected='INVALID_EVIDENCE_RACE_REASON_PAIRS')
        self.review(report=evidence(((R1, 'PROMOTE_LIVE'), (R2, FAIL))),
                    expected='INVALID_EVIDENCE_RACE_REASON_PAIRS')
        self.review(report=evidence(((R1, 'ASOF_BOGUS_APPROVE'), (R2, FAIL))),
                    expected='INVALID_EVIDENCE_RACE_REASON_PAIRS')

    def test_claimed_positive_permission_denied(self):
        class FakePositive:
            status = 'OFFLINE_K_ASOF_SYNTHETIC_COUNTS_ALL_HARD_HOLD'
            forward_eligible = True
        self.review(report=FakePositive(), expected='INVALID_OR_UNTRUSTED_EVIDENCE_REPORT')

    def test_falsified_aggregate_denied(self):
        self.review(report=evidence(synthetic_joint_shape_races=2),
                    expected='EVIDENCE_AGGREGATES_INCONSISTENT')
        self.review(report=evidence(predecision_failure_reasons=()),
                    expected='EVIDENCE_AGGREGATES_INCONSISTENT')

    def test_no_shape_never_becomes_selection_eligible(self):
        r = evidence(((R1, FAIL), (R2, FAIL)), synthetic_k_receipt_shape_races=0)
        x = self.review(report=r, expected='SYNTHETIC_SCORING_RACE_ID_AUDIT_NO_LIVE_ELIGIBILITY')
        self.assertEqual((x.evaluated_races, x.mock_joint_shape_races, x.denied_races), (2, 0, 2))

    def test_all_shape_still_holds(self):
        r = evidence(((R1, MOCK_JOINT_SHAPE), (R2, MOCK_JOINT_SHAPE)))
        x = self.review(report=r, expected='SYNTHETIC_SCORING_RACE_ID_AUDIT_NO_LIVE_ELIGIBILITY')
        self.assertEqual(x.mock_joint_shape_races, 2)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            x.forward_eligible = True

    def test_immutable_payload_mapping_accepted_without_rewriting(self):
        score_rows = [SyntheticScoredRace(R1, MappingProxyType({'x': 1})),
                      SyntheticScoredRace(R2, MappingProxyType({'x': 2}))]
        x = self.review(score_rows=score_rows)
        self.assertEqual(x.joined_race_reasons[0], (R1, MOCK_JOINT_SHAPE))


if __name__ == '__main__':
    unittest.main()
