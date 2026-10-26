"""Pure synthetic-only regression: no HTTP, DB, ConoHa timers, or BUY."""
from __future__ import annotations

import dataclasses
import unittest
from datetime import datetime, timedelta, timezone

from v5.entry_quality_policy import STATS, LaneInput
from v5.offline_mainline_inference import OfflineV5InferenceInput
from v5.offline_paper_quality_bridge import (
    SyntheticPaperCandidate, evaluate_synthetic_paper,
)

JST = timezone(timedelta(hours=9))


def sample_entries():
    stats = {
        key: (0.16 if key == "avg_st" else
              25 if key in ("motor_no", "boat_no") else 5.)
        for key in STATS
    }
    return tuple(LaneInput(
        lane=i, racer_number=4000 + i, stats=dict(stats),
        established_strength_rating=98.5 if i == 1 else 45.)
        for i in range(1, 7))


def sample():
    return SyntheticPaperCandidate(
        entries=sample_entries(),
        math_input=OfflineV5InferenceInput(
            race_id="20261026_10_01",
            decision_cutoff_at=datetime(2026, 10, 26, 8, 47, tzinfo=JST),
            lane_racer_numbers=tuple(4000+i for i in range(1, 7)),
            base_probabilities=(.3, .2, .16, .14, .12, .08),
            factors={
                k: (1., 1., 1., 1., 1., 1.)
                for k in ("recent_form", "exhibition_rank", "racer_course",
                          "opponent", "venue_lane")
            },
        ),
        synthetic_only=True,
    )


def replace_lane_first(c, **changes):
    entries = list(c.entries)
    entries[0] = dataclasses.replace(entries[0], **changes)
    return dataclasses.replace(c, entries=tuple(entries))


class OfflinePaperQualityBridgeTest(unittest.TestCase):
    def check(self, candidate, reason):
        result = evaluate_synthetic_paper(candidate)
        self.assertEqual(result.reason, reason)
        for field in (
            "independently_authenticated_source",
            "original_first_observation_verified", "six_active_starts_confirmed",
            "selection_eligible", "forward_eligible", "buy_eligible",
        ):
            self.assertIs(getattr(result, field), False)
        return result

    def test_complete_stats_calculates_only_synthetic_first_place(self):
        case = sample()
        original = dataclasses.asdict(case)
        outcome = self.check(
            case, "SYNTHETIC_FIRST_PLACE_RESEARCH_ONLY_HARD_HOLD")
        self.assertTrue(outcome.synthetic_scoring_executed)
        self.assertEqual(len(outcome.lane_probabilities), 6)
        self.assertAlmostEqual(sum(outcome.lane_probabilities), 1.)
        self.assertEqual(dataclasses.asdict(case), original)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            outcome.buy_eligible = True

    def test_official_unreported_preserves_rating_but_blocks_unvalidated_math(self):
        c = sample()
        fields = dict(c.entries[0].stats)
        fields["local_win_rate"] = None
        updated = replace_lane_first(
            c, stats=fields,
            missing_evidence={"local_win_rate": "OFFICIAL_UNREPORTED"})
        outcome = self.check(
            updated, "MISSING_AWARE_MODEL_NOT_VALIDATED_HOLD")
        self.assertEqual(updated.entries[0].established_strength_rating, 98.5)
        self.assertEqual(outcome.entry_quality_status, "MISSING_AWARE_RESEARCH_ONLY")
        self.assertFalse(outcome.synthetic_scoring_executed)

    def test_unverified_null_and_parser_failure_block_scoring(self):
        c = sample()
        fields = dict(c.entries[0].stats)
        fields["avg_st"] = None
        self.check(replace_lane_first(c, stats=fields), "ENTRY_QUALITY_HOLD")
        self.check(replace_lane_first(c, parser_failed=True),
                   "ENTRY_QUALITY_HOLD")
        self.check(replace_lane_first(c, stats=dict.fromkeys(STATS)),
                   "ENTRY_QUALITY_HOLD")

    def test_six_lane_identity_mismatch_blocks_scoring(self):
        c = sample()
        bad_math = dataclasses.replace(
            c.math_input, lane_racer_numbers=(9999, 4002, 4003, 4004, 4005, 4006))
        outcome = self.check(
            dataclasses.replace(c, math_input=bad_math),
            "LANE_IDENTITY_MISMATCH_HOLD")
        self.assertFalse(outcome.lane_probabilities)

    def test_invalid_asof_or_synthetic_only_flag_blocks_scoring(self):
        c = sample()
        self.check(dataclasses.replace(c, synthetic_only=False),
                   "SYNTHETIC_ONLY_REQUIRED_HOLD")
        bad_math = dataclasses.replace(c.math_input, race_id="20261027_10_01")
        self.check(dataclasses.replace(c, math_input=bad_math),
                   "MATH_INPUT_INVALID_HOLD")

    def test_invalid_candidate_never_promoted(self):
        self.check(None, "SYNTHETIC_ONLY_REQUIRED_HOLD")


if __name__ == "__main__":
    unittest.main()
