# -*- coding: utf-8 -*-
import unittest
from copy import deepcopy

from research.candidate_discovery_v4_availability_guard import (
    V4AvailabilityGuardError,
    evaluate_availability_guard,
)


def artifact():
    feed = []
    core = [
        ("20260921_10_05", "10"),
        ("20260921_17_07", "17"),
        ("20260921_02_08", "02"),
        ("20260921_09_07", "09"),
        ("20260921_12_07", "12"),
        ("20260921_09_08", "09"),
    ]
    for rank, (race_id, venue) in enumerate(core, 1):
        feed.append(
            {
                "race_id": race_id,
                "venue_id": venue,
                "daily_rank": rank,
                "tickets": [
                    {"core_order": 1, "ticket": "1-2-3"},
                    {"core_order": 2, "ticket": "1-3-2"},
                ],
            }
        )
    return {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "generated_at": "2026-09-21T10:03:12+09:00",
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": "2026-09-21",
            "all_frozen_rows_pre_deadline": True,
        },
        "feed": feed,
    }


def snapshot():
    return {
        "contract": "candidate_discovery_v4_official_availability_snapshot_v1",
        "target_date": "2026-09-21",
        "observed_at": "2026-09-21T09:55:00+09:00",
        "source_updated_at": "2026-09-21T08:25:00+09:00",
        "source_url": "https://www.boatrace.jp/owpc/pc/race/index?hd=20260921",
        "source_content_sha256": "a" * 64,
        "races": [
            {
                "race_id": row["race_id"],
                "venue_id": row["venue_id"],
                "status": "active",
                "scope": "race",
            }
            for row in artifact()["feed"]
        ],
    }


class AvailabilityGuardTests(unittest.TestCase):
    def test_all_active_core_passes_without_reranking(self):
        result = evaluate_availability_guard(artifact(), snapshot())
        self.assertTrue(result["eligible_under_guard"])
        self.assertEqual(result["decision"], "PASS_ACTIVE_CORE")
        self.assertEqual(result["blocked_core_races"], [])
        self.assertFalse(result["replacement_candidates_generated"])
        self.assertFalse(result["ranking_changed"])
        self.assertFalse(result["purchase_action"])

    def test_pre_freeze_cancelled_selected_venue_blocks_without_replacement(self):
        status = snapshot()
        cancelled = next(row for row in status["races"] if row["venue_id"] == "02")
        cancelled["status"] = "cancelled_postponed"
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(result["decision"], "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE")
        self.assertEqual(len(result["blocked_core_races"]), 1)
        self.assertEqual(result["blocked_core_races"][0]["venue_id"], "02")
        self.assertEqual(result["blocked_core_races"][0]["race_id"], "20260921_02_08")
        self.assertFalse(result["replacement_candidates_generated"])
        self.assertFalse(result["ranking_changed"])

    def test_malformed_formal_core_orders_fail_closed(self):
        bad = artifact()
        bad["feed"][0]["tickets"] = [
            {"core_order": 1, "ticket": "1-2-3"},
        ]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "exact orders 1 and 2"):
            evaluate_availability_guard(bad, snapshot())

    def test_formal_core_daily_rank_must_be_exactly_one_to_six(self):
        bad = artifact()
        bad["feed"][5]["daily_rank"] = 5
        with self.assertRaisesRegex(V4AvailabilityGuardError, "daily_rank must be exactly 1..6"):
            evaluate_availability_guard(bad, snapshot())

    def test_formal_core_race_identity_must_match_date_and_venue(self):
        bad = artifact()
        bad["feed"][0]["race_id"] = "20260920_10_05"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "target_date mismatch"):
            evaluate_availability_guard(bad, snapshot())

        bad = artifact()
        bad["feed"][0]["race_id"] = "20260921_11_05"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "race_id venue mismatch"):
            evaluate_availability_guard(bad, snapshot())

        bad = artifact()
        bad["feed"][0]["race_id"] = "20260921_10_13"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "malformed core race_id"):
            evaluate_availability_guard(bad, snapshot())

    def test_venue_level_unavailable_can_block_but_venue_active_cannot_pass(self):
        status = snapshot()
        row = next(item for item in status["races"] if item["race_id"] == "20260921_02_08")
        row["status"] = "cancelled_postponed"
        row["scope"] = "venue"
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(result["blocked_core_races"][0]["scope"], "venue")

        status = snapshot()
        status["races"][0]["scope"] = "venue"
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "venue-level active status is insufficient",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_unknown_availability_scope_fails_closed(self):
        status = snapshot()
        status["races"][0]["scope"] = "inferred"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "unknown availability scope"):
            evaluate_availability_guard(artifact(), status)

    def test_snapshot_observed_after_freeze_is_rejected(self):
        status = snapshot()
        status["observed_at"] = "2026-09-21T10:04:00+09:00"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "observed after artifact freeze"):
            evaluate_availability_guard(artifact(), status)

    def test_missing_core_venue_fails_closed(self):
        status = snapshot()
        removed = status["races"][0]["race_id"]
        status["races"] = [row for row in status["races"] if row["race_id"] != removed]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "missing core race"):
            evaluate_availability_guard(artifact(), status)

    def test_unknown_status_fails_closed(self):
        status = snapshot()
        status["races"][0]["status"] = "unknown"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "unknown availability status"):
            evaluate_availability_guard(artifact(), status)

    def test_duplicate_race_fails_closed(self):
        status = snapshot()
        status["races"].append(deepcopy(status["races"][0]))
        with self.assertRaisesRegex(V4AvailabilityGuardError, "duplicate availability race_id"):
            evaluate_availability_guard(artifact(), status)

    def test_race_level_status_can_differ_within_same_venue(self):
        status = snapshot()
        venue09 = [row for row in status["races"] if row["venue_id"] == "09"]
        self.assertEqual(len(venue09), 2)
        venue09[0]["status"] = "cancelled_postponed"
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(len(result["blocked_core_races"]), 1)
        self.assertEqual(result["blocked_core_races"][0]["race_id"], venue09[0]["race_id"])

    def test_race_venue_mismatch_fails_closed(self):
        status = snapshot()
        status["races"][0]["venue_id"] = "24"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "venue mismatch"):
            evaluate_availability_guard(artifact(), status)

    def test_source_update_after_observation_fails_closed(self):
        status = snapshot()
        status["source_updated_at"] = "2026-09-21T09:56:00+09:00"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "source update time"):
            evaluate_availability_guard(artifact(), status)

    def test_missing_or_malformed_source_digest_fails_closed(self):
        status = snapshot()
        del status["source_content_sha256"]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "source_content_sha256"):
            evaluate_availability_guard(artifact(), status)

        status = snapshot()
        status["source_content_sha256"] = "A" * 64
        with self.assertRaisesRegex(V4AvailabilityGuardError, "lowercase SHA-256 hex"):
            evaluate_availability_guard(artifact(), status)

        status = snapshot()
        status["source_content_sha256"] = "abc"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "lowercase SHA-256 hex"):
            evaluate_availability_guard(artifact(), status)

    def test_non_official_source_is_rejected(self):
        status = snapshot()
        status["source_url"] = "https://example.com/status"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "BOAT RACE official"):
            evaluate_availability_guard(artifact(), status)

    def test_purchase_enabled_artifact_is_rejected(self):
        bad = artifact()
        bad["purchase_action"] = True
        with self.assertRaisesRegex(V4AvailabilityGuardError, "purchase_action"):
            evaluate_availability_guard(bad, snapshot())


if __name__ == "__main__":
    unittest.main()
