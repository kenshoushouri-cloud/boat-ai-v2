"""Offline batch manifest + fail-closed multi-day scenario aggregation tests."""
import unittest
from dataclasses import replace
from datetime import date
from v5.offline_day_evidence_coverage import DayEvidenceAudit
from v5.offline_frozen_day_evidence_adapter import FrozenDayEvidenceBinding
from v5.offline_retrospective_result_adapter import V5ScenarioJoin
from v5.offline_retrospective_trifecta_returns import RetrospectiveReturns
from v5.offline_whole_day_research_ledger import WholeDayResearchLedger
from v5.offline_research_period_batches import plan_research_period, rollup_research_period


def simulated(day, decision="FROZEN", *, unresolved=False):
    race_id = f"{day:%Y%m%d}_24_12"
    audit = DayEvidenceAudit(day, (), 1, int(decision=="FROZEN"),
                             int(decision=="NO_BUY"), int(decision=="PENDING"),
                             (), (), True)
    frozen = (race_id,) if decision == "FROZEN" else ()
    no_buy = (race_id,) if decision == "NO_BUY" else ()
    pending = (race_id,) if decision == "PENDING" else ()
    coverage = FrozenDayEvidenceBinding(audit, frozen + no_buy, frozen, no_buy)
    economics = RetrospectiveReturns(
        "INCOMPLETE_COHORT_ROI_WITHHELD" if unresolved else
        "RETROSPECTIVE_RESULT_PAYOUT_SCENARIO_ONLY",
        candidate_races=1, planned_stake_yen=100,
        resolved_races=0 if unresolved else 1,
        unresolved_races=1 if unresolved else 0,
        resolved_stake_yen=0 if unresolved else 100,
        unresolved_stake_yen=100 if unresolved else 0,
        gross_return_yen=0 if unresolved else 240,
        hypothetical_net_yen=None if unresolved else 140,
        hypothetical_roi_pct=None if unresolved else 240.0)
    scenario = V5ScenarioJoin("RETROSPECTIVE_V5_SCENARIO_JOIN_NO_BUY_AUTHORITY",
                              economics=economics) if frozen else None
    return WholeDayResearchLedger("SCENARIO_ONLY", coverage,
                                  ((race_id, decision),), (), frozen,
                                  no_buy, pending, scenario,
                                  bool(frozen and not unresolved))


class TestPeriodBatches(unittest.TestCase):
    def test_seven_day_windows_and_last_partial(self):
        p = plan_research_period(date(2025,7,1),date(2025,7,17))
        self.assertEqual([x.expected_days for x in p.windows],[7,7,3])
        self.assertEqual(p.expected_days,17)
        self.assertFalse(p.buy_eligible)

    def test_reject_unsafe_period_and_window(self):
        for a,b,n in ((date(2025,6,30),date(2025,7,1),7),
                      (date(2025,7,2),date(2025,7,1),7),
                      (date(2025,7,1),date(2025,7,1),0)):
            with self.assertRaises(ValueError): plan_research_period(a,b,n)

    def test_complete_declared_scenario_only(self):
        p = plan_research_period(date(2026,5,1),date(2026,5,2))
        r = rollup_research_period(p, (simulated(p.start), simulated(p.end,"NO_BUY")))
        self.assertEqual(r.inventory_races,2)
        self.assertEqual(r.selected_races,1)
        self.assertEqual(r.hypothetical_roi_pct,240.0)
        self.assertEqual(r.hypothetical_net_yen,140)
        self.assertFalse(r.v5_real_roi_verified)

    def test_missing_day_kept_and_roi_withheld(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,3))
        r=rollup_research_period(p,(simulated(p.start),))
        self.assertEqual(r.missing_days,(date(2026,5,2),date(2026,5,3)))
        self.assertIsNone(r.hypothetical_roi_pct)

    def test_pending_day_prevents_full_period_roi(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,2))
        r=rollup_research_period(p,(simulated(p.start), simulated(p.end,"PENDING")))
        self.assertEqual(r.pending_races,1)
        self.assertIsNone(r.hypothetical_net_yen)

    def test_missing_refund_unresolved_prevents_roi(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,2))
        r=rollup_research_period(p,(simulated(p.start,unresolved=True),simulated(p.end,"NO_BUY")))
        self.assertEqual(r.unresolved_selected_races,1)
        self.assertIsNone(r.hypothetical_roi_pct)

    def test_zero_buy_period_has_no_roi(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,2))
        r=rollup_research_period(p,(simulated(p.start,"NO_BUY"),simulated(p.end,"NO_BUY")))
        self.assertEqual(r.hypothetical_stake_yen,0)
        self.assertIsNone(r.hypothetical_roi_pct)

    def test_duplicate_and_out_of_range_rejected(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,1))
        x=simulated(p.start)
        with self.assertRaises(ValueError): rollup_research_period(p,(x,x))
        with self.assertRaises(ValueError): rollup_research_period(p,(simulated(date(2026,5,2)),))

    def test_denominator_mismatch_rejected(self):
        p=plan_research_period(date(2026,5,1),date(2026,5,1))
        x=simulated(p.start)
        bad=replace(x,coverage=replace(x.coverage,audit=replace(x.coverage.audit,inventory_count=2)))
        with self.assertRaises(ValueError): rollup_research_period(p,(bad,))


if __name__=="__main__": unittest.main()
