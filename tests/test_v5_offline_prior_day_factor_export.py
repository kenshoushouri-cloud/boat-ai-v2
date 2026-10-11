"""Offline-only prior-day factor export: mock research helper boundaries.

Mocks verify chronology, vector plumbing and guards, NOT numerical equivalence
to real production research helper formulas (separate native parity needed).
"""
from __future__ import annotations
import sys
import types
import unittest
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from v5.offline_archived_six_lane_bridge import ArchivedLane
from v5.offline_prior_day_factor_export import (
    MAP_KEYS, PriorDayCounters, export_prior_day_factors,
)

JST = ZoneInfo("Asia/Tokyo")
RID = "20260501_24_12"
NESTED = ("lcs", "lcw", "rcs", "rct", "vc")


def counters():
    q = {k: ({} if k in NESTED else Counter()) for k in MAP_KEYS}
    q["lw"] = Counter({1:5, 2:4, 3:3, 4:2, 5:1, 6:1})
    for k in ("lcs","lcw","rcs","rct"):
        q[k] = {i:Counter() for i in range(1,7)}
    q["vc"]={"24":Counter({1:1, 2:1})}
    q["vn"]=Counter({"24":2})
    return q


def state():
    return PriorDayCounters(date(2026,4,30),date(2025,7,1),16,counters(),"mock-prior-day")


def lanes():
    return tuple(ArchivedLane(
        i, 4100+i, "A1",
        tuple({"race_date":f"2026-04-{day:02d}","finish_position":(day%6)+1}
              for day in range(26,31)),
        (3,1,4,2,6,5)[i-1], "official_beforeinfo_historical",
        datetime(2026,8,15,13,54,tzinfo=JST)) for i in range(1,7))


def mock_research_modules():
    b = types.ModuleType("research.v5_lc_rf_exrank_rc_plus_opponent_pg")
    vr = types.ModuleType("research.v5_lane_class_plus_venue_residual_pg")
    b.NEUTRAL = .5
    b.lane_probs = lambda w,n:[(w[i]+1.)/(n+6.) for i in range(1,7)]
    b.lc_probs = lambda cls,gp,starts,wins:list(gp)
    def strength(history):
        val = [int(h["finish_position"]) for h in history if 1<=int(h["finish_position"])<=6]
        return ((1+sum(f<=3 for f in val))/(len(val)+2.),len(val)) if len(val)>=3 else (.5,len(val))
    b.recent_strength = strength
    b.adjusted = lambda key,prior,starts,wins:(prior,0,0.0)
    b.rc_prior = lambda lane,starts,top3:.5
    b.rc_adjusted = lambda racer,lane,prior,starts,top3:(prior,0,0.0)
    b.opponent_probs = lambda cls,base,starts,wins:(list(base),0,[])
    vr.venue_shrunk = lambda venue,gp,vc,vn:(list(gp),[0.]*6)
    pkg = types.ModuleType("research")
    pkg.__path__=[]
    pkg.v5_lc_rf_exrank_rc_plus_opponent_pg=b
    pkg.v5_lane_class_plus_venue_residual_pg=vr
    return {"research":pkg,
            "research.v5_lc_rf_exrank_rc_plus_opponent_pg":b,
            "research.v5_lane_class_plus_venue_residual_pg":vr}


class TestFrozenFactorExport(unittest.TestCase):
    def run_one(self,rid=RID,rows=None,s=None):
        with patch.dict(sys.modules, mock_research_modules()):
            return export_prior_day_factors(rid,lanes() if rows is None else rows,
                                            state() if s is None else s)

    def test_six_factor_vectors_and_exact_key_names(self):
        out=self.run_one()
        self.assertEqual(out.reason,"RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY")
        self.assertEqual(set(out.factors),
                         {"recent_form","exhibition_rank","racer_course","opponent","venue_lane"})
        self.assertEqual(tuple(len(v) for v in out.factors.values()),(6,)*5)
        self.assertAlmostEqual(sum(out.base_probabilities),1.)
        self.assertFalse(out.buy_eligible)
        self.assertFalse(out.source_state_independently_verified)

    def test_neutral_only_if_prior_history_insufficient_not_magic_model(self):
        rows=list(lanes())
        rows[0]=replace(rows[0],recent_form=({"race_date":"2026-04-30","finish_position":3},))
        out=self.run_one(rows=tuple(rows))
        self.assertEqual(out.factors["recent_form"][0],1.)

    def test_previous_day_fit_boundary(self):
        out=self.run_one(s=replace(state(),fitted_through=date(2026,5,1)))
        self.assertEqual(out.reason,"PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED")

    def test_history_not_prior_day_rejected(self):
        rows=list(lanes());rows[0]=replace(rows[0],recent_form=({"race_date":"2026-05-01"},))
        self.assertEqual(self.run_one(rows=tuple(rows)).reason,
                         "RECENT_HISTORY_NOT_PRIOR_DAY")

    def test_duplicate_exhibition_rank_rejected(self):
        rows=list(lanes());rows[0]=replace(rows[0],exhibition_time_rank=1)
        self.assertEqual(self.run_one(rows=tuple(rows)).reason,"SIX_LANE_FIELDS_INVALID")

    def test_duplicate_racer_rejected(self):
        rows=list(lanes());rows[0]=replace(rows[0],racer_number=4102)
        self.assertEqual(self.run_one(rows=tuple(rows)).reason,"SIX_LANE_FIELDS_INVALID")

    def test_missing_one_history_prior_counter_set_rejected(self):
        s=state();cs=deepcopy(s.counters);del cs["rks"]
        self.assertEqual(self.run_one(s=replace(s,counters=cs)).reason,
                         "PRIOR_DAY_COUNTER_KEYS_INVALID")

    def test_bad_negative_counter_does_not_create_fake_probabilities(self):
        s=state();cs=deepcopy(s.counters);cs["lw"][1]=-5
        self.assertEqual(self.run_one(s=replace(s,counters=cs)).reason,
                         "PRIOR_DAY_COUNTER_SHAPE_INVALID")

    def test_state_counter_input_unchanged(self):
        s=state();original=deepcopy(s.counters)
        self.assertEqual(self.run_one(s=s).reason,
                         "RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY")
        self.assertEqual(s.counters,original)

    def test_missing_training_source_not_assumed_verified(self):
        self.assertEqual(self.run_one(s=replace(state(),source_ref="")).reason,
                         "PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED")

    def test_missing_one_lane_rejected(self):
        self.assertEqual(self.run_one(rows=lanes()[:5]).reason,"SIX_LANES_REQUIRED")


if __name__=="__main__":
    unittest.main()
