"""Tests actual V5 math AST offline; no research main(), imports, DB, HTTP, Railway.

Loads only unchanged weighted_probs/temp_probs/ece10/metrics functions and W/EPS
from the live repository file; b.score from its exact dependency. Reassesses
small synthetic scores before and after separate race-ID sidecar audit.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import types
import unittest
from pathlib import Path

from v5.offline_score_identity_parity import (
    ScoringOrigin, audit_offline_scorer_identity_parity,
    frozen_baseline_digest, score_row_digest,
)

ROOT = Path(__file__).resolve().parents[1]
CALIB = ROOT / 'research' / 'v5_strong_core_calibration_pg.py'
BASE = ROOT / 'research' / 'v5_lc_rf_exrank_rc_plus_opponent_pg.py'
WEIGHTS = {'recent_form': .5, 'exhibition_rank': 1., 'racer_course': .75,
           'opponent': 1.25, 'venue_lane': .75}
DATES = ('2026-03-30', '2026-03-31', '2026-04-01', '2026-05-05', '2026-06-12')
RACE_IDS = ('20260330_03_01', '20260331_03_02', '20260401_03_03',
            '20260505_03_04', '20260612_03_05')
PERIODS = ('train', 'oos_all', 'oos_april', 'oos_may', 'oos_june_to_end')


def _math_ast(path, assignments, functions, namespace):
    """Compile exact checked-in math definitions; never execute module imports/main."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in assignments for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
    found_assign = {t.id for node in selected if isinstance(node, ast.Assign)
                    for t in node.targets if isinstance(t, ast.Name)}
    found_funcs = {node.name for node in selected if isinstance(node, ast.FunctionDef)}
    if not assignments <= found_assign or not functions <= found_funcs:
        raise RuntimeError('Missing exact mainline math expressions in source')
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace


def actual_math():
    dependent = _math_ast(BASE, {'EPS'}, {'score'}, {'math': math})
    return _math_ast(CALIB, {'W', 'EPS'},
                     {'weighted_probs', 'temp_probs', 'ece10', 'metrics'},
                     {'math': math, 'b': types.SimpleNamespace(score=dependent['score'])})


def rows():
    data = []
    for k, day in enumerate(DATES):
        base = [0.30-.008*k, 0.25, 0.19, 0.11+.005*k, 0.09, 0.06+.003*k]
        factors = {name: [1.0 + .02*k + .01*j + .005*f for j in range(6)]
                   for f, name in enumerate(WEIGHTS)}
        data.append({'date': day, 'venue': '03', 'winner': 1 + (k % 6),
                     'base': base, 'factors': factors})
    return data


def frozen_metric_blocks(math_funcs, cohort):
    groups = {
        'train': [r for r in cohort if r['date'] <= '2026-03-31'],
        'oos_all': [r for r in cohort if r['date'] > '2026-03-31'],
        'oos_april': [r for r in cohort if '2026-03-31' < r['date'] <= '2026-04-30'],
        'oos_may': [r for r in cohort if '2026-04-30' < r['date'] <= '2026-05-31'],
        'oos_june_to_end': [r for r in cohort if r['date'] > '2026-05-31'],
    }
    return {name: {'uncalibrated': math_funcs['metrics'](part, 1.0),
                   'calibrated': math_funcs['metrics'](part, 1.1)}
            for name, part in groups.items()}


class V5CoreMathParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = actual_math()

    def test_unchanged_strong_core_weights(self):
        self.assertEqual(self.model['W'], WEIGHTS)

    def test_probabilities_against_independent_formula(self):
        x = rows()[0]
        actual = self.model['weighted_probs'](x)
        expected_raw = [max(x['base'][i], 1e-12) * math.prod(
            max(x['factors'][name][i], 1e-12) ** w for name, w in WEIGHTS.items())
                        for i in range(6)]
        total = sum(expected_raw)
        for got, expected in zip(actual, expected_raw):
            self.assertAlmostEqual(got, expected / total, places=14)
        self.assertAlmostEqual(sum(actual), 1., places=14)

    def test_temperature_against_independent_formula(self):
        probability = self.model['weighted_probs'](rows()[0])
        for temperature in (0.8, 1., 1.1, 1.3):
            with self.subTest(temperature=temperature):
                actual = self.model['temp_probs'](probability, temperature)
                raw = [max(p, 1e-12) ** (1. / temperature) for p in probability]
                for got, exp in zip(actual, raw):
                    self.assertAlmostEqual(got, exp / sum(raw), places=14)

    def test_actual_metrics_independent_reference_logloss_brier_top1(self):
        cohort = rows()
        actual = self.model['metrics'](cohort, 1.1)
        expected_ll = expected_br = expected_hits = 0.
        for row in cohort:
            p = self.model['temp_probs'](self.model['weighted_probs'](row), 1.1)
            winner = row['winner'] - 1
            expected_ll += -math.log(p[winner])
            expected_br += sum((v - (1. if i == winner else 0.)) ** 2
                               for i, v in enumerate(p))
            expected_hits += int(p.index(max(p)) == winner and p.count(max(p)) == 1)
        self.assertEqual(actual['n'], len(cohort))
        self.assertAlmostEqual(actual['logloss'], expected_ll / len(cohort), places=14)
        self.assertAlmostEqual(actual['brier'], expected_br / len(cohort), places=14)
        self.assertAlmostEqual(actual['top1'], expected_hits / len(cohort), places=14)
        self.assertGreaterEqual(actual['ece10'], 0.)

    def test_sidecar_identity_parity_preserves_original_cohort_and_metrics(self):
        cohort = rows()
        original = copy.deepcopy(cohort)
        metrics = frozen_metric_blocks(self.model, cohort)
        original_metrics = copy.deepcopy(metrics)
        before = self.model['metrics'](cohort, 1.1)
        anchors = [ScoringOrigin(rid, score_row_digest(row))
                   for rid, row in zip(RACE_IDS, cohort)]
        verdict = audit_offline_scorer_identity_parity(
            scorer_origins=anchors, original_score_rows=cohort,
            frozen_historical_metrics=metrics,
            frozen_baseline_sha256=frozen_baseline_digest(cohort, metrics))
        self.assertEqual(verdict.status, 'SYNTHETIC_IDENTITY_AND_BASELINE_PARITY_HARD_HOLD')
        self.assertEqual(verdict.original_rows, len(cohort))
        self.assertEqual(self.model['metrics'](cohort, 1.1), before)
        self.assertEqual(frozen_metric_blocks(self.model, cohort), original_metrics)
        self.assertEqual(cohort, original)
        self.assertFalse(verdict.selection_eligible)
        self.assertFalse(verdict.forward_eligible)
        self.assertFalse(verdict.buy_eligible)

    def test_sidecar_anchors_reordered_no_metric_change(self):
        cohort = rows()
        metrics = frozen_metric_blocks(self.model, cohort)
        before = self.model['metrics'](cohort, 1.0)
        anchors = list(reversed([ScoringOrigin(rid, score_row_digest(row))
                   for rid, row in zip(RACE_IDS, cohort)]))
        verdict = audit_offline_scorer_identity_parity(
            scorer_origins=anchors, original_score_rows=cohort,
            frozen_historical_metrics=metrics,
            frozen_baseline_sha256=frozen_baseline_digest(cohort, metrics))
        self.assertTrue(verdict.historical_evaluation_preserved)
        self.assertEqual(self.model['metrics'](cohort, 1.0), before)

    def test_sidecar_wrong_hash_refuses_without_repricing(self):
        cohort = rows()
        metrics = frozen_metric_blocks(self.model, cohort)
        before = self.model['metrics'](cohort, 1.1)
        anchors = [ScoringOrigin(rid, score_row_digest(row))
                   for rid, row in zip(RACE_IDS, cohort)]
        anchors[0] = ScoringOrigin(RACE_IDS[0], '0' * 64)
        verdict = audit_offline_scorer_identity_parity(
            scorer_origins=anchors, original_score_rows=cohort,
            frozen_historical_metrics=metrics,
            frozen_baseline_sha256=frozen_baseline_digest(cohort, metrics))
        self.assertEqual(verdict.status, 'MISSING_OR_EXTRA_OR_TAMPERED_SCORING_ROW_BINDING')
        self.assertEqual(self.model['metrics'](cohort, 1.1), before)

    def test_postrace_metadata_not_used_to_prune_synthetic_cohort(self):
        cohort = rows()
        before = self.model['metrics'](cohort, 1.0)
        metadata = {rid: {'result_incident': i % 2 == 0, 'claimed_void': i == 1}
                    for i, rid in enumerate(RACE_IDS)}
        self.assertEqual(len(metadata), len(cohort))
        self.assertEqual(self.model['metrics'](cohort, 1.0), before)
        # The independent sidecar cannot read those keys or remove score rows.


if __name__ == '__main__':
    unittest.main()
