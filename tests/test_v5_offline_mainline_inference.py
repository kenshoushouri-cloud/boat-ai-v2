"""Focused synthetic-only V5 frozen-core inference parity test; no DB/GET."""
from __future__ import annotations

import ast
import copy
import dataclasses
import math
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v5.offline_mainline_inference import (
    FROZEN_TEMPERATURE, FROZEN_WEIGHTS,
    OfflineV5InferenceInput, check_offline_v5_inference,
)

JST = timezone(timedelta(hours=9))
CUTOFF = datetime(2026, 10, 10, 12, 0, tzinfo=JST)
RID = '20261010_03_04'
FACTORS = tuple(key for key, _ in FROZEN_WEIGHTS)


def fixture():
    return OfflineV5InferenceInput(
        race_id=RID, decision_cutoff_at=CUTOFF,
        lane_racer_numbers=(1111, 2222, 3333, 4444, 5555, 6666),
        base_probabilities=(.30, .25, .15, .13, .10, .07),
        factors={name: tuple(1. + j*.02 + k*.01 for j in range(6))
                 for k, name in enumerate(FACTORS)},
    )


def research_math():
    # AST compilation is limited to the exact frozen *pure math* functions;
    # do not import research module (it imports db_pg and owns a main()).
    p = Path(__file__).resolve().parents[1] / 'research' / 'v5_strong_core_calibration_pg.py'
    tree = ast.parse(p.read_text(encoding='utf-8'))
    selected = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id in ('EPS', 'W') for t in node.targets)):
            selected.append(node)
        if isinstance(node, ast.FunctionDef) and node.name in ('weighted_probs', 'temp_probs'):
            selected.append(node)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                 str(p), 'exec'), namespace)
    return namespace


class OfflineMainlineInferenceTest(unittest.TestCase):
    def check(self, candidate=None, reason=None):
        verdict = check_offline_v5_inference(fixture() if candidate is None else candidate)
        if reason:
            self.assertEqual(verdict.reason, reason)
        for name in ('independently_authenticated_source', 'original_first_observation_verified',
                     'six_active_starts_confirmed', 'selection_eligible',
                     'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(verdict, name), False)
        return verdict

    def test_frozen_weights_and_temperature_same_as_research(self):
        m = research_math()
        self.assertEqual(dict(FROZEN_WEIGHTS), m['W'])
        self.assertEqual(FROZEN_TEMPERATURE, 1.)

    def test_six_lane_probabilities_same_as_unchanged_research(self):
        case = fixture()
        verdict = self.check(reason='SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD')
        m = research_math()
        row = {'base': list(case.base_probabilities),
               'factors': {k: list(v) for k, v in case.factors.items()}}
        expected = m['temp_probs'](m['weighted_probs'](row), m['EPS'] * 0 + 1.)
        self.assertEqual(len(verdict.lane_probabilities), 6)
        for got, want in zip(verdict.lane_probabilities, expected):
            self.assertAlmostEqual(got, want, places=14)
        self.assertAlmostEqual(sum(verdict.lane_probabilities), 1., places=14)

    def test_synthetic_no_source_does_not_authorize_purchase(self):
        verdict = self.check()
        self.assertTrue(verdict.synthetic_math_consistent)
        self.assertFalse(verdict.six_active_starts_confirmed)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            verdict.buy_eligible = True

    def test_input_scores_remain_unchanged(self):
        candidate = fixture()
        before = copy.deepcopy(candidate)
        self.check(candidate)
        self.assertEqual(candidate, before)

    def test_invalid_or_missing_race_id_fails_closed(self):
        for rid in ('', '20260230_03_04', '20261010_99_04', '20250630_03_04'):
            with self.subTest(rid=rid):
                self.check(dataclasses.replace(fixture(), race_id=rid), 'RACE_ID_OR_CUTOFF_INVALID')

    def test_wrong_day_or_naive_cutoff_fails_closed(self):
        for cutoff in (CUTOFF + timedelta(days=1), CUTOFF.replace(tzinfo=None)):
            self.check(dataclasses.replace(fixture(), decision_cutoff_at=cutoff),
                       'RACE_ID_OR_CUTOFF_INVALID')

    def test_six_distinct_racers_required_but_not_proof_of_active_starts(self):
        for racers in ((1111,) * 6, (1111, 2222),
                       (1111, 2222, 3333, 4444, 5555, True),
                       (1111, 2222, 3333, 4444, 5555, 0)):
            self.check(dataclasses.replace(fixture(), lane_racer_numbers=racers),
                       'SIX_LANE_RACER_SHAPE_INVALID')

    def test_missing_extra_feature_rejected(self):
        x = fixture()
        for factors in ({k:v for k,v in x.factors.items() if k != 'opponent'},
                        {**x.factors, 'future_extra': (1,) * 6}):
            self.check(dataclasses.replace(x, factors=factors), 'FIVE_FACTOR_SCHEMA_INVALID')

    def test_factor_nan_negative_wrong_length_rejected(self):
        x = fixture()
        for bad in ((1.,) * 5, (float('nan'),) * 6, (-1.,) * 6,
                    (float('inf'),) * 6, (1e7,) * 6):
            self.check(dataclasses.replace(x, factors={**x.factors, 'recent_form': bad}),
                       'FIVE_FACTOR_VALUES_INVALID')

    def test_invalid_base_or_not_normalized_rejected(self):
        x = fixture()
        self.check(dataclasses.replace(x, base_probabilities=(.2,)*5),
                   'BASE_SIX_PROBABILITIES_INVALID')
        self.check(dataclasses.replace(x, base_probabilities=(.2,)*6), 'BASE_NOT_NORMALIZED')
        self.check(dataclasses.replace(x, base_probabilities=(0., 0., 0., 0., 0., 1.)),
                   'SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD')

    def test_reject_forged_shape_with_no_actual_fixture(self):
        self.check({}, 'INVALID_SYNTHETIC_INPUT')

    def test_zero_factors_clamped_like_frozen_research(self):
        x = fixture()
        factors = {**x.factors, 'exhibition_rank': (0.,)*6}
        case = dataclasses.replace(x, factors=factors)
        result = self.check(case)
        m = research_math()
        row = {'base': list(case.base_probabilities), 'factors': {k: list(v) for k,v in case.factors.items()}}
        exp = m['temp_probs'](m['weighted_probs'](row), 1.)
        for a,b in zip(result.lane_probabilities, exp):
            self.assertAlmostEqual(a, b, places=14)


if __name__ == '__main__':
    unittest.main()
