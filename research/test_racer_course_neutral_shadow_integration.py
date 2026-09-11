from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from research.racer_course_neutral_forward_contract import CourseLaneEvidence
from research.racer_course_neutral_shadow_integration import (
    SHADOW_TABLE_NAME,
    TICKET_ORDER_VERSION,
    WRITE_POLICY,
    CourseNeutralShadowIntegrationError,
    prepare_shadow_row,
)
from research.racer_course_neutral_shadow_payload import (
    CANONICAL_TICKETS,
    build_shadow_payload,
    trifecta_probabilities,
)

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
        self.assertEqual(TICKET_ORDER_VERSION, "canonical-permutations-1to6-v1")

    def test_valid_payload_becomes_immutable_row_contract(self) -> None:
        row = prepare_shadow_row(
            payload=self.payload(), observed_at=self.observed, deadline_at=self.deadline
        )
        self.assertEqual(row.immutable_key, ("20260912_01_01", "course-neutral-missing-v1"))
        self.assertEqual(row.write_policy, WRITE_POLICY)
        self.assertEqual(row.ticket_order_version, TICKET_ORDER_VERSION)
        self.assertEqual(row.course_coef, 0.50)
        self.assertEqual(row.prob_temp, 2.20)
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

    def test_zero_variance_course_values_keep_all_lanes_at_base(self) -> None:
        evidence = {
            lane: self.evidence(lane, 50.0)
            for lane in range(1, 7)
        }
        payload = build_shadow_payload(
            race_id="20260912_01_01",
            race_date=self.race_date,
            base_raw=self.base,
            expected_racers=self.racers,
            evidence_by_lane=evidence,
        )
        row = prepare_shadow_row(
            payload=payload,
            observed_at=self.observed,
            deadline_at=self.deadline,
        )
        self.assertTrue(all(row.usable_mask))
        self.assertTrue(all(value == 0.0 for value in row.course_z))
        self.assertEqual(row.adjusted_raw, row.base_raw)
        self.assertEqual(row.adjusted_trifecta, row.base_trifecta)

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

    def test_tampered_course_coefficient_fails_closed(self) -> None:
        bad = replace(self.payload(), course_coef=0.60)
        with self.assertRaisesRegex(CourseNeutralShadowIntegrationError, "frozen 0.50"):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_duplicate_racer_identity_fails_closed(self) -> None:
        payload = self.payload()
        racers = list(payload.racer_numbers)
        racers[5] = racers[0]
        bad = replace(payload, racer_numbers=tuple(racers))
        with self.assertRaisesRegex(CourseNeutralShadowIntegrationError, "must be unique"):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_tampered_course_z_fails_closed(self) -> None:
        payload = self.payload()
        course_z = list(payload.course_z)
        course_z[0] += 0.1
        bad = replace(payload, course_z=tuple(course_z))
        with self.assertRaisesRegex(CourseNeutralShadowIntegrationError, "course_z does not match"):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_tampered_missing_lane_adjustment_fails_closed(self) -> None:
        payload = self.payload(missing_lane=4)
        adjusted = list(payload.adjusted_raw)
        adjusted[3] += 0.1
        bad = replace(payload, adjusted_raw=tuple(adjusted))
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_adjusted_raw_tamper_fails_even_with_matching_recomputed_probabilities(self) -> None:
        payload = self.payload()
        adjusted = list(payload.adjusted_raw)
        adjusted[0] += 0.1
        recomputed = trifecta_probabilities(
            {lane: adjusted[lane - 1] for lane in range(1, 7)}
        )
        bad = replace(
            payload,
            adjusted_raw=tuple(adjusted),
            adjusted_trifecta=tuple(recomputed[ticket] for ticket in CANONICAL_TICKETS),
        )
        with self.assertRaisesRegex(CourseNeutralShadowIntegrationError, "frozen Course 0.50"):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_probability_vector_tamper_fails_closed(self) -> None:
        payload = self.payload()
        probs = list(payload.adjusted_trifecta)
        probs[0] += 0.05
        bad = replace(payload, adjusted_trifecta=tuple(probs))
        with self.assertRaises(CourseNeutralShadowIntegrationError):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)

    def test_probability_permutation_tamper_fails_even_if_sum_stays_one(self) -> None:
        payload = self.payload()
        probs = list(payload.adjusted_trifecta)
        probs[0], probs[1] = probs[1], probs[0]
        bad = replace(payload, adjusted_trifecta=tuple(probs))
        with self.assertRaisesRegex(
            CourseNeutralShadowIntegrationError,
            "does not match frozen v24 probability transform",
        ):
            prepare_shadow_row(payload=bad, observed_at=self.observed, deadline_at=self.deadline)


if __name__ == "__main__":
    unittest.main()
