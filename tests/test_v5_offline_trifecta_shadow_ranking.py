"""Fake-only V5-to-120-trifecta mathematical parity, no actual odds/BUY."""
from __future__ import annotations
import dataclasses
import inspect
import math
import unittest
from itertools import permutations

from research.candidate_discovery_v4_contract import pl_trifecta
from v5.offline_mainline_inference import OfflineV5InferenceVerdict
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas

REASON = 'SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD'
PASS = 'SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD'
RID = '20261010_03_04'
VECTORS = (
    (.30,.25,.15,.13,.10,.07),
    (1/6,)*6,
    (.45,.12,.16,.09,.10,.08),
)

def prediction(p=VECTORS[0], rid=RID):
    return OfflineV5InferenceVerdict(REASON, rid, tuple(p), True)

class ShadowRankingTests(unittest.TestCase):
    def checked(self, source=None, n=3, reason=PASS):
        verdict = rank_offline_v5_trifectas(prediction() if source is None else source, ticket_count=n)
        self.assertEqual(verdict.reason, reason)
        for flag in ('original_first_observation_verified','independently_authenticated_source',
                     'six_active_starts_confirmed','selection_eligible',
                     'beforeinfo_first_write_eligible','forward_eligible','buy_eligible'):
            self.assertIs(getattr(verdict, flag), False)
        self.assertIs(verdict.second_third_pl_assumption_unvalidated, True)
        return verdict

    def test_120_unique_distinct_lane_permutations_and_sum_one(self):
        v=self.checked()
        self.assertEqual(len(v.ticket_distribution), 120)
        self.assertEqual(len({t for t,p in v.ticket_distribution}), 120)
        self.assertEqual(set(t for t,p in v.ticket_distribution),
                         {'-'.join(map(str,x)) for x in permutations(range(1,7),3)})
        self.assertAlmostEqual(math.fsum(p for _,p in v.ticket_distribution),1.,places=12)
        self.assertTrue(all(p>0 for _,p in v.ticket_distribution))

    def test_various_explicit_ticket_counts_and_no_v4_default(self):
        for n in (1,2,3,6,120):
            with self.subTest(n=n):
                v=self.checked(n=n)
                self.assertEqual(v.requested_ticket_count,n)
                self.assertEqual(len(v.top_tickets),n)
        with self.assertRaises(TypeError): rank_offline_v5_trifectas(prediction())
        self.assertEqual(tuple(inspect.signature(rank_offline_v5_trifectas).parameters),
                         ('inference','ticket_count'))

    def test_invalid_ticket_count_fails_closed(self):
        for n in (0,-1,121,True,2.,'2',None):
            with self.subTest(n=n):
                v=self.checked(n=n,reason='EXPLICIT_TICKET_COUNT_REQUIRED')
                self.assertEqual(v.top_tickets,())

    def test_exact_source_race_id_preserved(self):
        v=self.checked(source=prediction(rid='20261010_21_12'))
        self.assertEqual(v.race_id,'20261010_21_12')

    def test_invalid_race_dates_and_ids_denied(self):
        for rid in ('','20260230_03_04','20250700_03_04','20260610_44_01','20250630_03_04'):
            self.checked(source=prediction(rid=rid),reason='INVALID_SOURCE_RACE_ID')

    def test_wrong_or_forged_inference_denied(self):
        for v in (object(), {}, OfflineV5InferenceVerdict('FAKE_ALLOW',RID,VECTORS[0],True),
                  OfflineV5InferenceVerdict(REASON,RID,VECTORS[0],False)):
            self.checked(source=v, reason='UNTRUSTED_OR_UNAUTHORIZED_V5_INFERENCE')

    def test_positive_authority_claim_does_not_upgrade_mock(self):
        x=prediction()
        object.__setattr__(x,'buy_eligible',True)
        self.checked(source=x,reason='UNTRUSTED_OR_UNAUTHORIZED_V5_INFERENCE')

    def test_nan_negative_zero_one_boolean_and_bad_norm_denied(self):
        invalid = ([.3,.25,.15,.13,.1,.07],(.5,.5),(.3,.25,.15,.13,.1,0.),
                   (1.,0.,0.,0.,0.,0.),(.3,.25,.15,.13,.1,float('nan')),
                   (.3,.25,.15,.13,.1,float('inf')),
                   (.3,.25,.15,.13,.1,True),(.2,)*6,(-.01,.26,.25,.20,.20,.10))
        for p in invalid:
            with self.subTest(p=p):
                self.checked(source=dataclasses.replace(prediction(), lane_probabilities=p),reason='INVALID_SIX_LANE_PROBABILITY_VECTOR')

    def test_v4_pl_mathematical_parity_multiple_synthetic_vectors(self):
        for p in VECTORS:
            with self.subTest(p=p):
                ours=self.checked(source=prediction(p),n=120)
                expected=pl_trifecta({i+1:v for i,v in enumerate(p)})
                self.assertEqual(len(expected),120)
                for ticket, probability in ours.ticket_distribution:
                    self.assertAlmostEqual(probability,expected[ticket],places=13)

    def test_uniform_probability_ties_sorted_by_ticket_lexically(self):
        v=self.checked(source=prediction(VECTORS[1]),n=5)
        self.assertEqual([t for t,p in v.top_tickets],
                         sorted(t for t,p in v.ticket_distribution)[:5])

    def test_ranked_top_has_monotone_prob_and_no_duplicate_tickets(self):
        v=self.checked(n=120)
        self.assertEqual(len({t for t,p in v.top_tickets}),120)
        self.assertEqual(list(v.top_tickets),sorted(v.top_tickets,key=lambda x:(-x[1],x[0])))

    def test_input_is_unmodified_and_frozen_output_cannot_buy(self):
        x=prediction()
        original=dataclasses.asdict(x)
        v=self.checked(source=x)
        self.assertEqual(dataclasses.asdict(x),original)
        with self.assertRaises(dataclasses.FrozenInstanceError):v.buy_eligible=True
        self.assertNotIn('odds',vars(type(v)))

if __name__=='__main__': unittest.main()
