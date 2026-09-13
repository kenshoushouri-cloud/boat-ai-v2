# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.candidate_discovery_forward_stability_metrics import summarize_frozen_forward
from research.candidate_discovery_market_forward_metrics import V4_FEED_CONTRACT, summarize_forward


def row(
    rid: str,
    ds: str,
    rno: int,
    *,
    support: bool,
    hit: bool,
    ret: int,
    prospective: bool = True,
    late: bool = True,
    ready: bool = True,
    source_contract: str = V4_FEED_CONTRACT,
    source_prospective_eligible: bool = True,
):
    return {
        "race_id": rid,
        "race_date": ds,
        "venue_id": "08",
        "race_no": rno,
        "source_feed_contract": source_contract,
        "source_prospective_evidence_eligible": source_prospective_eligible,
        "counts_as_prospective": prospective,
        "late_snapshot_available": late,
        "result_ready": ready,
        "market_top2_support": support,
        "hit": hit,
        "return_yen": ret,
    }


def eval_doc(ds: str, rows: list[dict]):
    return {
        "contract": "candidate_discovery_frozen_forward_eval_v1",
        "source_date": ds,
        "rows": rows,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }


def eval_row(rid: str, tier: str, tickets: list[str], *, hit: bool, ret: int, ready: bool = True):
    if not ready:
        return {"race_id": rid, "tier": tier, "status": "RESULT_NOT_READY", "tickets": tickets}
    return {
        "race_id": rid,
        "tier": tier,
        "status": "EVALUATED",
        "tickets": tickets,
        "hit": hit,
        "investment_yen": len(tickets) * 100,
        "return_yen": ret,
    }


class MarketForwardMetricsTest(unittest.TestCase):
    def test_same_universe_baseline_and_supported_metrics(self):
        rows = [
            row("r1", "2026-09-14", 1, support=True, hit=True, ret=300),
            row("r2", "2026-09-14", 2, support=True, hit=False, ret=0),
            row("r3", "2026-09-15", 1, support=True, hit=True, ret=200),
            row("r4", "2026-09-15", 2, support=False, hit=False, ret=0),
            row("old", "2026-09-13", 3, support=True, hit=True, ret=999, prospective=False, source_contract="candidate_discovery_main_feed_v1", source_prospective_eligible=False),
            row("nol", "2026-09-15", 4, support=True, hit=True, ret=999, late=False),
            row("pend", "2026-09-15", 5, support=True, hit=True, ret=999, ready=False),
        ]
        out = summarize_forward(rows)
        base = out["late_available_baseline"]
        sup = out["market_top2_supported"]

        self.assertEqual(base["evaluated_cases"], 4)
        self.assertEqual(base["hits"], 2)
        self.assertEqual(base["investment_yen"], 400)
        self.assertEqual(base["return_yen"], 500)
        self.assertEqual(base["profit_yen"], 100)
        self.assertEqual(base["roi_pct"], 125.0)
        self.assertEqual(base["positive_days"], 1)
        self.assertEqual(base["positive_day_rate_pct"], 50.0)

        self.assertEqual(sup["evaluated_cases"], 3)
        self.assertEqual(sup["hits"], 2)
        self.assertEqual(sup["investment_yen"], 300)
        self.assertEqual(sup["return_yen"], 500)
        self.assertEqual(sup["profit_yen"], 200)
        self.assertEqual(sup["roi_pct"], 166.667)
        self.assertEqual(sup["max_losing_race_streak"], 1)
        self.assertEqual(sup["max_drawdown_yen"], 100)
        self.assertEqual(sup["positive_days"], 2)
        self.assertEqual(sup["positive_day_rate_pct"], 100.0)
        self.assertEqual(sup["max_single_hit_return_yen"], 300)
        self.assertEqual(sup["max_single_hit_share_of_returns_pct"], 60.0)
        self.assertEqual(out["source_feed_contract"], V4_FEED_CONTRACT)
        self.assertTrue(out["source_prospective_evidence_required"])
        self.assertEqual(out["milestone"]["next_target"], 30)
        self.assertEqual(out["milestone"]["remaining_to_next"], 27)
        self.assertFalse(out["promotion_allowed"])
        self.assertFalse(out["purchase_action"])

    def test_milestone_30_does_not_promote(self):
        rows = [
            row(f"r{i:02d}", "2026-09-14", i, support=True, hit=False, ret=0)
            for i in range(1, 31)
        ]
        out = summarize_forward(rows)
        self.assertEqual(out["milestone"]["reached"], [30])
        self.assertEqual(out["milestone"]["next_target"], 50)
        self.assertEqual(out["milestone"]["remaining_to_next"], 20)
        self.assertFalse(out["milestone"]["promotion_allowed"])

    def test_non_v4_prospective_row_fails_closed(self):
        bad = row(
            "baseline-mislabel",
            "2026-09-14",
            1,
            support=True,
            hit=False,
            ret=0,
            prospective=True,
            source_contract="candidate_discovery_main_feed_v1",
        )
        with self.assertRaises(ValueError):
            summarize_forward([bad])

    def test_unproven_v4_prospective_row_fails_closed(self):
        bad = row(
            "v4-unproven",
            "2026-09-14",
            1,
            support=True,
            hit=False,
            ret=0,
            prospective=True,
            source_prospective_eligible=False,
        )
        with self.assertRaises(ValueError):
            summarize_forward([bad])

    def test_duplicate_race_fails_closed(self):
        rows = [
            row("dup", "2026-09-14", 1, support=True, hit=False, ret=0),
            row("dup", "2026-09-14", 2, support=False, hit=False, ret=0),
        ]
        with self.assertRaises(ValueError):
            summarize_forward(rows)

    def test_invalid_return_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize_forward([row("bad1", "2026-09-14", 1, support=True, hit=False, ret=100)])
        with self.assertRaises(ValueError):
            summarize_forward([row("bad2", "2026-09-14", 2, support=True, hit=True, ret=0)])

    def test_frozen_feed_stability_splits_v4_and_legacy(self):
        docs = [
            eval_doc("2026-09-14", [
                eval_row("20260914_08_01", "A", ["1-2-3", "1-3-2"], hit=True, ret=500),
                eval_row("20260914_08_02", "B", ["2-1-3", "2-3-1"], hit=False, ret=0),
                eval_row("20260914_10_01", "L", ["1-6-5"], hit=False, ret=0),
            ]),
            eval_doc("2026-09-15", [
                eval_row("20260915_08_01", "C", ["3-1-2", "3-2-1"], hit=False, ret=0),
                eval_row("20260915_21_01", "L", ["3-1-2"], hit=True, ret=300),
                eval_row("20260915_22_02", "A", ["4-1-2", "4-2-1"], hit=False, ret=0, ready=False),
            ]),
        ]
        out = summarize_frozen_forward(docs)
        all_feed = out["all_feed"]
        core = out["v4_core"]
        legacy = out["legacy_carryover"]

        self.assertEqual(all_feed["evaluated_races"], 5)
        self.assertEqual(all_feed["tickets"], 8)
        self.assertEqual(all_feed["hits"], 2)
        self.assertEqual(all_feed["investment_yen"], 800)
        self.assertEqual(all_feed["return_yen"], 800)
        self.assertEqual(all_feed["profit_yen"], 0)
        self.assertEqual(all_feed["roi_pct"], 100.0)
        self.assertEqual(all_feed["max_single_hit_return_yen"], 500)
        self.assertEqual(all_feed["max_single_hit_share_of_returns_pct"], 62.5)
        self.assertEqual(all_feed["top3_hit_share_of_returns_pct"], 100.0)
        self.assertEqual(all_feed["months"], 1)
        self.assertEqual(out["missing_result_rows"], 1)

        self.assertEqual(core["evaluated_races"], 3)
        self.assertEqual(core["tickets"], 6)
        self.assertEqual(core["investment_yen"], 600)
        self.assertEqual(core["return_yen"], 500)
        self.assertEqual(core["roi_pct"], 83.333)

        self.assertEqual(legacy["evaluated_races"], 2)
        self.assertEqual(legacy["tickets"], 2)
        self.assertEqual(legacy["investment_yen"], 200)
        self.assertEqual(legacy["return_yen"], 300)
        self.assertEqual(legacy["roi_pct"], 150.0)
        self.assertFalse(out["promotion_allowed"])
        self.assertFalse(out["purchase_action"])


if __name__ == "__main__":
    unittest.main()
