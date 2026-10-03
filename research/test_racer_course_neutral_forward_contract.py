from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from research.racer_course_neutral_forward_contract import (
    COURSE_COEF,
    CourseLaneEvidence,
    CourseNeutralContractError,
    apply_course_neutral_rule,
)

JST = ZoneInfo("Asia/Tokyo")


class CourseNeutralForwardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.race_date = date(2026, 9, 12)
        self.base = {lane: float(lane) for lane in range(1, 7)}
        self.racers = {lane: 5000 + lane for lane in range(1, 7)}

    def evidence(self, lane: int, top3: float, *, hour: int = 7, minute: int = 30) -> CourseLaneEvidence:
        return CourseLaneEvidence(
            racer_number=self.racers[lane],
            lane=lane,
            course=lane,
            race_date=self.race_date,
            top3_rate=top3,
            created_at=datetime(2026, 9, 12, hour, minute, tzinfo=JST),
            deadline_at=datetime(2026, 9, 12, 10, 0, tzinfo=JST),
        )

    def test_coefficient_is_fixed(self) -> None:
        self.assertEqual(COURSE_COEF, 0.50)

    def test_missing_lane_keeps_base_exactly(self) -> None:
        evidence = {lane: self.evidence(lane, 40 + lane) for lane in range(1, 7) if lane != 3}
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane=evidence,
        )
        self.assertEqual(result.adjusted_raw[3], self.base[3])
        self.assertEqual(result.z_by_lane[3], 0.0)
        self.assertEqual(result.unavailable_reasons[3], "missing_required_row")

    def test_observed_z_scores_sum_to_zero(self) -> None:
        evidence = {lane: self.evidence(lane, 40 + lane) for lane in range(1, 7) if lane != 3}
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane=evidence,
        )
        self.assertAlmostEqual(sum(result.z_by_lane[l] for l in result.usable_lanes), 0.0, places=12)

    def test_exact_0815_is_usable(self) -> None:
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane={1: self.evidence(1, 40, hour=8, minute=15), 2: self.evidence(2, 60)},
        )
        self.assertIn(1, result.usable_lanes)

    def test_after_0815_is_neutralized(self) -> None:
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane={1: self.evidence(1, 40, hour=8, minute=16), 2: self.evidence(2, 60)},
        )
        self.assertEqual(result.adjusted_raw[1], self.base[1])
        self.assertEqual(result.unavailable_reasons[1], "created_after_0815")

    def test_wrong_racer_is_neutralized(self) -> None:
        bad = self.evidence(1, 50)
        bad = CourseLaneEvidence(
            racer_number=999999,
            lane=bad.lane,
            course=bad.course,
            race_date=bad.race_date,
            top3_rate=bad.top3_rate,
            created_at=bad.created_at,
            deadline_at=bad.deadline_at,
        )
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane={1: bad, 2: self.evidence(2, 60)},
        )
        self.assertEqual(result.adjusted_raw[1], self.base[1])
        self.assertEqual(result.unavailable_reasons[1], "racer_mismatch")

    def test_wrong_course_is_neutralized(self) -> None:
        bad = self.evidence(1, 50)
        bad = CourseLaneEvidence(
            racer_number=bad.racer_number,
            lane=1,
            course=2,
            race_date=bad.race_date,
            top3_rate=bad.top3_rate,
            created_at=bad.created_at,
            deadline_at=bad.deadline_at,
        )
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane={1: bad, 2: self.evidence(2, 60)},
        )
        self.assertEqual(result.unavailable_reasons[1], "course_lane_mismatch")

    def test_single_usable_lane_leaves_every_lane_at_base(self) -> None:
        result = apply_course_neutral_rule(
            base_raw=self.base,
            expected_racers=self.racers,
            race_date=self.race_date,
            evidence_by_lane={1: self.evidence(1, 50)},
        )
        self.assertEqual(result.adjusted_raw, self.base)

    def test_invalid_base_fails_closed(self) -> None:
        with self.assertRaises(CourseNeutralContractError):
            apply_course_neutral_rule(
                base_raw={1: 1.0},
                expected_racers=self.racers,
                race_date=self.race_date,
                evidence_by_lane={},
            )


if __name__ == "__main__":
    unittest.main()
