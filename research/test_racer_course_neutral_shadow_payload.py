from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from research.racer_course_neutral_forward_contract import CourseLaneEvidence
from research.racer_course_neutral_shadow_payload import (
    CANONICAL_TICKETS,
    SHADOW_VERSION,
    V24_PROB_TEMP,
    CourseNeutralPayloadError,
    build_shadow_payload,
    trifecta_probabilities,
)

JST = ZoneInfo("Asia/Tokyo")


class CourseNeutralShadowPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.race_date = date(2026, 9, 12)
        self.base = {lane: float(lane) / 10.0 for lane in range(1, 7)}
        self.racers = {lane: 7000 + lane for lane in range(1, 7)}

    def evidence(self, lane: int, top3: float) -> CourseLaneEvidence:
        return CourseLaneEvidence(
            racer_number=self.racers[lane],
            lane=lane,
            course=lane,
            race_date=self.race_date,
            top3_rate=top3,
            created_at=datetime(2026, 9, 12, 7, 30, tzinfo=JST),
            deadline_at=datetime(2026, 9, 12, 10, 0, tzinfo=JST),
        )

    def test_v24_temperature_and_ticket_order_are_fixed(self) -> None:
        self.assertEqual(V24_PROB_TEMP, 2.20)
        self.assertEqual(len(CANONICAL_TICKETS), 120)
        self.assertEqual(CANONICAL_TICKETS[0], "1-2-3")
        self.assertEqual(len(set(CANONICAL_TICKETS)), 120)

    def test_probability_vector_is_complete_and_normalized(self) -> None:
        probs = trifecta_probabilities(self.base)
        self.assertEqual(tuple(probs), CANONICAL_TICKETS)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=12)
        self.assertTrue(all(p > 0.0 for p in probs.values()))

    def test_no_evidence_produces_identical_base_and_adjusted_vectors(self) -> None:
        payload = build_shadow_payload(
            race_id="20260912_01_01",
            race_date=self.race_date,
            base_raw=self.base,
            expected_racers=self.racers,
            evidence_by_lane={},
        )
        self.assertEqual(payload.shadow_version, SHADOW_VERSION)
        self.assertEqual(payload.base_version, "v24")
        self.assertEqual(payload.course_coef, 0.50)
        self.assertEqual(payload.base_raw, payload.adjusted_raw)
        self.assertEqual(payload.base_trifecta, payload.adjusted_trifecta)
        self.assertEqual(payload.usable_mask, (False,) * 6)
        self.assertEqual(len(payload.base_trifecta), 120)

    def test_one_missing_lane_preserves_its_raw_strength_and_payload_slot(self) -> None:
        evidence = {lane: self.evidence(lane, 40 + lane) for lane in range(1, 7) if lane != 4}
        payload = build_shadow_payload(
            race_id="20260912_01_02",
            race_date=self.race_date,
            base_raw=self.base,
            expected_racers=self.racers,
            evidence_by_lane=evidence,
        )
        self.assertFalse(payload.usable_mask[3])
        self.assertIsNone(payload.course_top3[3])
        self.assertEqual(payload.unavailable_reason[3], "missing_required_row")
        self.assertEqual(payload.adjusted_raw[3], payload.base_raw[3])
        self.assertAlmostEqual(sum(payload.adjusted_trifecta), 1.0, places=12)

    def test_complete_evidence_changes_adjusted_vector_but_not_base_vector(self) -> None:
        evidence = {lane: self.evidence(lane, 35 + lane * 3) for lane in range(1, 7)}
        payload = build_shadow_payload(
            race_id="20260912_01_03",
            race_date=self.race_date,
            base_raw=self.base,
            expected_racers=self.racers,
            evidence_by_lane=evidence,
        )
        expected_base = tuple(trifecta_probabilities(self.base)[ticket] for ticket in CANONICAL_TICKETS)
        self.assertEqual(payload.base_trifecta, expected_base)
        self.assertNotEqual(payload.adjusted_trifecta, payload.base_trifecta)
        self.assertEqual(payload.usable_mask, (True,) * 6)

    def test_blank_race_id_fails_closed(self) -> None:
        with self.assertRaises(CourseNeutralPayloadError):
            build_shadow_payload(
                race_id=" ",
                race_date=self.race_date,
                base_raw=self.base,
                expected_racers=self.racers,
                evidence_by_lane={},
            )

    def test_nonfinite_raw_fails_closed(self) -> None:
        bad = dict(self.base)
        bad[2] = float("nan")
        with self.assertRaises(CourseNeutralPayloadError):
            trifecta_probabilities(bad)


if __name__ == "__main__":
    unittest.main()
