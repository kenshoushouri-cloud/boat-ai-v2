# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.candidate_discovery_market_forward_metrics import summarize_forward


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
):
    return {
        "race_id": rid,
        "race_date": ds,
        "venue_id": "08",
        "race_no": rno,
        "counts_as_prospective": prospective,
        "late_snapshot_available": late,
        "result_ready": ready,
        "market_top2_support": support,
        "hit": hit,
        "return_yen": ret,
    }


class MarketForwardMetricsTest(unittest.TestCase):
    def test_same_universe_baseline_and_supported_metrics(self):
        rows = [
            row("r1", "2026-09-14", 1, support=True, hit=True, ret=300),
            row("r2", "2026-09-14", 2, support=True, hit=False, ret=0),
            row("r3", "2026-09-15", 1, support=True, hit=True, ret=200),
            row("r4", "2026-09-15", 2, support=False, hit=False, ret=0),
            row("old", "2026-09-13", 3, support=True, hit=True, ret=999, prospective=False),
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


if __name__ == "__main__":
    unittest.main()
