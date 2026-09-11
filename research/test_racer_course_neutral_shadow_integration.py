from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from research.racer_course_neutral_forward_contract import CourseLaneEvidence
from research.racer_course_neutral_shadow_integration import (
    SHADOW_TABLE_NAME,
    WRITE_POLICY,
    CourseNeutralShadowIntegrationError,
    prepare_shadow_row,
)
from research.racer_course_neutral_shadow_payload import build_shadow_payload

JST = ZoneInfo("Asia/Tokyo")


class CourseNeutralShadowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.race_date = date(2026, 9, 12)
        self.base = {lane: float(lane) / 10.0 for lane in range(1, 7)}
        self.racers = {lane: 7000 + lane for lane in range(1, 7)}
        self.deadline = datetime(2026, 9, 12, 10, 0, tzinfo=JST)
        self.observed = datetime(2026, 9, 12, 8, 0, tzinfo=JST)

    def evidence(self, lane: int, top3: float) -> CourseLaneEvidence:
        return CourseLaneEvidence(
            racer_number=self.racers[lane],
            lane=lane,
            course=lane,
            race_date=self.race_date,
            top3_rate=top3,
            created_at=datetime(2026, 9, 12, 7, 30, tzinfo=JST),
            deadline_at=self.deadline,
        )

    def payload(self, *, missing_lane: int | None = None):
        evidence = {
            lane: self.evidence(lane, 35 + lane * 3)
            for lane in range(1, 7)
            if lane != missing_lane
        }
        return build_shadow_payload(
            race_id="20260912_01_01",
            race_date=self.race_date,
            base_raw=self.base,
            expected_racers=self.racers,
            evidence_by_lane=evidence,
        )

    def test_persistence_namespace_and_policy_are_fixed(self) -> None:
        self.assertEqual(SHADOW_TABLE_NAME, "v2_racer_course_neutral_shadow")
        self.assertEqual(WRITE_POLICY, "FIRST_WRITE_WINS_DO_NOTHING")

    def test_valid_payload_becomes_immutable_row_contract(self) -> None:
        row = prepare_shadow_row(
            payload=self.payload(), observed_at=self.observed, deadline_at=self.deadline
        )
        self.assertEqual(row.immutable_key, ("20260912_01_01", "course-neutral-missing-v1"))
        self.assertEqual(row.write_policy, WRITE_POLICY)
        self.assertEqual(len(row.ticket_order), 120)
        self.assertEqual(len(row.base_trifecta), 120)
        self.assertEqual(len(row.adjusted_trifecta), 120)
        self.assertAlmostEqual(sum(row.base_trifecta), 1.0, places=9)
        self.assertAlmostEqual(sum(row.adjusted_trifecta), 1.0, places=9)

    def test_missing_lane_stays_neutral_in_persistence_contract(self) -> None:
        row = prepare_shadow_row(
            payload=self.payload(missing_lane=4), observed_at=self.observed, deadline_at=self.deadline
        )
        idx = 3
        self.assertFalse(row.usable_mask[idx])
        self.assertIsNone(row.course_top3[idx])
        self.assertEqual(row.unavailable_reason[idx], "missing_required_row")
        self.assertEqual(row.course_z[idx], 0.0)
        self.assertEqual(row.adjusted_raw[idx], row.base_raw[idx])

    def test_exact_0815_is_allowed(self) -> None:
        row = prepare_shadow_row(
            payload=self.payload(),
            observed_at=datetime(2026, 9, 12, 8, 15, tzinfo=JST),
            deadline_at=self.deadline,
        )
        self.assertEqual(row.observed_at.hour, 8)
        self.assertEqual(row.observed_at.minute, 15)

    def test_after_0815_fails_closed(self) -> None:
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(
                payload=self.payload(),
                observed_at=datetime(2026, 9, 12, 8, 15, 1, tzinfo=JST),
                deadline_at=self.deadline,
            )

    def test_at_deadline_fails_closed(self) -> None:
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(
                payload=self.payload(), observed_at=self.deadline, deadline_at=self.deadline
            )

    def test_tampered_missing_lane_adjustment_fails_closed(self) -> None:
        payload = self.payload(missing_lane=4)
        adjusted = list(payload.adjusted_raw)
        adjusted[3] += 0.1
        bad = replace(payload, adjusted_raw=tuple(adjusted))
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_probability_vector_tamper_fails_closed(self) -> None:
        payload = self.payload()
        probs = list(payload.adjusted_trifecta)
        probs[0] += 0.05
        bad = replace(payload, adjusted_trifecta=tuple(probs))
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)


if __name__ == "__main__":
    unittest.main()
