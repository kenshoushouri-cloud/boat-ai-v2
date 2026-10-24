import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_mainline_inference import OfflineV5InferenceInput
from v5.offline_v5_freeze_bridge import (
    MODEL_VERSION, build_paper_shadow_freeze,
)


class V5FreezeBridgeTest(unittest.TestCase):
    def setUp(self):
        jst = timezone(timedelta(hours=9))
        self.now = datetime(2026, 10, 21, 12, 0, tzinfo=jst)
        self.case = OfflineV5InferenceInput(
            "20261021_01_01", self.now - timedelta(seconds=10),
            (101, 102, 103, 104, 105, 106),
            (.3, .2, .15, .14, .11, .1),
            {key: (1.,) * 6 for key in
             ("recent_form", "exhibition_rank", "racer_course",
              "opponent", "venue_lane")},
        )
        self.kwargs = {
            "deadline_at": (self.now + timedelta(minutes=15)).isoformat(),
            "exhibition": {"complete_items": 6, "sha256": "a"*64,
                           "captured_at": (self.now - timedelta(seconds=30)).isoformat()},
            "odds": {"complete_items": 120, "sha256": "b"*64,
                     "captured_at": (self.now - timedelta(seconds=40)).isoformat()},
            "ticket_count": 2, "stake_per_ticket_yen": 100,
            "now": self.now,
        }

    def test_v5_ranks_are_frozen_for_paper_only(self):
        result = build_paper_shadow_freeze(self.case, **self.kwargs)
        self.assertEqual(result["model_version"], MODEL_VERSION)
        self.assertEqual(len(result["selected_tickets"]), 2)
        self.assertEqual(result["hypothetical_stake_yen"], 200)
        self.assertEqual(result["settlement_status"], "PENDING_NO_REAL_ROI")
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(result["buy_eligible"])
        self.assertFalse(result["original_first_observation_verified"])

    def test_reject_stale_model_decision(self):
        self.case = OfflineV5InferenceInput(
            self.case.race_id, self.now - timedelta(minutes=2),
            self.case.lane_racer_numbers, self.case.base_probabilities, self.case.factors)
        with self.assertRaisesRegex(ValueError, "stale"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_reject_future_model_decision(self):
        self.case = OfflineV5InferenceInput(
            self.case.race_id, self.now + timedelta(seconds=1),
            self.case.lane_racer_numbers, self.case.base_probabilities, self.case.factors)
        with self.assertRaisesRegex(ValueError, "future"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_reject_exhibition_captured_after_decision_cutoff(self):
        # Source arrived before freeze(now), but AFTER model decision cutoff.
        self.kwargs["exhibition"]["captured_at"] = (
            self.now - timedelta(seconds=5)).isoformat()
        with self.assertRaisesRegex(ValueError, "exhibition.*decision cutoff"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_reject_odds_captured_after_decision_cutoff(self):
        self.kwargs["odds"]["captured_at"] = (
            self.now - timedelta(seconds=3)).isoformat()
        with self.assertRaisesRegex(ValueError, "odds.*decision cutoff"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_captured_exactly_at_cutoff_stays_non_buyable(self):
        at_cutoff = self.case.decision_cutoff_at.isoformat()
        self.kwargs["exhibition"]["captured_at"] = at_cutoff
        self.kwargs["odds"]["captured_at"] = at_cutoff
        record = build_paper_shadow_freeze(self.case, **self.kwargs)
        self.assertFalse(record["original_first_observation_verified"])
        self.assertFalse(record["forward_eligible"])
        self.assertFalse(record["buy_eligible"])

    def test_reject_incomplete_odds(self):
        self.kwargs["odds"]["complete_items"] = 119
        with self.assertRaisesRegex(ValueError, "odds"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_reject_postdeadline_freeze(self):
        self.kwargs["deadline_at"] = (self.now + timedelta(minutes=2)).isoformat()
        with self.assertRaisesRegex(ValueError, "deadline"):
            build_paper_shadow_freeze(self.case, **self.kwargs)

    def test_reject_invalid_model_shape(self):
        self.case = OfflineV5InferenceInput(
            self.case.race_id, self.case.decision_cutoff_at,
            (101, 102, 103, 104, 105, 105),
            self.case.base_probabilities, self.case.factors)
        with self.assertRaisesRegex(ValueError, "inference"):
            build_paper_shadow_freeze(self.case, **self.kwargs)


if __name__ == "__main__":
    unittest.main()
