"""V5 frozen-ranking adapter unit tests: NO Railway, web, DB or BUY."""
import unittest
from dataclasses import replace
from datetime import datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_retrospective_result_adapter import (
    FrozenResearchRank, StoredResultRow, join_ranked_v5_scenarios,
)

JST = ZoneInfo("Asia/Tokyo")
RACE = "20260501_24_12"
EXPECTED = "SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD"


def rank(top_count=1):
    tickets = ["-".join(map(str, p)) for p in permutations(range(1, 7), 3)]
    weight = {t: 10. if t == "2-1-5" else 1. for t in tickets}
    total = sum(weight.values())
    dist = tuple(sorted((t, p / total) for t, p in weight.items()))
    ordered = tuple(sorted(dist, key=lambda x: (-x[1], x[0])))
    return OfflineTrifectaShadowRanking(
        EXPECTED, RACE, top_count, dist, ordered[:top_count], True,
    )


def case(top_count=1, stake=100, *, early=False):
    created = datetime(2026, 5, 1, 17, 10, tzinfo=JST) if early else (
        datetime(2026, 8, 15, 13, 54, tzinfo=JST))
    return FrozenResearchRank(
        rank(top_count), datetime(2026, 5, 1, 17, 30, tzinfo=JST),
        datetime(2026, 5, 1, 17, 41, tzinfo=JST), created, stake)


def actual_stored_winner(*, refunded=None, verified=False):
    return StoredResultRow(RACE, "official", "official", "2-1-5", 6180,
                           refunded, verified)


class TestV5RetrospectiveResultAdapter(unittest.TestCase):
    def test_stored_payout_is_only_hypothetical_when_refund_verified(self):
        # User-observed stored ticket/payout 2-1-5 / JPY 6180.
        # Synthetic constructed top-1 deliberately equals winner here;
        # that is NOT evidence V5 historically selected it.
        x = join_ranked_v5_scenarios(
            [case()], [actual_stored_winner(refunded=(), verified=True)])
        self.assertEqual(x.reason, "RETROSPECTIVE_V5_SCENARIO_JOIN_NO_BUY_AUTHORITY")
        self.assertEqual(x.selections[0].tickets[0].combination, "2-1-5")
        self.assertEqual((x.economics.planned_stake_yen,
                          x.economics.gross_return_yen,
                          x.economics.hypothetical_net_yen), (100, 6180, 6080))
        self.assertEqual(x.provenance_by_race[0][1],
                         "RETROSPECTIVE_ARCHIVE_NOT_ASOF")
        self.assertFalse(x.v5_real_roi_verified)
        self.assertFalse(x.buy_eligible)

    def test_missing_refund_proof_blocks_full_cohort_roi(self):
        x = join_ranked_v5_scenarios([case()], [actual_stored_winner()])
        self.assertEqual(x.economics.unresolved_races, 1)
        self.assertEqual(x.economics.reason, "INCOMPLETE_COHORT_ROI_WITHHELD")
        self.assertIsNone(x.economics.hypothetical_roi_pct)
        self.assertIsNone(x.economics.hypothetical_net_yen)

    def test_empty_refund_tuple_without_verified_flag_still_blocks(self):
        x = join_ranked_v5_scenarios(
            [case()], [actual_stored_winner(refunded=(), verified=False)])
        self.assertIsNone(x.economics.hypothetical_roi_pct)

    def test_unmatched_original_cohort_is_not_silently_removed(self):
        x = join_ranked_v5_scenarios([case()], [])
        self.assertEqual(x.economics.candidate_races, 1)
        self.assertEqual(x.economics.unresolved_races, 1)
        self.assertIsNone(x.economics.hypothetical_net_yen)

    def test_official_void_only_when_independently_verified(self):
        result = StoredResultRow(RACE, "void", "void", None, None,
                                 None, False, True)
        x = join_ranked_v5_scenarios([case()], [result])
        self.assertEqual(x.economics.hypothetical_net_yen, 0)
        self.assertEqual(x.economics.status_by_race[0][1], "VOID_REFUNDED")

    def test_unverified_void_remains_pending(self):
        result = StoredResultRow(RACE, "void", "void", None, None,
                                 None, False, False)
        x = join_ranked_v5_scenarios([case()], [result])
        self.assertIsNone(x.economics.hypothetical_roi_pct)

    def test_forged_top_ticket_order_is_rejected(self):
        forged = replace(rank(), top_tickets=(("1-2-3", 0.1),))
        x = join_ranked_v5_scenarios(
            [replace(case(), ranking=forged)], [actual_stored_winner()])
        self.assertEqual(x.reason, "RANKING_OR_TIME_SHAPE_INVALID")

    def test_ticket_count_and_stake_explicit_not_inherited_from_v4(self):
        x = join_ranked_v5_scenarios([case(stake=50)], [])
        self.assertEqual(x.reason, "RANKING_OR_TIME_SHAPE_INVALID")

    def test_duplicate_stored_result_cannot_bias_roi(self):
        row = actual_stored_winner()
        x = join_ranked_v5_scenarios([case()], [row, row])
        self.assertEqual(x.reason, "DUPLICATE_OR_EXTRANEOUS_RESULT_RACE")

    def test_early_time_is_not_independent_source_proof(self):
        x = join_ranked_v5_scenarios([case(early=True)], [])
        self.assertEqual(x.provenance_by_race[0][1],
                         "EARLY_TIMESTAMP_CLAIM_NOT_SOURCE_AUTHENTICATED")
        self.assertFalse(x.predeadline_original_capture_verified)


if __name__ == "__main__":
    unittest.main()
