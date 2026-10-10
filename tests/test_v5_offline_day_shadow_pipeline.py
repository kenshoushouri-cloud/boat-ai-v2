"""Focused offline orchestration tests: stub existing stage math/ledger only.

These verify race/cohort/time joins and HOLD wiring, not a full-dependency
historical result or a real official odds/receipt test.
"""
from __future__ import annotations

import dataclasses
import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dataclasses import dataclass

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 10, 10, tzinfo=JST)
R1 = '20261010_03_01'
R2 = '20261010_03_02'
R3 = '20261011_03_01'

@dataclass(frozen=True)
class Input:
    race_id: str
    decision_cutoff_at: datetime

@dataclass(frozen=True)
class Frozen:
    race_id: str
    frozen_at: datetime
    tickets: tuple[str, ...] = ('1-2-3',)

@dataclass(frozen=True)
class Result:
    race_id: str
    status: str = 'OFFICIAL'

FALSE_FLAGS = ('independently_authenticated_source',
               'original_first_observation_verified','six_active_starts_confirmed',
               'selection_eligible','beforeinfo_first_write_eligible',
               'forward_eligible','buy_eligible')


def verdict(**kwargs):
    return types.SimpleNamespace(**dict({key:False for key in FALSE_FLAGS}, **kwargs))


def score(candidate):
    return verdict(synthetic_math_consistent=True, race_id=candidate.race_id,
                   reason='SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD')


def rank(scored, *, ticket_count):
    return verdict(synthetic_math_consistent=True, race_id=scored.race_id,
                   requested_ticket_count=ticket_count,
                   ticket_distribution=tuple(range(120)),
                   reason='SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD')


def cash(ranks, pre, post):
    if any(x.status == 'PENDING' for x in post):
        return verdict(mock_complete=False,reason='LEDGER_UNRESOLVED_OR_INVALID_SETTLEMENT')
    if any(len(x.tickets) != r.requested_ticket_count for x,r in zip(pre,ranks)):
        return verdict(mock_complete=False,reason='MISSING_EXTRA_OR_REORDERED_PURCHASE_TICKETS')
    count=sum(r.requested_ticket_count for r in ranks)
    spent=count*100
    refund=sum(len(x.tickets)*100 for x,y in zip(pre,post) if y.status=='VOID')
    return verdict(mock_complete=True, reason='SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD',
                   candidate_races=len(ranks), tickets=count,
                   synthetic_paid_yen=spent, synthetic_return_yen=refund,
                   synthetic_net_yen=refund-spent, synthetic_roi_pct=100*refund/spent,
                   actual_purchase_verified=False)


mods={}
for name in ('offline_mainline_inference','offline_trifecta_shadow_ranking',
             'offline_trifecta_cash_ledger','offline_trifecta_cash_bridge'):
    obj=types.ModuleType('v5.'+name)
    mods[obj.__name__]=obj
mods['v5.offline_mainline_inference'].OfflineV5InferenceInput=Input
mods['v5.offline_mainline_inference'].check_offline_v5_inference=score
mods['v5.offline_trifecta_shadow_ranking'].rank_offline_v5_trifectas=rank
mods['v5.offline_trifecta_cash_ledger'].MAX_RACES=500
mods['v5.offline_trifecta_cash_ledger'].PredeadlineMockRace=Frozen
mods['v5.offline_trifecta_cash_ledger'].PostraceMockResult=Result
mods['v5.offline_trifecta_cash_bridge'].audit_offline_shadow_cash_bridge=cash
with patch.dict(sys.modules,mods):
    pipeline=importlib.import_module('v5.offline_day_shadow_pipeline')


def case():
    return pipeline.OfflineV5DayInput(
        (Input(R1,T), Input(R2,T)), (1,1),
        (Frozen(R1,T), Frozen(R2,T)),
        (Result(R1), Result(R2,'VOID')),
    )


class OfflineDayPipelineTests(unittest.TestCase):
    def inspect(self,c, reason):
        result=pipeline.evaluate_offline_v5_day(c)
        self.assertEqual(result.reason,reason)
        for key in ('independently_authenticated_source', 'actual_purchase_verified',
                    'six_active_starts_confirmed','original_first_observation_verified',
                    'beforeinfo_first_write_eligible','selection_eligible',
                    'forward_eligible','buy_eligible'):
            self.assertIs(getattr(result,key),False)
        if reason!='SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD':
            self.assertFalse(result.mock_complete)
            self.assertEqual((result.candidate_races,result.synthetic_paid_yen,
                              result.synthetic_net_yen,result.synthetic_roi_pct),(0,0,0,None))
        return result

    def test_complete_day_official_and_void_included(self):
        v=self.inspect(case(),'SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD')
        self.assertEqual((v.candidate_races,v.simulated_tickets,v.synthetic_paid_yen,
                          v.synthetic_return_yen,v.synthetic_net_yen), (2,2,200,100,-100))
        self.assertEqual(v.synthetic_roi_pct,50.)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.buy_eligible=True

    def test_scores_and_rankings_run_for_each_candidate(self):
        with (patch.object(pipeline,'check_offline_v5_inference',wraps=score) as x,
              patch.object(pipeline,'rank_offline_v5_trifectas',wraps=rank) as y,
              patch.object(pipeline,'audit_offline_shadow_cash_bridge',wraps=cash) as z):
            self.inspect(case(),'SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD')
            self.assertEqual((x.call_count,y.call_count,z.call_count),(2,2,1))
            self.assertEqual([c.kwargs['ticket_count'] for c in y.call_args_list],[1,1])

    def test_invalid_request_and_empty_day_frozen(self):
        self.inspect({},'DAY_INPUT_INVALID')
        v=dataclasses.replace(case(),candidates=(),requested_ticket_counts=(),predecision=(),postrace=())
        self.inspect(v,'DAY_COHORT_OR_TICKET_COUNTS_INVALID')

    def test_missing_or_wrong_ticket_counts(self):
        d=case()
        self.inspect(dataclasses.replace(d,requested_ticket_counts=(1,)),
                     'DAY_COHORT_OR_TICKET_COUNTS_INVALID')
        self.inspect(dataclasses.replace(d,requested_ticket_counts=(True,1)),
                     'DAY_COHORT_OR_TICKET_COUNTS_INVALID')
        self.inspect(dataclasses.replace(d,requested_ticket_counts=(0,1)),
                     'DAY_COHORT_OR_TICKET_COUNTS_INVALID')

    def test_duplicate_or_missing_races_denied_before_scoring(self):
        d=case()
        self.inspect(dataclasses.replace(d,candidates=(d.candidates[0],d.candidates[0])),
                     'DAY_RACE_ID_JOIN_INVALID')
        self.inspect(dataclasses.replace(d,predecision=(d.predecision[0],Frozen(R3,T))),
                     'DAY_RACE_ID_JOIN_INVALID')
        self.inspect(dataclasses.replace(d,postrace=(d.postrace[0],Result(R3))),
                     'DAY_RACE_ID_JOIN_INVALID')

    def test_mixed_date_cohort_refused(self):
        d=case()
        self.inspect(dataclasses.replace(d,candidates=(d.candidates[0],Input(R3,T)),
                         predecision=(d.predecision[0],Frozen(R3,T)),
                         postrace=(d.postrace[0],Result(R3))),
                     'DAY_MIXED_RACE_DATES')

    def test_freeze_clock_is_bound_to_input_cutoff(self):
        d=case()
        self.inspect(dataclasses.replace(d,candidates=(Input(R1,T+timedelta(minutes=1)),d.candidates[1])),
                     'INFERENCE_NOT_TIED_TO_FROZEN_DECISION_TIME')

    def test_modified_scoring_or_authority_flag_denied(self):
        with patch.object(pipeline,'check_offline_v5_inference',return_value=verdict(
            synthetic_math_consistent=True,race_id=R1,buy_eligible=True,reason='SYNTHETIC')):
            self.inspect(case(),'V5_INFERENCE_SYNTHETIC')

    def test_ranking_authority_denied(self):
        with patch.object(pipeline,'rank_offline_v5_trifectas',return_value=verdict(
            synthetic_math_consistent=True,race_id=R1,requested_ticket_count=1,
            ticket_distribution=tuple(range(120)),buy_eligible=True,reason='SYNTHETIC')):
            self.inspect(case(),'V5_TRIFECTA_SYNTHETIC')

    def test_pending_postrace_keeps_economics_blank(self):
        d=case()
        self.inspect(dataclasses.replace(d,postrace=(Result(R1),Result(R2,'PENDING'))),
                     'V5_SHADOW_CASH_LEDGER_UNRESOLVED_OR_INVALID_SETTLEMENT')

    def test_missing_purchase_order_denies_all_economics(self):
        d=case()
        self.inspect(dataclasses.replace(d,predecision=(Frozen(R1,T,()),d.predecision[1])),
                     'V5_SHADOW_CASH_MISSING_EXTRA_OR_REORDERED_PURCHASE_TICKETS')

    def test_no_hidden_v4_two_ticket_rule(self):
        d=case()
        d=dataclasses.replace(d,requested_ticket_counts=(2,1),
                              predecision=(Frozen(R1,T,('1-2-3','1-3-2')),d.predecision[1]))
        v=self.inspect(d,'SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD')
        self.assertEqual(v.simulated_tickets,3)


if __name__=='__main__':
    unittest.main()
