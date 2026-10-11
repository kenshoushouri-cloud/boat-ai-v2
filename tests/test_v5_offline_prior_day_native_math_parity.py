"""V5 exact native research-helper formula wiring parity, CPU-only.

Uses real research functions with DB/incident module imports stubbed solely
to prevent *any* DB attempt. Never mocks the math functions themselves.
Synthetic counters, no results/odds/official GET or production actions.
"""
from __future__ import annotations

import importlib
import math
import sys
import types
import unittest
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from v5.offline_archived_six_lane_bridge import ArchivedLane
from v5.offline_prior_day_factor_export import (
    MAP_KEYS, NESTED, PriorDayCounters, export_prior_day_factors,
)

RID = "20260501_24_12"
DAY = date(2026, 5, 1)
JST = ZoneInfo("Asia/Tokyo")


def inputs():
    wins = (40, 22, 18, 10, 6, 4)
    c = {k: ({} if k in NESTED else Counter()) for k in MAP_KEYS}
    c["lw"] = Counter({i: wins[i - 1] for i in range(1, 7)})
    for k in ("lcs", "lcw", "rcs", "rct"):
        c[k] = {i: Counter() for i in range(1, 7)}
    for lane, w in enumerate(wins, 1):
        c["lcs"][lane].update({"A1": 50, "B1": 50})
        a = min(w, max(1, (w * 4) // 5))
        c["lcw"][lane].update({"A1": a, "B1": w - a})
        c["cs"][lane] = 100
        c["ct"][lane] = min(85, 18 + lane * 7)
        c["rcs"][lane].update({4100 + lane: 40, 5100 + lane: 40})
        c["rct"][lane].update({4100 + lane: 32, 5100 + lane: 5})
        for cls in ("A1", "B1"):
            c["rks"][(lane, cls, "1")] = 40
            c["rkw"][(lane, cls, "1")] = 32
            c["rks"][(lane, cls, "6")] = 40
            c["rkw"][(lane, cls, "6")] = 2
        for other in range(1, 7):
            if other == lane:
                continue
            cls = "A1" if lane % 2 else "B1"
            other_cls = "A1" if other % 2 else "B1"
            key = (lane, cls, other, other_cls)
            c["ps"][key] = 40
            c["pw"][key] = 32 if other % 2 else 3
    c["vc"] = {
        "24": Counter({1: 50, 2: 20, 3: 12, 4: 8, 5: 6, 6: 4}),
        "23": Counter({1: 5, 2: 7, 3: 9, 4: 11, 5: 18, 6: 50}),
    }
    c["vn"] = Counter({"24": 100, "23": 100})
    state = PriorDayCounters(date(2026, 4, 30), date(2025, 7, 1),
                             100, c, "synthetic-only-not-authenticated")
    lanes = tuple(ArchivedLane(
        i, 4100 + i, "A1" if i % 2 else "B1",
        tuple({"race_date": f"2026-04-{d:02d}", "finish_position": ((d+i) % 6)+1}
              for d in range(26, 31)),
        (3, 1, 4, 2, 6, 5)[i-1], "official_beforeinfo_historical",
        datetime(2026, 8, 15, 13, 54, tzinfo=JST),
    ) for i in range(1, 7))
    return state, lanes


def native_research_imports():
    """Stub ONLY dependencies that could touch DB/large historical registries."""
    db = types.ModuleType("db_pg")
    def never_db(*args, **kwargs):
        raise AssertionError("DB_CALL_FORBIDDEN_IN_PARITY_TEST")
    db.fetch_all = never_db
    registry = types.ModuleType("research.historical_void_registry")
    registry.VERIFIED_VOID_RACE_IDS = frozenset()
    registry.EVIDENCE_REF = "OFFLINE_SYNTHETIC_ONLY"
    incident = types.ModuleType("research.historical_incident_eligibility")
    incident.classify_historical_incident = never_db
    return {
        "db_pg": db,
        "research.historical_void_registry": registry,
        "research.historical_incident_eligibility": incident,
    }


def direct_reference(state, ordered, core, venue):
    """Independently assemble 6-vector math using actual research functions."""
    q = deepcopy(dict(state.counters))
    for key in NESTED:
        q[key] = defaultdict(Counter, q[key])
    classes = {r.lane: r.racer_class for r in ordered}
    gp = core.lane_probs(q["lw"], state.completed_races)
    lc = core.lc_probs(classes, gp, q["lcs"], q["lcw"])
    course_prior = {
        lane: core.rc_prior(lane, q["cs"], q["ct"]) for lane in range(1, 7)
    }
    recent = []
    exh = []
    course = []
    for r in ordered:
        strength, _ = core.recent_strength(list(r.recent_form))
        recent.append(max(strength / core.NEUTRAL, 1e-12))
        ex_value, _, _ = core.adjusted(
            (r.lane, classes[r.lane], str(r.exhibition_time_rank)),
            lc[r.lane - 1], q["rks"], q["rkw"])
        exh.append(max(ex_value / max(lc[r.lane-1], 1e-12), 1e-12))
        rc_value, _, _ = core.rc_adjusted(
            r.racer_number, r.lane, course_prior[r.lane],
            q["rcs"], q["rct"])
        course.append(max(rc_value / max(course_prior[r.lane], 1e-12), 1e-12))
    opp, _, _ = core.opponent_probs(classes, lc, q["ps"], q["pw"])
    opp_factor = [max(opp[i] / max(lc[i], 1e-12), 1e-12) for i in range(6)]
    vp, _ = venue.venue_shrunk("24", gp, q["vc"], q["vn"])
    venue_factor = [max(vp[i] / max(gp[i], 1e-12), 1e-12) for i in range(6)]
    return tuple(lc), {
        "recent_form": tuple(recent),
        "exhibition_rank": tuple(exh),
        "racer_course": tuple(course),
        "opponent": tuple(opp_factor),
        "venue_lane": tuple(venue_factor),
    }


class TestNativeResearchFormulaParity(unittest.TestCase):
    def test_real_native_math_all_six_vectors_equal(self):
        state, lanes = inputs()
        # Real original research modules, no math-function stubs.
        with patch.dict(sys.modules, native_research_imports()):
            core = importlib.import_module(
                "research.v5_lc_rf_exrank_rc_plus_opponent_pg")
            venue = importlib.import_module(
                "research.v5_lane_class_plus_venue_residual_pg")
            output = export_prior_day_factors(RID, lanes, state)
            reference_base, reference_factors = direct_reference(
                state, lanes, core, venue)
        self.assertEqual(output.reason, "RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY")
        self.assertEqual(output.fitted_through, date(2026, 4, 30))
        self.assertEqual(set(output.factors), set(reference_factors))
        for actual, expected in zip(output.base_probabilities, reference_base):
            self.assertTrue(math.isclose(actual, expected, rel_tol=0,
                                         abs_tol=1e-12))
        for key in reference_factors:
            with self.subTest(factor=key):
                for actual, expected in zip(output.factors[key],
                                            reference_factors[key]):
                    self.assertTrue(math.isclose(actual, expected, rel_tol=0,
                                                 abs_tol=1e-12))
        self.assertFalse(output.forward_eligible)
        self.assertFalse(output.buy_eligible)
        self.assertFalse(output.source_state_independently_verified)

    def test_state_not_mutated_by_real_helpers(self):
        state, lanes = inputs()
        frozen = deepcopy(state.counters)
        with patch.dict(sys.modules, native_research_imports()):
            out = export_prior_day_factors(RID, lanes, state)
        self.assertEqual(out.reason, "RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY")
        self.assertEqual(state.counters, frozen)

    def test_same_day_training_rejected_before_helper_import(self):
        state, lanes = inputs()
        later = PriorDayCounters(DAY, state.history_start, state.completed_races,
                                 state.counters, state.source_ref)
        with patch.dict(sys.modules, native_research_imports()):
            out = export_prior_day_factors(RID, lanes, later)
        self.assertEqual(out.reason, "PRIOR_DAY_STATE_DATE_OR_SOURCE_UNVERIFIED")
        self.assertEqual(out.factors, {})
        self.assertFalse(out.buy_eligible)


if __name__ == "__main__":
    unittest.main()
