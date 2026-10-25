"""Synthetic test fixtures only; no database, web or BUY actions."""
import unittest

from v5.entry_quality_policy import STATS, LaneInput, inspect_lane, inspect_race


def full_stats():
    return {
        "avg_st": .16,
        "national_win_rate": 7.5,
        "national_place2_rate": 52.,
        "national_place3_rate": 65.,
        "local_win_rate": 6.5,
        "local_place2_rate": 47.,
        "local_place3_rate": 55.,
        "motor_no": 24,
        "motor_place2_rate": 38.,
        "motor_place3_rate": 44.,
        "boat_no": 63,
        "boat_place2_rate": 27.,
        "boat_place3_rate": 43.,
    }


def lane(n, **kwargs):
    data = {"lane": n, "racer_number": 4000+n,
            "stats": full_stats(),
            "established_strength_rating": 96.5 if n == 1 else 42.}
    data.update(kwargs)
    return LaneInput(**data)


class TestV5EntryQualityPolicy(unittest.TestCase):
    def test_all_13_present_does_not_authorize_buy(self):
        result = inspect_lane(lane(1))
        self.assertEqual(result.status, "COMPLETE_STATS_RESEARCH_ONLY")
        self.assertTrue(result.research_candidate)
        self.assertFalse(result.buy_eligible)
        self.assertEqual(result.established_strength_rating, 96.5)

    def test_trusted_official_missing_keeps_high_rating(self):
        stats = full_stats()
        stats["local_win_rate"] = None
        r = inspect_lane(lane(1, stats=stats,
                              missing_evidence={"local_win_rate": "OFFICIAL_UNREPORTED"}))
        self.assertEqual(r.status, "OFFICIAL_UNREPORTED_RESEARCH_ONLY")
        self.assertEqual(r.established_strength_rating, 96.5)
        self.assertEqual(r.official_unreported, ("local_win_rate",))
        self.assertTrue(r.requires_missing_aware_model)
        self.assertTrue(r.research_candidate)
        self.assertFalse(r.buy_eligible)

    def test_null_alone_is_not_proof_of_official_missing(self):
        stats = full_stats()
        stats["local_win_rate"] = None
        r = inspect_lane(lane(1, stats=stats))
        self.assertEqual(r.status, "UNVERIFIED_MISSING_HOLD")
        self.assertFalse(r.research_candidate)
        self.assertEqual(r.established_strength_rating, 96.5)

    def test_parser_warning_even_if_other_values_survive(self):
        r = inspect_lane(lane(1, parser_failed=True))
        self.assertEqual(r.status, "PARSER_FAILURE_HOLD")
        self.assertFalse(r.buy_eligible)

    def test_all_thirteen_nulls_are_not_a_weak_racer(self):
        r = inspect_lane(lane(1, stats=dict.fromkeys(STATS)))
        self.assertEqual(r.status, "ALL_STATS_MISSING_HOLD")
        self.assertEqual(r.established_strength_rating, 96.5)

    def test_forged_official_evidence_on_reported_number(self):
        r = inspect_lane(lane(
            1, missing_evidence={"national_win_rate": "OFFICIAL_UNREPORTED"}))
        self.assertEqual(r.status, "INVALID_OR_CONFLICTING_INPUT_HOLD")

    def test_zero_and_none_are_not_interchangeable(self):
        stats = full_stats()
        stats["local_win_rate"] = 0.0
        r = inspect_lane(lane(1, stats=stats))
        self.assertEqual(r.status, "COMPLETE_STATS_RESEARCH_ONLY")
        self.assertFalse(r.missing_fields)

    def test_invalid_stat_is_not_clamped_or_imputed(self):
        stats = full_stats()
        stats["national_place2_rate"] = 120.
        self.assertEqual(inspect_lane(lane(1, stats=stats)).status,
                         "INVALID_OR_CONFLICTING_INPUT_HOLD")

    def test_one_bad_lane_holds_only_that_race(self):
        lanes = [lane(i) for i in range(1, 7)]
        lanes[2] = lane(3, stats=dict.fromkeys(STATS), parser_failed=True)
        result = inspect_race(tuple(lanes))
        self.assertEqual(result.status, "AT_LEAST_ONE_LANE_QUALITY_HOLD")
        self.assertEqual(result.lanes[0].established_strength_rating, 96.5)
        self.assertFalse(result.research_candidate)
        self.assertFalse(result.buy_eligible)

    def test_good_unreported_lane_remains_research_candidate(self):
        lanes = [lane(i) for i in range(1, 7)]
        stats = full_stats()
        stats["avg_st"] = None
        lanes[0] = lane(1, stats=stats,
                        missing_evidence={"avg_st": "OFFICIAL_UNREPORTED"})
        result = inspect_race(tuple(lanes))
        self.assertEqual(result.status, "MISSING_AWARE_RESEARCH_ONLY")
        self.assertTrue(result.research_candidate)
        self.assertFalse(result.buy_eligible)

    def test_duplicate_or_missing_racer_identity_holds(self):
        lanes = [lane(i) for i in range(1, 7)]
        lanes[1] = lane(2, racer_number=4001)
        r = inspect_race(tuple(lanes))
        self.assertEqual(r.status, "SIX_LANE_IDENTITY_HOLD")

    def test_nonfinite_strength_score_does_not_pass(self):
        self.assertEqual(
            inspect_lane(lane(1, established_strength_rating=float("nan"))).status,
            "INVALID_OR_CONFLICTING_INPUT_HOLD",
        )


if __name__ == "__main__":
    unittest.main()
