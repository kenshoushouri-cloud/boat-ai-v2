"""Offline-only provenance/coverage audit: never certifies Forward or BUY."""
from __future__ import annotations
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from v5.offline_day_evidence_coverage import (
    DayEvidenceRow, audit_day_evidence_coverage,
    APPROVED_POSITIVE_SOURCE_SCHEMAS,
)

JST = ZoneInfo("Asia/Tokyo")
DAY = date(2026, 5, 1)
A, B = "20260501_24_11", "20260501_24_12"


def local(hour, minute=0):
    return datetime(2026, 5, 1, hour, minute, tzinfo=JST)


def row(rid=A, decision="FROZEN", **overrides):
    template = DayEvidenceRow(
        rid, decision, local(17, 35), local(17, 41),
        (4001, 4002, 4003, 4004, 4005, 4006),
        "official_beforeinfo_historical", local(17, 31), local(17, 32),
        local(18, 20), "claim-postrace-official",
    )
    return replace(template, **overrides)


def check(inventory=(A,), ledger=None, frozen=(A,)):
    return audit_day_evidence_coverage(DAY, inventory, "caller-roster-not-certified",
                                       (row(),) if ledger is None else ledger, frozen)


class TestDayEvidenceCoverage(unittest.TestCase):
    def test_consistent_roster_does_not_prove_official_coverage(self):
        result = check()
        self.assertTrue(result.caller_inventory_matches_decision_ledger)
        self.assertEqual((result.inventory_count, result.frozen_count), (1, 1))
        self.assertTrue(result.rows[0].predecision_timestamps_consistent)
        self.assertFalse(result.inventory_independently_verified)
        self.assertFalse(result.original_first_observation_verified)
        self.assertFalse(result.forward_eligible)
        self.assertFalse(result.buy_eligible)
        self.assertIn("OFFICIAL_POSITIVE_SOURCE_UNAPPROVED", result.rows[0].predecision_reasons)
        self.assertIn("RESULT_ORIGIN_INDEPENDENTLY_UNVERIFIED", result.rows[0].result_reasons)
        self.assertEqual(APPROVED_POSITIVE_SOURCE_SCHEMAS, frozenset())

    def test_missing_race_cannot_be_silently_removed_from_denominator(self):
        result = check(inventory=(A, B))
        self.assertFalse(result.caller_inventory_matches_decision_ledger)
        self.assertEqual(result.unaccounted_ids, (B,))
        self.assertEqual(result.inventory_count, 2)
        self.assertEqual(len(result.rows), 1)

    def test_feature_missing_is_accounted_with_no_buy_or_pending(self):
        result = check(inventory=(A, B), ledger=(row(), row(B, "PENDING")))
        self.assertTrue(result.caller_inventory_matches_decision_ledger)
        self.assertEqual(result.pending_count, 1)
        self.assertIn("PREDECISION_PENDING", result.rows[1].predecision_reasons)
        self.assertFalse(result.rows[1].buy_eligible)
        alt = check(inventory=(A, B), ledger=(row(), row(B, "NO_BUY")))
        self.assertEqual(alt.no_buy_count, 1)
        self.assertTrue(alt.caller_inventory_matches_decision_ledger)

    def test_late_historical_capture_cannot_be_predeadline(self):
        late = row(exhibition_snapshot_at=datetime(2026, 8, 15, 13, 54, tzinfo=JST),
                   exhibition_first_observed_at=datetime(2026, 8, 15, 13, 54, tzinfo=JST))
        result = check(ledger=(late,))
        self.assertFalse(result.rows[0].predecision_timestamps_consistent)
        self.assertIn("EXHIBITION_AFTER_DECISION_CUTOFF", result.rows[0].predecision_reasons)
        self.assertFalse(result.buy_eligible)

    def test_oomura_retrospective_snapshot_post_deadline_without_cutoff(self):
        # Archived row is a research fixture, not the original DB object.
        # No frozen V5 selection, no independently proven 6-boat source.
        late = row(
            B, "PENDING", decision_cutoff_at=None, six_lanes=None,
            six_lane_source_contract=None, exhibition_first_observed_at=None,
            exhibition_snapshot_at=datetime(2026, 8, 15, 13, 54, 54, tzinfo=JST),
            result_first_observed_at=None, result_source_ref=None,
        )
        audit = check(inventory=(B,), ledger=(late,), frozen=())
        one = audit.rows[0]
        self.assertEqual(one.race_id, "20260501_24_12")
        self.assertEqual(audit.pending_count, 1)
        self.assertIn("DECISION_CLOCK_INVALID", one.predecision_reasons)
        self.assertIn("ORIGINAL_FIRST_OBSERVATION_UNKNOWN", one.predecision_reasons)
        self.assertIn("EXHIBITION_SNAPSHOT_RECORDED_AFTER_DEADLINE",
                      one.predecision_reasons)
        self.assertIn("OFFICIAL_POSITIVE_SOURCE_UNAPPROVED", one.predecision_reasons)
        self.assertIn("INDEPENDENT_SIX_LANE_POSITIVE_EVIDENCE_MISSING",
                      one.predecision_reasons)
        self.assertIn("RESULT_FIRST_OBSERVATION_UNKNOWN", one.result_reasons)
        self.assertFalse(one.predecision_timestamps_consistent)
        self.assertFalse(audit.inventory_independently_verified)
        self.assertFalse(audit.buy_eligible)

    def test_missing_first_observation_and_result_timestamp_are_not_invented(self):
        result = check(ledger=(row(exhibition_first_observed_at=None,
                                   result_first_observed_at=None),))
        self.assertIn("ORIGINAL_FIRST_OBSERVATION_UNKNOWN", result.rows[0].predecision_reasons)
        self.assertIn("RESULT_FIRST_OBSERVATION_UNKNOWN", result.rows[0].result_reasons)
        self.assertFalse(result.rows[0].predecision_timestamps_consistent)

    def test_result_seen_before_deadline_flagged_separately(self):
        result = check(ledger=(row(result_first_observed_at=local(17, 39)),))
        self.assertTrue(result.rows[0].predecision_timestamps_consistent)
        self.assertIn("RESULT_OBSERVATION_BEFORE_DEADLINE_SUSPECT", result.rows[0].result_reasons)

    def test_frozen_disposition_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "FROZEN_DECISION_MISMATCH"):
            check(ledger=(row(decision="NO_BUY"),))
        with self.assertRaisesRegex(ValueError, "FROZEN_RACE_NOT_IN_LEDGER"):
            check(ledger=(row(B, "NO_BUY"),), frozen=(A,))

    def test_duplicate_and_cross_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RACE_ID"):
            check(inventory=(A, A))
        with self.assertRaisesRegex(ValueError, "CROSS_DAY_RACE_ID"):
            check(inventory=(A, "20260502_24_12"))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RACE_ID"):
            check(ledger=(row(), row()))

    def test_timezone_offsets_are_compared_as_instants(self):
        UTC = timezone.utc
        # 17:31 JST = 08:31 UTC, before 17:35 JST cutoff.
        r = row(exhibition_first_observed_at=local(17, 31).astimezone(UTC),
                exhibition_snapshot_at=local(17, 32).astimezone(UTC))
        result = check(ledger=(r,))
        self.assertTrue(result.rows[0].predecision_timestamps_consistent)
        self.assertFalse(result.rows[0].historical_provenance_verified)

    def test_naive_dates_late_cutoff_and_bad_six_lanes(self):
        r = row(decision_cutoff_at=local(17, 43),
                six_lanes=(1, 1, 2, 3, 4, 5),
                exhibition_snapshot_at=local(17, 44))
        result = check(ledger=(r,))
        self.assertIn("DECISION_CLOCK_INVALID", result.rows[0].predecision_reasons)
        self.assertIn("INDEPENDENT_SIX_LANE_POSITIVE_EVIDENCE_MISSING", result.rows[0].predecision_reasons)
        self.assertFalse(result.rows[0].predecision_timestamps_consistent)
        r2 = row(exhibition_first_observed_at=datetime(2026, 5, 1, 17, 31))
        self.assertIn("ORIGINAL_FIRST_OBSERVATION_UNKNOWN",
                      check(ledger=(r2,)).rows[0].predecision_reasons)

    def test_undefined_inventory_and_empty_roster_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "INVENTORY_OR_LEDGER_INVALID"):
            check(inventory=())
        with self.assertRaisesRegex(ValueError, "INVENTORY_OR_LEDGER_INVALID"):
            audit_day_evidence_coverage(DAY, (A,), "", (row(),), (A,))
        with self.assertRaisesRegex(ValueError, "CROSS_DAY_RACE_ID"):
            check(frozen=("20260502_24_12",))


if __name__ == "__main__":
    unittest.main()
