"""V5 retrospective economics; local/offline, NEVER a live bet or real ROI."""
import unittest
from v5.offline_retrospective_trifecta_returns import (
    FixedSelection, FixedTicket, OfficialSettlement,
    evaluate_fixed_retrospective_returns as evaluate,
)
R = "20260501_24_12"
OTHER = "20260501_24_11"


def selection(race_id=R, tickets=("2-1-5",)):
    return FixedSelection(race_id, tuple(FixedTicket(t, 100) for t in tickets))


class RetrospectiveEconomicsTest(unittest.TestCase):
    def test_actual_recorded_payout_math_with_hypothetical_selection(self):
        # Stored real numerical parity 61.8*100==6180, but V5 has NOT
        # demonstrated it selected this 2-1-5 ticket before cutoff.
        a = evaluate((selection(),),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, ()),))
        self.assertEqual((a.planned_stake_yen, a.gross_return_yen,
                          a.hypothetical_net_yen), (100, 6180, 6080))
        self.assertEqual(a.hypothetical_roi_pct, 6180.0)
        self.assertEqual(a.reason, "RETROSPECTIVE_RESULT_PAYOUT_SCENARIO_ONLY")
        self.assertTrue(a.scenario_only)
        self.assertFalse(a.original_predeadline_capture_verified)
        self.assertFalse(a.genuine_forward_roi_verified)
        self.assertFalse(a.buy_eligible)

    def test_losing_ticket_retains_full_stake(self):
        a = evaluate((selection(tickets=("1-2-3",)),),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, ()),))
        self.assertEqual((a.planned_stake_yen, a.gross_return_yen,
                          a.hypothetical_net_yen, a.hypothetical_roi_pct),
                         (100, 0, -100, 0.0))

    def test_multiple_tickets_win_and_lose(self):
        a = evaluate((selection(tickets=("2-1-5", "3-4-5")),),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, ()),))
        self.assertEqual((a.planned_stake_yen, a.gross_return_yen,
                          a.hypothetical_net_yen), (200, 6180, 5980))

    def test_void_race_refunds_every_original_stake(self):
        a = evaluate((selection(),), (OfficialSettlement(R, "VOID"),))
        self.assertEqual((a.planned_stake_yen, a.gross_return_yen,
                          a.hypothetical_net_yen, a.hypothetical_roi_pct),
                         (100, 100, 0, 100.0))
        self.assertEqual(a.status_by_race, ((R, "VOID_REFUNDED"),))

    def test_official_flying_boat_refund_only_affected_ticket(self):
        s = selection(tickets=("1-2-3", "2-1-5"))
        a = evaluate((s,), (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, (3,)),))
        self.assertEqual((a.planned_stake_yen, a.gross_return_yen), (200, 6280))

    def test_unknown_refund_mapping_withholds_roi(self):
        a = evaluate((selection(),),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, None),))
        self.assertEqual(a.reason, "INCOMPLETE_COHORT_ROI_WITHHELD")
        self.assertEqual((a.unresolved_races, a.unresolved_stake_yen), (1, 100))
        self.assertIsNone(a.hypothetical_roi_pct)
        self.assertIsNone(a.hypothetical_net_yen)

    def test_one_pending_race_kept_in_original_denominator(self):
        a = evaluate((selection(), selection(OTHER, ("1-2-3",))),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, ()),))
        self.assertEqual((a.candidate_races, a.resolved_races, a.unresolved_races,
                          a.planned_stake_yen, a.unresolved_stake_yen),
                         (2, 1, 1, 200, 100))
        self.assertIsNone(a.hypothetical_net_yen)
        self.assertEqual(a.status_by_race[-1], (OTHER, "UNRESOLVED"))

    def test_invalid_ticket_never_assumed_to_lose(self):
        a = evaluate((selection(tickets=("1-1-2",)),), ())
        self.assertEqual(a.reason, "INVALID_SELECTED_TICKET")
        self.assertIsNone(a.hypothetical_roi_pct)

    def test_duplicate_selected_ticket_fails(self):
        a = evaluate((selection(tickets=("1-2-3", "1-2-3")),), ())
        self.assertEqual(a.reason, "DUPLICATE_SELECTED_TICKET")

    def test_winner_refund_contradiction_fails(self):
        a = evaluate((selection(),),
                     (OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, (2,)),))
        self.assertEqual(a.reason, "WINNER_REFUND_CONTRADICTION")

    def test_duplicated_settlement_fails(self):
        o = OfficialSettlement(R, "OFFICIAL", "2-1-5", 6180, ())
        a = evaluate((selection(),), (o, o))
        self.assertEqual(a.reason, "EXTRA_OR_DUPLICATE_SETTLEMENT")

    def test_extra_settlement_fails(self):
        a = evaluate((selection(),), (OfficialSettlement(OTHER, "PENDING"),))
        self.assertEqual(a.reason, "EXTRA_OR_DUPLICATE_SETTLEMENT")


if __name__ == "__main__":
    unittest.main()
