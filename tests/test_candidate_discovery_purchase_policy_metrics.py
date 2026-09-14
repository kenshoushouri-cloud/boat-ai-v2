# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.candidate_discovery_purchase_policy_metrics import (
    V4_FEED_CONTRACT,
    summarize_purchase_policy,
)


def candidate(
    day: str,
    rank: int,
    order: int,
    *,
    hit: bool = False,
    ret: int = 0,
    ready: bool = True,
    contract: str = V4_FEED_CONTRACT,
    eligible: bool = True,
    prospective: bool = True,
):
    return {
        "source_feed_contract": contract,
        "source_prospective_evidence_eligible": eligible,
        "counts_as_prospective": prospective,
        "race_date": day,
        "race_id": f"{day.replace('-', '')}_08_{rank:02d}",
        "daily_rank": rank,
        "core_order": order,
        "result_ready": ready,
        "hit": hit,
        "return_yen": ret,
    }


def stage2(
    day: str,
    rank: int,
    *,
    support: bool = False,
    late: bool = True,
    hit: bool = False,
    ret: int = 0,
    ready: bool = True,
    core_order: int = 1,
    contract: str = V4_FEED_CONTRACT,
    eligible: bool = True,
    prospective: bool = True,
):
    return {
        "source_feed_contract": contract,
        "source_prospective_evidence_eligible": eligible,
        "counts_as_prospective": prospective,
        "race_date": day,
        "race_id": f"{day.replace('-', '')}_08_{rank:02d}",
        "daily_rank": rank,
        "core_order": core_order,
        "late_snapshot_available": late,
        "market_top2_support": support,
        "result_ready": ready,
        "hit": hit,
        "return_yen": ret,
    }


def complete_day(day: str, candidate_hits=None, stage2_support=None):
    candidate_hits = candidate_hits or {}
    stage2_support = set(stage2_support or [])
    candidates = []
    annotations = []
    for rank in range(1, 7):
        for order in (1, 2):
            ret = int(candidate_hits.get((rank, order), 0))
            candidates.append(candidate(day, rank, order, hit=ret > 0, ret=ret))
        core1_ret = int(candidate_hits.get((rank, 1), 0))
        annotations.append(
            stage2(
                day,
                rank,
                support=rank in stage2_support,
                hit=core1_ret > 0,
                ret=core1_ret,
            )
        )
    return candidates, annotations


class CandidatePurchasePolicyMetricsTest(unittest.TestCase):
    def test_preregistered_views_and_zero_supported_day(self):
        c1, s1 = complete_day(
            "2026-09-15",
            candidate_hits={(1, 1): 500, (2, 2): 300},
            stage2_support={1, 3},
        )
        c2, s2 = complete_day(
            "2026-09-16",
            candidate_hits={(6, 1): 200},
            stage2_support=set(),
        )
        out = summarize_purchase_policy(c1 + c2, s1 + s2)

        feed = out["candidate_feed"]
        self.assertEqual(feed["prospective_days"], 2)
        self.assertEqual(feed["core_races"], 12)
        self.assertEqual(feed["core_tickets"], 24)
        self.assertEqual(feed["avg_core_tickets_per_day"], 12.0)
        self.assertEqual(feed["all_v4"]["evaluated_cases"], 24)
        self.assertEqual(feed["all_v4"]["investment_yen"], 2400)
        self.assertEqual(feed["all_v4"]["return_yen"], 1000)
        self.assertEqual(feed["by_core_order"]["core_order_1"]["return_yen"], 700)
        self.assertEqual(feed["by_core_order"]["core_order_2"]["return_yen"], 300)
        self.assertEqual(feed["by_race_rank"]["rank_1_2"]["evaluated_cases"], 8)

        st2 = out["stage2_v1"]
        self.assertEqual(st2["core_order"], 1)
        self.assertEqual(st2["annotated_core1_cases"], 12)
        self.assertEqual(st2["late_snapshot_available_cases"], 12)
        self.assertEqual(st2["supported_cases"], 2)
        self.assertEqual(st2["supported_days"], 1)
        self.assertEqual(st2["zero_supported_days"], 1)
        self.assertEqual(st2["zero_supported_day_rate_pct"], 50.0)
        self.assertEqual(st2["avg_supported_cases_per_day"], 1.0)
        self.assertEqual(st2["supported_performance"]["evaluated_cases"], 2)
        self.assertEqual(st2["supported_performance"]["return_yen"], 500)
        self.assertEqual(st2["supported_performance"]["roi_pct"], 250.0)
        self.assertEqual(st2["supported_by_race_rank"]["rank_1_2"]["evaluated_cases"], 1)
        self.assertEqual(st2["supported_by_race_rank"]["rank_3_4"]["evaluated_cases"], 1)
        self.assertEqual(st2["milestone"]["next_target"], 30)
        self.assertEqual(st2["milestone"]["remaining_to_next"], 28)
        self.assertFalse(out["purchase_action"])
        self.assertFalse(out["promotion_allowed"])

    def test_incomplete_candidate_day_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15")
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates[:-1], annotations)

    def test_stage2_core_order2_extension_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15")
        annotations[0] = stage2("2026-09-15", 1, core_order=2)
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates, annotations)

    def test_stage2_support_requires_late_snapshot(self):
        candidates, annotations = complete_day("2026-09-15")
        annotations[0] = stage2("2026-09-15", 1, support=True, late=False)
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates, annotations)

    def test_missing_stage2_race_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15")
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates, annotations[:-1])

    def test_baseline_or_unproven_source_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15")
        candidates[0] = candidate(
            "2026-09-15",
            1,
            1,
            contract="candidate_discovery_main_feed_v1",
        )
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates, annotations)

        candidates, annotations = complete_day("2026-09-15")
        annotations[0] = stage2("2026-09-15", 1, eligible=False)
        with self.assertRaises(ValueError):
            summarize_purchase_policy(candidates, annotations)

    def test_supported_but_result_pending_counts_coverage_not_milestone(self):
        candidates, annotations = complete_day("2026-09-15")
        annotations[0] = stage2(
            "2026-09-15",
            1,
            support=True,
            ready=False,
        )
        out = summarize_purchase_policy(candidates, annotations)
        self.assertEqual(out["stage2_v1"]["supported_cases"], 1)
        self.assertEqual(out["stage2_v1"]["supported_performance"]["evaluated_cases"], 0)
        self.assertEqual(out["stage2_v1"]["milestone"]["supported_evaluated_cases"], 0)
        self.assertEqual(out["stage2_v1"]["milestone"]["remaining_to_next"], 30)


if __name__ == "__main__":
    unittest.main()
