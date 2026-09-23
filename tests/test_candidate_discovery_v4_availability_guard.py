# -*- coding: utf-8 -*-
import hashlib
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
        "generated_at_jst": "2026-09-21T10:03:12+09:00",
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": "2026-09-21",
            "completed_at_jst": "2026-09-21T10:03:12+09:00",
            "all_frozen_rows_pre_deadline": True,
        },
        "feed": feed,
    }


def snapshot():
    evidence_sources = []
    races = []
    for idx, row in enumerate(artifact()["feed"], 1):
        race_id = row["race_id"]
        venue_id = row["venue_id"]
        race_no = int(race_id.split("_")[2])
        evidence_id = f"race-{race_id}"
        evidence_sources.append(
            {
                "evidence_id": evidence_id,
                "observed_at": "2026-09-21T09:55:00+09:00",
                "source_updated_at": None,
                "source_url": (
                    "https://www.boatrace.jp/owpc/pc/race/racelist"
                    f"?hd=20260921&jcd={venue_id}&rno={race_no}"
                ),
                "source_content_sha256": f"{idx:064x}",
            }
        )
        races.append(
            {
                "race_id": race_id,
                "venue_id": venue_id,
                "status": "active",
                "scope": "race",
                "evidence_id": evidence_id,
                "evidence_binding_sha256": hashlib.sha256(
                    race_id.encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "contract": "candidate_discovery_v4_official_availability_snapshot_v1",
        "target_date": "2026-09-21",
        "evidence_sources": evidence_sources,
        "races": races,
    }


def add_venue_unavailable_evidence(status, venue_id, evidence_id=None):
    evidence_id = evidence_id or f"venue-{venue_id}-cancel"
    status["evidence_sources"].append(
        {
            "evidence_id": evidence_id,
            "observed_at": "2026-09-21T09:00:00+09:00",
            "source_updated_at": "2026-09-21T08:25:00+09:00",
            "source_url": "https://www.boatrace.jp/owpc/pc/race/index?hd=20260921",
            "source_content_sha256": "f" * 64,
        }
    )
    return evidence_id


class AvailabilityGuardTests(unittest.TestCase):
    def test_all_active_core_passes_with_distinct_race_evidence(self):
        result = evaluate_availability_guard(artifact(), snapshot())
        self.assertTrue(result["eligible_under_guard"])
        self.assertEqual(result["decision"], "PASS_ACTIVE_CORE")
        self.assertEqual(result["blocked_core_races"], [])
        self.assertEqual(result["evidence_source_count"], 6)
        self.assertEqual(len(result["core_evidence"]), 6)
        self.assertFalse(result["replacement_candidates_generated"])
        self.assertFalse(result["ranking_changed"])
        self.assertFalse(result["purchase_action"])

    def test_pre_freeze_cancelled_selected_venue_blocks_without_replacement(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "02")
        cancelled = next(row for row in status["races"] if row["venue_id"] == "02")
        cancelled["status"] = "cancelled_postponed"
        cancelled["scope"] = "venue"
        cancelled["evidence_id"] = evidence_id
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(result["decision"], "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE")
        self.assertEqual(len(result["blocked_core_races"]), 1)
        self.assertEqual(result["blocked_core_races"][0]["venue_id"], "02")
        self.assertEqual(result["blocked_core_races"][0]["race_id"], "20260921_02_08")
        self.assertEqual(result["blocked_core_races"][0]["evidence_id"], evidence_id)
        self.assertFalse(result["replacement_candidates_generated"])
        self.assertFalse(result["ranking_changed"])

    def test_malformed_formal_core_orders_fail_closed(self):
        bad = artifact()
        bad["feed"][0]["tickets"] = [{"core_order": 1, "ticket": "1-2-3"}]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "exact orders 1 and 2"):
            evaluate_availability_guard(bad, snapshot())

    def test_formal_core_daily_rank_must_be_exactly_one_to_six(self):
        bad = artifact()
        bad["feed"][5]["daily_rank"] = 5
        with self.assertRaisesRegex(V4AvailabilityGuardError, "daily_rank must be exactly 1..6"):
            evaluate_availability_guard(bad, snapshot())

    def test_formal_core_race_identity_must_match_date_venue_and_valid_venue_range(self):
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

        bad = artifact()
        bad["feed"][0]["race_id"] = "20260921_99_05"
        bad["feed"][0]["venue_id"] = "99"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "invalid core venue_id"):
            evaluate_availability_guard(bad, snapshot())

    def test_venue_level_unavailable_can_block_but_venue_active_cannot_pass(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "02")
        row = next(item for item in status["races"] if item["race_id"] == "20260921_02_08")
        row["status"] = "cancelled_postponed"
        row["scope"] = "venue"
        row["evidence_id"] = evidence_id
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(result["blocked_core_races"][0]["scope"], "venue")

        status = snapshot()
        status["races"][0]["scope"] = "venue"
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "non-race active status is insufficient",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_partial_venue_race_range_blocks_only_covered_core_race(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "09", "venue-09-from-8")
        venue09 = [row for row in status["races"] if row["venue_id"] == "09"]
        r7 = next(row for row in venue09 if row["race_id"].endswith("_07"))
        r8 = next(row for row in venue09 if row["race_id"].endswith("_08"))
        r8["status"] = "cancelled_postponed"
        r8["scope"] = "venue_race_range"
        r8["cancel_from_race_no"] = 8
        r8["evidence_id"] = evidence_id

        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(len(result["blocked_core_races"]), 1)
        self.assertEqual(result["blocked_core_races"][0]["race_id"], "20260921_09_08")
        self.assertEqual(result["blocked_core_races"][0]["scope"], "venue_race_range")
        self.assertEqual(result["blocked_core_races"][0]["cancel_from_race_no"], 8)
        self.assertEqual(r7["status"], "active")

    def test_partial_venue_range_cannot_block_race_before_range(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "09", "venue-09-from-8")
        r7 = next(row for row in status["races"] if row["race_id"] == "20260921_09_07")
        r7["status"] = "cancelled_postponed"
        r7["scope"] = "venue_race_range"
        r7["cancel_from_race_no"] = 8
        r7["evidence_id"] = evidence_id
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "does not cover core race",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_partial_venue_range_evidence_may_be_shared_for_covered_same_venue_races(self):
        status = snapshot()
        # Use a synthetic same-venue pair at R8/R9 so one official range source can
        # legitimately cover both selected races.
        art = artifact()
        art["feed"][3]["race_id"] = "20260921_09_09"
        art["feed"][3]["venue_id"] = "09"
        status = snapshot()
        status["races"][3]["race_id"] = "20260921_09_09"
        status["races"][3]["venue_id"] = "09"
        status["evidence_sources"][3]["source_url"] = (
            "https://www.boatrace.jp/owpc/pc/race/racelist?hd=20260921&jcd=09&rno=9"
        )
        evidence_id = add_venue_unavailable_evidence(status, "09", "venue-09-from-8")
        for row in status["races"]:
            if row["venue_id"] == "09":
                row["status"] = "cancelled_postponed"
                row["scope"] = "venue_race_range"
                row["cancel_from_race_no"] = 8
                row["evidence_id"] = evidence_id
        result = evaluate_availability_guard(art, status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(len(result["blocked_core_races"]), 2)

    def test_unknown_availability_scope_fails_closed(self):
        status = snapshot()
        status["races"][0]["scope"] = "inferred"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "unknown availability scope"):
            evaluate_availability_guard(artifact(), status)

    def test_generated_timestamp_must_match_freeze_completion(self):
        bad = artifact()
        bad["freeze_provenance"]["completed_at_jst"] = (
            "2026-09-21T10:03:13+09:00"
        )
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "must equal freeze completion",
        ):
            evaluate_availability_guard(bad, snapshot())

    def test_evidence_observed_after_freeze_is_rejected(self):
        status = snapshot()
        status["evidence_sources"][0]["observed_at"] = "2026-09-21T10:04:00+09:00"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "observed after artifact freeze"):
            evaluate_availability_guard(artifact(), status)

    def test_missing_core_race_fails_closed(self):
        status = snapshot()
        removed = status["races"][0]["race_id"]
        status["races"] = [row for row in status["races"] if row["race_id"] != removed]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "missing core race"):
            evaluate_availability_guard(artifact(), status)

    def test_unexpected_non_core_race_fails_closed(self):
        status = snapshot()
        status["evidence_sources"].append(
            {
                "evidence_id": "extra-race",
                "observed_at": "2026-09-21T09:55:00+09:00",
                "source_updated_at": None,
                "source_url": (
                    "https://www.boatrace.jp/owpc/pc/race/racelist"
                    "?hd=20260921&jcd=01&rno=1"
                ),
                "source_content_sha256": "e" * 64,
            }
        )
        status["races"].append(
            {
                "race_id": "20260921_01_01",
                "venue_id": "01",
                "status": "active",
                "scope": "race",
                "evidence_id": "extra-race",
                "evidence_binding_sha256": hashlib.sha256(
                    b"20260921_01_01"
                ).hexdigest(),
            }
        )
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "unexpected non-core race",
        ):
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

    def test_optional_source_update_after_observation_fails_closed(self):
        status = snapshot()
        status["evidence_sources"][0]["source_updated_at"] = "2026-09-21T09:56:00+09:00"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "source update time"):
            evaluate_availability_guard(artifact(), status)

    def test_missing_or_malformed_source_digest_fails_closed(self):
        status = snapshot()
        del status["evidence_sources"][0]["source_content_sha256"]
        with self.assertRaisesRegex(V4AvailabilityGuardError, "source_content_sha256"):
            evaluate_availability_guard(artifact(), status)

        status = snapshot()
        status["evidence_sources"][0]["source_content_sha256"] = "A" * 64
        with self.assertRaisesRegex(V4AvailabilityGuardError, "lowercase SHA-256 hex"):
            evaluate_availability_guard(artifact(), status)

        status = snapshot()
        status["evidence_sources"][0]["source_content_sha256"] = "abc"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "lowercase SHA-256 hex"):
            evaluate_availability_guard(artifact(), status)

    def test_non_official_source_is_rejected(self):
        status = snapshot()
        status["evidence_sources"][0]["source_url"] = "https://example.com/status"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "BOAT RACE official"):
            evaluate_availability_guard(artifact(), status)

    def test_missing_or_unknown_evidence_reference_fails_closed(self):
        status = snapshot()
        status["races"][0]["evidence_id"] = "missing"
        with self.assertRaisesRegex(V4AvailabilityGuardError, "evidence_id missing or unknown"):
            evaluate_availability_guard(artifact(), status)

    def test_duplicate_evidence_id_fails_closed(self):
        status = snapshot()
        status["evidence_sources"].append(deepcopy(status["evidence_sources"][0]))
        with self.assertRaisesRegex(V4AvailabilityGuardError, "duplicate availability evidence_id"):
            evaluate_availability_guard(artifact(), status)

    def test_active_race_requires_row_binding_digest(self):
        status = snapshot()
        del status["races"][0]["evidence_binding_sha256"]
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "evidence_binding_sha256 required",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_same_venue_pre_freeze_source_may_bind_distinct_active_rows(self):
        status = snapshot()
        venue09 = [
            row for row in status["races"] if row["venue_id"] == "09"
        ]
        self.assertEqual(len(venue09), 2)
        first_id = venue09[0]["evidence_id"]
        second_id = venue09[1]["evidence_id"]
        venue09[1]["evidence_id"] = first_id
        status["evidence_sources"] = [
            source
            for source in status["evidence_sources"]
            if source["evidence_id"] != second_id
        ]
        shared = next(
            source
            for source in status["evidence_sources"]
            if source["evidence_id"] == first_id
        )
        shared["source_url"] = (
            "https://www.boatrace.jp/owpc/pc/race/raceindex"
            "?hd=20260921&jcd=09"
        )
        result = evaluate_availability_guard(artifact(), status)
        self.assertTrue(result["eligible_under_guard"])
        bound = [
            item["evidence_binding_sha256"]
            for item in result["core_evidence"]
            if item["venue_id"] == "09"
        ]
        self.assertEqual(len(set(bound)), 2)

    def test_same_venue_source_reuse_rejects_duplicate_row_binding(self):
        status = snapshot()
        venue09 = [
            row for row in status["races"] if row["venue_id"] == "09"
        ]
        first_id = venue09[0]["evidence_id"]
        second_id = venue09[1]["evidence_id"]
        venue09[1]["evidence_id"] = first_id
        venue09[1]["evidence_binding_sha256"] = venue09[0][
            "evidence_binding_sha256"
        ]
        status["evidence_sources"] = [
            source
            for source in status["evidence_sources"]
            if source["evidence_id"] != second_id
        ]
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "evidence source reused across incompatible core races",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_race_active_evidence_cannot_be_reused_for_another_core_race(self):
        status = snapshot()
        status["races"][1]["evidence_id"] = status["races"][0]["evidence_id"]
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "evidence source reused across incompatible core races",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_venue_wide_unavailable_evidence_may_be_shared_with_same_venue(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "09")
        venue09 = [row for row in status["races"] if row["venue_id"] == "09"]
        for row in venue09:
            row["status"] = "cancelled_postponed"
            row["scope"] = "venue"
            row["evidence_id"] = evidence_id
        result = evaluate_availability_guard(artifact(), status)
        self.assertFalse(result["eligible_under_guard"])
        self.assertEqual(len(result["blocked_core_races"]), 2)

    def test_venue_wide_unavailable_cannot_coexist_with_active_core_at_same_venue(self):
        status = snapshot()
        evidence_id = add_venue_unavailable_evidence(status, "09")
        venue09 = [row for row in status["races"] if row["venue_id"] == "09"]
        venue09[0]["status"] = "cancelled_postponed"
        venue09[0]["scope"] = "venue"
        venue09[0]["evidence_id"] = evidence_id
        with self.assertRaisesRegex(
            V4AvailabilityGuardError,
            "inconsistent venue-level unavailable evidence",
        ):
            evaluate_availability_guard(artifact(), status)

    def test_purchase_enabled_artifact_is_rejected(self):
        bad = artifact()
        bad["purchase_action"] = True
        with self.assertRaisesRegex(V4AvailabilityGuardError, "purchase_action"):
            evaluate_availability_guard(bad, snapshot())


if __name__ == "__main__":
    unittest.main()
