"""V5 offline-only TOP-N -> actual stored result scenario join tests."""
import unittest
from dataclasses import replace
from itertools import permutations

from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_retrospective_v5_result_join import (
    StoredResult, RefundEvidenceClaim, VoidEvidenceClaim,
    join_v5_rankings_to_stored_results as join,
    RANK_REASON,
)

R = "20260501_24_12"
OTHER = "20260501_24_11"


def ranking(rid=R, n=1):
    tickets = sorted("-".join(map(str, t))
                     for t in permutations(range(1, 7), 3))
    vals = {t: 0.3 / 118 for t in tickets}
    vals["2-1-5"] = 0.4
    vals["3-4-5"] = 0.3
    dist = tuple(sorted(vals.items()))
    top = tuple(sorted(dist, key=lambda x: (-x[1], x[0]))[:n])
    return OfflineTrifectaShadowRanking(
        RANK_REASON, rid, n, dist, top, True)


def official(rid=R):
    return StoredResult(rid, "official", "official", "2-1-5", 6180)


def refund(rid=R, boats=()):
    return RefundEvidenceClaim(rid, boats, "official-return-section:checked")


def settle(rankings=None, results=None, refunds=None, voids=None, stake=100):
    if rankings is None: rankings = (ranking(),)
    if results is None: results = (official(),)
    if refunds is None: refunds = ()
    if voids is None: voids = ()
    return join(rankings, results, refunds, voids, ticket_stake_yen=stake)


class RetrospectiveV5JoinTest(unittest.TestCase):
    def test_recorded_winner_payout_scenario_only(self):
        v = settle(refunds=(refund(),))
        self.assertEqual(v.reason, "RETROSPECTIVE_JOIN_SCENARIO_ONLY")
        self.assertEqual((v.cash.planned_stake_yen, v.cash.gross_return_yen,
                          v.cash.hypothetical_net_yen), (100, 6180, 6080))
        self.assertTrue(v.postrace_archive_only)
        self.assertFalse(v.independently_authenticated_source)
        self.assertFalse(v.predeadline_frozen_selection_verified)
        self.assertFalse(v.v5_real_roi_verified)
        self.assertFalse(v.buy_eligible)

    def test_missing_refund_proof_withholds_complete_roi(self):
        v = settle()
        self.assertEqual(v.reason, "RETROSPECTIVE_JOIN_PENDING_ROI_WITHHELD")
        self.assertEqual(v.missing_refund_evidence_races, 1)
        self.assertIsNone(v.cash.hypothetical_roi_pct)
        self.assertIsNone(v.cash.hypothetical_net_yen)

    def test_missing_result_keeps_original_cohort(self):
        v = settle(rankings=(ranking(), ranking(OTHER)), results=(official(),),
                   refunds=(refund(),))
        self.assertEqual((v.cash.candidate_races, v.cash.unresolved_races,
                          v.cash.planned_stake_yen), (2, 1, 200))
        self.assertIsNone(v.cash.hypothetical_net_yen)

    def test_explicit_void_refunds_selected_stake(self):
        v = settle(results=(StoredResult(R, "void", "void", None, None),),
                   voids=(VoidEvidenceClaim(R, "official-k:verified"),))
        self.assertEqual((v.evidenced_void_races, v.cash.gross_return_yen,
                          v.cash.hypothetical_net_yen), (1, 100, 0))
        self.assertFalse(v.buy_eligible)

    def test_unverified_void_is_pending(self):
        v = settle(results=(StoredResult(R, "void", "void", None, None),))
        self.assertEqual(v.reason, "RETROSPECTIVE_JOIN_PENDING_ROI_WITHHELD")
        self.assertEqual(v.missing_result_races, 1)

    def test_single_flying_boat_refunds_only_affected_ticket(self):
        v = settle(rankings=(ranking(n=2),), refunds=(refund(boats=(3,)),))
        self.assertEqual((v.cash.planned_stake_yen, v.cash.gross_return_yen,
                          v.cash.hypothetical_net_yen), (200, 6280, 6080))

    def test_forged_ranking_top_rejected(self):
        x = ranking()
        altered = replace(x, top_tickets=(("1-2-3", 0.8),))
        self.assertEqual(settle(rankings=(altered,)).reason,
                         "STALE_OR_FORGED_V5_TOP_TICKETS")

    def test_duplicate_race_rejected(self):
        self.assertEqual(settle(rankings=(ranking(), ranking())).reason,
                         "DUPLICATE_RANKING_RACE")

    def test_extra_result_rejected(self):
        self.assertEqual(settle(results=(official(), official(OTHER))).reason,
                         "EXTRA_DUPLICATE_OR_BAD_EVIDENCE")

    def test_no_empty_evidence_ref(self):
        self.assertEqual(
            settle(refunds=(RefundEvidenceClaim(R, (), ""),)).reason,
            "INVALID_REFUND_CLAIM")

    def test_void_evidence_conflicts_with_official(self):
        self.assertEqual(
            settle(voids=(VoidEvidenceClaim(R, "official-k:verified"),)).reason,
            "OFFICIAL_RESULT_CONFLICTS_WITH_VOID_EVIDENCE")

    def test_invalid_stake_rejected(self):
        self.assertEqual(settle(stake=0).reason,
                         "EXPLICIT_VALID_TICKET_STAKE_REQUIRED")
        self.assertEqual(settle(stake=True).reason,
                         "EXPLICIT_VALID_TICKET_STAKE_REQUIRED")

    def test_ambiguous_race_status_pending_not_silent_loss(self):
        v = settle(results=(StoredResult(R, "official", "pending", "2-1-5", 6180),))
        self.assertEqual(v.reason, "RETROSPECTIVE_JOIN_PENDING_ROI_WITHHELD")
        self.assertIsNone(v.cash.hypothetical_roi_pct)


if __name__ == "__main__":
    unittest.main()
