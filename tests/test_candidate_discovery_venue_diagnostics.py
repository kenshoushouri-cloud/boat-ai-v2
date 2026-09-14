# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.candidate_discovery_venue_diagnostics import (
    V4_FEED_CONTRACT,
    summarize_venue_diagnostics,
)


def candidate(day, rank, order, venue, *, hit=False, ret=0, ready=True):
    return {
        "source_feed_contract": V4_FEED_CONTRACT,
        "source_prospective_evidence_eligible": True,
        "counts_as_prospective": True,
        "race_date": day,
        "race_id": f"{day.replace('-', '')}_{int(venue):02d}_{rank:02d}",
        "venue_id": str(venue),
        "daily_rank": rank,
        "core_order": order,
        "result_ready": ready,
        "hit": hit,
        "return_yen": ret,
    }


def stage2(day, rank, venue, *, support=False, late=True, hit=False, ret=0, ready=True, core_order=1):
    return {
        "source_feed_contract": V4_FEED_CONTRACT,
        "source_prospective_evidence_eligible": True,
        "counts_as_prospective": True,
        "race_date": day,
        "race_id": f"{day.replace('-', '')}_{int(venue):02d}_{rank:02d}",
        "venue_id": str(venue),
        "daily_rank": rank,
        "core_order": core_order,
        "late_snapshot_available": late,
        "market_top2_support": support,
        "result_ready": ready,
        "hit": hit,
        "return_yen": ret,
    }


def complete_day(day, venues, *, hits=None, support_ranks=None):
    hits = hits or {}
    support_ranks = set(support_ranks or [])
    candidates = []
    annotations = []
    for rank, venue in enumerate(venues, 1):
        for order in (1, 2):
            ret = int(hits.get((rank, order), 0))
            candidates.append(candidate(day, rank, order, venue, hit=ret > 0, ret=ret))
        core1_ret = int(hits.get((rank, 1), 0))
        annotations.append(
            stage2(
                day,
                rank,
                venue,
                support=rank in support_ranks,
                hit=core1_ret > 0,
                ret=core1_ret,
            )
        )
    return candidates, annotations


class VenueDiagnosticsTest(unittest.TestCase):
    def test_venue_metrics_are_diagnostic_only(self):
        c1, s1 = complete_day(
            "2026-09-15",
            [8, 8, 12, 12, 18, 18],
            hits={(1, 1): 500, (3, 2): 300},
            support_ranks={1, 3},
        )
        c2, s2 = complete_day(
            "2026-09-16",
            [8, 12, 18, 8, 12, 18],
            hits={(6, 1): 200},
            support_ranks={6},
        )
        out = summarize_venue_diagnostics(c1 + c2, s1 + s2)

        self.assertFalse(out["venue_exclusion_allowed"])
        self.assertFalse(out["purchase_action"])
        self.assertFalse(out["promotion_allowed"])
        self.assertIn("NO_EXCLUSION", out["venue_policy"])

        all_by = out["candidate_all_v4_by_venue"]
        self.assertEqual(all_by["08"]["evaluated_cases"], 8)
        self.assertEqual(all_by["08"]["return_yen"], 500)
        self.assertEqual(all_by["12"]["evaluated_cases"], 8)
        self.assertEqual(all_by["12"]["return_yen"], 300)
        self.assertEqual(all_by["18"]["evaluated_cases"], 8)
        self.assertEqual(all_by["18"]["return_yen"], 200)

        supported = out["stage2_supported_core1_by_venue"]
        self.assertEqual(supported["08"]["evaluated_cases"], 1)
        self.assertEqual(supported["08"]["return_yen"], 500)
        self.assertEqual(supported["12"]["evaluated_cases"], 1)
        self.assertEqual(supported["12"]["return_yen"], 0)
        self.assertEqual(supported["18"]["evaluated_cases"], 1)
        self.assertEqual(supported["18"]["return_yen"], 200)

    def test_missing_or_invalid_venue_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15", [1, 2, 3, 4, 5, 6])
        candidates[0]["venue_id"] = ""
        with self.assertRaises(ValueError):
            summarize_venue_diagnostics(candidates, annotations)

        candidates, annotations = complete_day("2026-09-15", [1, 2, 3, 4, 5, 6])
        annotations[0]["venue_id"] = "24"
        with self.assertRaises(ValueError):
            summarize_venue_diagnostics(candidates, annotations)

    def test_stage2_core_order2_extension_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15", [1, 2, 3, 4, 5, 6])
        annotations[0]["core_order"] = 2
        with self.assertRaises(ValueError):
            summarize_venue_diagnostics(candidates, annotations)

    def test_support_without_late_snapshot_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15", [1, 2, 3, 4, 5, 6])
        annotations[0]["market_top2_support"] = True
        annotations[0]["late_snapshot_available"] = False
        with self.assertRaises(ValueError):
            summarize_venue_diagnostics(candidates, annotations)

    def test_incomplete_day_fails_closed(self):
        candidates, annotations = complete_day("2026-09-15", [1, 2, 3, 4, 5, 6])
        with self.assertRaises(ValueError):
            summarize_venue_diagnostics(candidates[:-1], annotations)


if __name__ == "__main__":
    unittest.main()
