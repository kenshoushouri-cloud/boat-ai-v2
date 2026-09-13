# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.candidate_discovery_market_annotation_contract import (
    V4_FEED_CONTRACT,
    annotate_feed,
    market_top2,
)


CORE = [
    (1, "20260913_11_02", "11", 2, "A", "2-3-5"),
    (2, "20260913_08_08", "08", 8, "A", "2-3-6"),
    (3, "20260913_22_03", "22", 3, "B", "3-4-5"),
    (4, "20260913_19_05", "19", 5, "B", "1-4-3"),
    (5, "20260913_07_07", "07", 7, "C", "1-3-4"),
    (6, "20260913_08_05", "08", 5, "C", "2-5-1"),
]


def feed_doc(date_str: str = "2026-09-13", *, contract: str = "candidate_discovery_main_feed_v1"):
    rows = []
    for rank, rid, venue, rno, tier, ticket in CORE:
        rows.append({
            "daily_rank": rank,
            "race_id": rid.replace("20260913", date_str.replace("-", "")),
            "race_date": date_str,
            "venue_id": venue,
            "race_no": rno,
            "tier": tier,
            "legacy_carryover": False,
            "tickets": [
                {"core_order": 1, "ticket": ticket, "source": ["DISCOVERY_CORE"]},
                {"core_order": 2, "ticket": "6-5-4", "source": ["DISCOVERY_CORE"]},
            ],
        })
    rows.append({
        "daily_rank": 99,
        "race_id": date_str.replace("-", "") + "_10_01",
        "race_date": date_str,
        "venue_id": "10",
        "race_no": 1,
        "tier": "LEGACY",
        "legacy_carryover": True,
        "tickets": [{"core_order": None, "ticket": "1-6-5", "source": ["LEGACY"]}],
    })
    return {
        "contract": contract,
        "feed": rows,
        "purchase_action": False,
        "production_behavior_changed": False,
    }


def odds_with_top2(first: str, second: str):
    tickets = ["-".join(map(str, p)) for p in itertools.permutations(range(1, 7), 3)]
    odds = {ticket: 100.0 for ticket in tickets}
    odds[first] = 2.0
    odds[second] = 3.0
    return odds


def snapshot(first: str, second: str, *, lead=5.0, spread=0.5):
    return {
        "lead_minutes": lead,
        "spread_seconds": spread,
        "odds": odds_with_top2(first, second),
    }


class MarketAnnotationContractTest(unittest.TestCase):
    def test_20260913_baseline_wiring_is_never_prospective(self):
        feed = feed_doc("2026-09-13")
        frozen_copy = copy.deepcopy(feed)
        market = {
            "20260913_08_08": snapshot("2-3-6", "2-6-3", lead=4.824),
            "20260913_19_05": snapshot("1-3-4", "1-4-3", lead=5.302),
            "20260913_08_05": snapshot("1-2-5", "2-1-5", lead=5.179),
        }
        out = annotate_feed(feed, market)
        self.assertEqual(out["core_top1"], 6)
        self.assertEqual(out["late_available"], 3)
        self.assertEqual(out["top2_supported"], 2)
        self.assertEqual(out["prospective_supported"], 0)
        self.assertFalse(out["exact_v4_source"])
        self.assertTrue(all(row["counts_as_prospective"] is False for row in out["rows"]))
        self.assertEqual(feed, frozen_copy, "annotation must not mutate immutable feed")

    def test_true_v4_after_start_counts_as_prospective(self):
        feed = feed_doc("2026-09-14", contract=V4_FEED_CONTRACT)
        market = {
            "20260914_08_08": snapshot("2-3-6", "2-6-3"),
            "20260914_19_05": snapshot("1-3-4", "1-4-3"),
            "20260914_08_05": snapshot("1-2-5", "2-1-5"),
        }
        out = annotate_feed(feed, market)
        self.assertTrue(out["exact_v4_source"])
        self.assertEqual(out["top2_supported"], 2)
        self.assertEqual(out["prospective_supported"], 2)

    def test_non_v4_feed_after_start_cannot_count_as_prospective(self):
        feed = feed_doc("2026-09-14", contract="candidate_discovery_main_feed_v1")
        market = {"20260914_08_08": snapshot("2-3-6", "2-6-3")}
        out = annotate_feed(feed, market)
        self.assertFalse(out["exact_v4_source"])
        self.assertEqual(out["prospective_supported"], 0)
        self.assertTrue(all(row["counts_as_prospective"] is False for row in out["rows"]))

    def test_outside_late_window_or_bad_spread_is_unavailable(self):
        self.assertIsNone(market_top2(snapshot("1-2-3", "1-3-2", lead=7.001)))
        self.assertIsNone(market_top2(snapshot("1-2-3", "1-3-2", lead=-0.001)))
        self.assertIsNone(market_top2(snapshot("1-2-3", "1-3-2", spread=60.001)))

    def test_incomplete_market_is_unavailable(self):
        snap = snapshot("1-2-3", "1-3-2")
        snap["odds"].pop("6-5-4")
        self.assertIsNone(market_top2(snap))

    def test_feed_requires_fail_closed_flags(self):
        bad = feed_doc()
        bad["purchase_action"] = True
        with self.assertRaises(ValueError):
            annotate_feed(bad, {})

    def test_prospective_pg_runner_is_hash_pinned_read_only_and_outcome_free(self):
        text = (ROOT / "research/candidate_discovery_market_forward_annotate_pg.py").read_text(encoding="utf-8").lower()
        self.assertIn("candidate_v4_freeze_sha256", text)
        self.assertIn("candidate_v4_freeze_run_id", text)
        self.assertIn("candidate_v4_freeze_artifact_id", text)
        self.assertIn("freeze sha-256 mismatch", text)
        self.assertIn("set transaction read only", text)
        self.assertIn("v2_realtime_odds_snapshots", text)
        self.assertIn("v4_feed_contract", text)
        self.assertIn("unexpected source contract", text)
        self.assertNotIn("20260913_11_02", text)
        for forbidden in (
            "v2_results", "trifecta_payout_yen", "result_status", "race_status",
            "delete from ", "insert into ", "update v2_", "alter table ",
            "drop table ", "truncate ", "vacuum ", "create table "
        ):
            self.assertNotIn(forbidden, text, forbidden)


if __name__ == "__main__":
    unittest.main()
