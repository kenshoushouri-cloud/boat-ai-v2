"""Synthetic-only parity tests; no production runner, DB, network or BUY."""
from __future__ import annotations

import copy
import dataclasses
import unittest

from v5.offline_score_identity_parity import (
    ScoringOrigin, audit_offline_scorer_identity_parity,
    frozen_baseline_digest, score_row_digest, PERIODS,
)

DATES = ('2026-03-31', '2026-04-15', '2026-05-16', '2026-06-17')
IDS = ('20260331_03_01', '20260415_03_02', '20260516_03_03', '20260617_03_04')
FACTORS = ('recent_form', 'exhibition_rank', 'racer_course', 'opponent', 'venue_lane')


def originals():
    return [{'date': day, 'venue': '03', 'winner': i % 6 + 1,
             'base': [round(0.1 + i * .01 + j * .01, 4) for j in range(6)],
             'factors': {factor: [1.0 + i*.01 + j*.001 for j in range(6)]
                         for factor in FACTORS}}
            for i, day in enumerate(DATES)]


def metrics(rows):
    dates = [row['date'] for row in rows]
    counts = {
        'train': sum(day <= '2026-03-31' for day in dates),
        'oos_all': sum(day > '2026-03-31' for day in dates),
        'oos_april': sum('2026-03-31' < day <= '2026-04-30' for day in dates),
        'oos_may': sum('2026-04-30' < day <= '2026-05-31' for day in dates),
        'oos_june_to_end': sum(day > '2026-05-31' for day in dates),
    }
    # Fixture values stand in for frozen historical output; no scoring here.
    return {period: {'uncalibrated': {'n': n, 'logloss': .95, 'brier': .57, 'top1': .50},
                     'calibrated': {'n': n, 'logloss': .90, 'brier': .54, 'top1': .55}}
            for period, n in counts.items()}


def fixture():
    rows = originals()
    block = metrics(rows)
    anchors = [ScoringOrigin(rid, score_row_digest(row))
               for rid, row in zip(IDS, rows)]
    return dict(scorer_origins=anchors, original_score_rows=rows,
                frozen_historical_metrics=block,
                frozen_baseline_sha256=frozen_baseline_digest(rows, block))


class ScoreIdentityParityTest(unittest.TestCase):
    def verdict(self, kwargs=None, expected=None):
        v = audit_offline_scorer_identity_parity(**(fixture() if kwargs is None else kwargs))
        if expected is not None:
            self.assertEqual(v.status, expected)
        for field in ('postrace_pruning_performed', 'original_first_observation_verified',
                      'six_active_starts_confirmed', 'selection_eligible',
                      'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(v, field), False)
        return v

    def test_exact_race_id_hash_join_and_counts(self):
        v = self.verdict(expected='SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        self.assertEqual((v.original_rows, v.train_rows, v.oos_rows), (4, 1, 3))
        self.assertEqual(len(v.race_id_row_sha256), 4)
        self.assertTrue(v.historical_evaluation_preserved)

    def test_reversed_scorer_origins_order_does_not_change_join(self):
        f = fixture()
        f['scorer_origins'] = list(reversed(f['scorer_origins']))
        result = self.verdict(f, 'SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        self.assertEqual([x[0] for x in result.race_id_row_sha256], sorted(IDS))

    def test_original_scores_and_historic_metrics_unchanged(self):
        f = fixture()
        before = copy.deepcopy(f)
        result = self.verdict(f, 'SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        self.assertEqual(f, before)
        self.assertEqual(result.original_baseline_sha256, before['frozen_baseline_sha256'])
        self.assertNotIn('logloss', repr(result))
        self.assertNotIn('winner', repr(result))

    def test_postrace_winner_zero_not_pruned(self):
        f = fixture()
        f['original_score_rows'][1]['winner'] = 0  # fake unresolved/VOID outcome
        f['scorer_origins'][1] = ScoringOrigin(IDS[1], score_row_digest(f['original_score_rows'][1]))
        f['frozen_baseline_sha256'] = frozen_baseline_digest(f['original_score_rows'], f['frozen_historical_metrics'])
        v = self.verdict(f, 'SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        self.assertEqual((v.original_rows, v.train_rows, v.oos_rows), (4, 1, 3))

    def test_changed_score_value_detected_by_baseline_digest(self):
        f = fixture()
        f['original_score_rows'][1]['base'][0] = .9999
        self.verdict(f, 'HISTORICAL_BASELINE_DIGEST_CHANGED')

    def test_changed_historic_oos_metric_detected(self):
        f = fixture()
        f['frozen_historical_metrics']['oos_all']['calibrated']['logloss'] = .99
        self.verdict(f, 'HISTORICAL_BASELINE_DIGEST_CHANGED')

    def test_count_mismatch_even_if_new_digest_forged(self):
        f = fixture()
        f['frozen_historical_metrics']['oos_all']['calibrated']['n'] = 2
        f['frozen_baseline_sha256'] = frozen_baseline_digest(f['original_score_rows'], f['frozen_historical_metrics'])
        self.verdict(f, 'HISTORICAL_SCORING_COHORT_COUNT_CHANGED')

    def test_no_source_id_or_invalid_date_refused(self):
        f = fixture()
        f['scorer_origins'][0] = ScoringOrigin('', f['scorer_origins'][0].frozen_score_row_sha256)
        self.verdict(f, 'INVALID_OR_MISSING_SCORER_RACE_ID')
        f = fixture()
        f['scorer_origins'][0] = ScoringOrigin('20260230_03_01', f['scorer_origins'][0].frozen_score_row_sha256)
        self.verdict(f, 'INVALID_OR_MISSING_SCORER_RACE_ID')

    def test_wrong_date_bound_to_score_hash_denied(self):
        f = fixture()
        f['scorer_origins'][0] = ScoringOrigin('20260330_03_01', f['scorer_origins'][0].frozen_score_row_sha256)
        self.verdict(f, 'SCORER_RACE_ID_DATE_MISMATCH')

    def test_duplicate_race_id_denied(self):
        f = fixture()
        f['scorer_origins'][1] = ScoringOrigin(IDS[0], f['scorer_origins'][1].frozen_score_row_sha256)
        self.verdict(f, 'DUPLICATE_SCORER_RACE_ID')

    def test_extra_or_tampered_source_hash_denied(self):
        f = fixture()
        f['scorer_origins'][2] = ScoringOrigin(IDS[2], 'a'*64)
        self.verdict(f, 'MISSING_OR_EXTRA_OR_TAMPERED_SCORING_ROW_BINDING')

    def test_ambiguous_equal_scores_fail_not_position_join(self):
        f = fixture()
        f['original_score_rows'][1] = copy.deepcopy(f['original_score_rows'][0])
        f['scorer_origins'][1] = ScoringOrigin(IDS[1], f['scorer_origins'][0].frozen_score_row_sha256)
        f['frozen_baseline_sha256'] = frozen_baseline_digest(f['original_score_rows'], f['frozen_historical_metrics'])
        self.verdict(f, 'AMBIGUOUS_IDENTICAL_SCORE_ROWS')

    def test_no_source_row_or_excess_rejected(self):
        f = fixture()
        f['scorer_origins'] = f['scorer_origins'][:-1]
        self.verdict(f, 'SCORER_ORIGIN_COUNT_OR_TYPE_MISMATCH')
        f = fixture()
        f['original_score_rows'] = []
        self.verdict(f, 'INVALID_OR_EMPTY_ORIGINAL_SCORING_ROWS')

    def test_nonfinite_score_rejected(self):
        f = fixture()
        f['original_score_rows'][0]['base'][0] = float('nan')
        self.verdict(f, 'INVALID_OR_NONFINITE_BASELINE_PAYLOAD')

    def test_immutable_report_and_no_unapproved_gates(self):
        v = self.verdict(expected='SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.forward_eligible = True
        self.assertIsInstance(v.race_id_row_sha256, tuple)


if __name__ == '__main__':
    unittest.main()
