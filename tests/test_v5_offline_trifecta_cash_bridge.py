"""Targeted fake-only ranking + cash ledger bridge tests; zero network/DB/BUY."""
from __future__ import annotations

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_mainline_inference import OfflineV5InferenceVerdict
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas
from v5.offline_trifecta_cash_ledger import (
    MockOrder, MockTicketReturn, PredeadlineMockRace, PostraceMockResult,
)
from v5.offline_trifecta_cash_bridge import audit_offline_shadow_cash_bridge

JST = timezone(timedelta(hours=9))
T0 = datetime(2026, 10, 10, 10, tzinfo=JST)
RID1 = '20261010_03_01'
RID2 = '20261010_03_02'
RID3 = '20261010_03_03'
MATH_REASON = 'SYNTHETIC_V5_FIRST_PLACE_PROBABILITIES_ASOF_UNVERIFIED_HARD_HOLD'
SRC = b'fake-source-not-authenticated'
RES = b'fake-results-not-authenticated'


def ranking(rid, n=2):
    pred = OfflineV5InferenceVerdict(MATH_REASON, rid, (.3, .25, .15, .13, .1, .07), True)
    ans = rank_offline_v5_trifectas(pred, ticket_count=n)
    assert ans.synthetic_math_consistent
    return ans


def race(rank):
    orders = tuple(MockOrder(ticket, 100, 8.4, T0+timedelta(minutes=2),
                             T0+timedelta(minutes=5), f'fictional-receipt-{rank.race_id}-{i}')
                   for i, (ticket, _) in enumerate(rank.top_tickets))
    return PredeadlineMockRace(rank.race_id, T0+timedelta(hours=1), T0,
                              T0+timedelta(minutes=20), 'fictional-raw-original',
                              SRC, hashlib.sha256(SRC).hexdigest(), orders)


def result(rank, status='OFFICIAL'):
    if status == 'VOID':
        amounts = tuple(MockTicketReturn(t, 0, 100) for t, _ in rank.top_tickets)
        winner = None
    else:
        winner = rank.top_tickets[0][0]
        amounts = tuple(MockTicketReturn(t, 900 if t == winner else 0, 0)
                        for t, _ in rank.top_tickets)
    return PostraceMockResult(rank.race_id, T0+timedelta(hours=4), 'fictional-results',
                              RES, hashlib.sha256(RES).hexdigest(), status, winner, amounts)


def fixtures(n=2):
    ranks = [ranking(RID1, n), ranking(RID2, n)]
    return ranks, [race(r) for r in ranks], [result(ranks[0]), result(ranks[1], 'VOID')]


class TestV5OfflineCashBridge(unittest.TestCase):
    def check(self, ranks, pre, post, reason):
        ans = audit_offline_shadow_cash_bridge(ranks, pre, post)
        self.assertEqual(ans.reason, reason)
        for flag in ('actual_purchase_verified', 'independently_authenticated_source',
                     'six_active_starts_confirmed', 'selection_eligible',
                     'beforeinfo_first_write_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(ans, flag), False)
        if reason != 'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD':
            self.assertFalse(ans.mock_complete)
            self.assertEqual((ans.synthetic_paid_yen, ans.synthetic_return_yen,
                              ans.synthetic_roi_pct, ans.candidate_races), (0, 0, None, 0))
        return ans

    def test_full_ledger_with_void_keeps_cash_denominator(self):
        a,b,c=fixtures()
        ans=self.check(a,b,c,'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD')
        self.assertEqual((ans.candidate_races, ans.tickets, ans.official_races,
                          ans.void_races, ans.ticket_hits), (2,4,1,1,1))
        self.assertEqual((ans.synthetic_paid_yen,ans.synthetic_return_yen,ans.synthetic_net_yen),(400,1100,700))
        self.assertEqual((ans.synthetic_roi_pct,ans.synthetic_ticket_hit_pct),(275.,25.))
        self.assertEqual((ans.days[0].candidate_races,ans.days[0].purchased_tickets),(2,4))

    def test_reordered_races_settlement_and_rankings_join_by_id(self):
        a,b,c=fixtures()
        ans=self.check(list(reversed(a)),b,list(reversed(c)), 'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD')
        self.assertEqual(ans.synthetic_net_yen,700)

    def test_explicit_one_ticket_or_three_ticket_not_v4_default(self):
        for n in (1,3):
            with self.subTest(n=n):
                a,b,c=fixtures(n)
                v=self.check(a,b,c,'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD')
                self.assertEqual(v.tickets,2*n)

    def test_missing_or_extra_race_prevents_any_derived_economics(self):
        a,b,c=fixtures()
        self.check(a,b[:1],c,'BRIDGE_COHORT_SHAPE_MISMATCH')
        b[1]=dataclasses.replace(b[1],race_id=RID3)
        self.check(a,b,c,'MISSING_OR_EXTRA_RACE_ID')

    def test_duplicate_ranking_and_predecision_ids_denied(self):
        a,b,c=fixtures()
        self.check([a[0],a[0]],b,c,'DUPLICATE_OR_INVALID_RACE_ID')
        self.check(a,[b[0],b[0]],c,'DUPLICATE_OR_INVALID_RACE_ID')

    def test_bad_ticket_order_and_duplicate_purchase_ticket_denied(self):
        a,b,c=fixtures()
        b[0]=dataclasses.replace(b[0],orders=tuple(reversed(b[0].orders)))
        self.check(a,b,c,'MISSING_EXTRA_OR_REORDERED_PURCHASE_TICKETS')
        a,b,c=fixtures()
        b[0]=dataclasses.replace(b[0],orders=(b[0].orders[0],b[0].orders[0]))
        self.check(a,b,c,'MISSING_EXTRA_OR_REORDERED_PURCHASE_TICKETS')

    def test_duplicated_receipt_across_races_denied(self):
        a,b,c=fixtures()
        b[1]=dataclasses.replace(b[1],orders=(dataclasses.replace(
            b[1].orders[0],purchase_receipt_ref=b[0].orders[0].purchase_receipt_ref),b[1].orders[1]))
        self.check(a,b,c,'MISSING_OR_DUPLICATE_PURCHASE_RECEIPT')

    def test_forged_ranked_top_and_distribution_denied(self):
        a,b,c=fixtures()
        a[0]=dataclasses.replace(a[0],top_tickets=tuple(reversed(a[0].top_tickets)))
        self.check(a,b,c,'FORGED_OR_STALE_TOP_TICKET_ORDER')
        a,b,c=fixtures()
        d=list(a[0].ticket_distribution)
        d[0]=(d[0][0],d[0][1] + .01)
        a[0]=dataclasses.replace(a[0],ticket_distribution=tuple(d))
        self.check(a,b,c,'RANKING_DISTRIBUTION_INVALID')

    def test_unapproved_ranking_claim_never_promoted(self):
        a,b,c=fixtures()
        object.__setattr__(a[0],'buy_eligible',True)
        self.check(a,b,c,'UNTRUSTED_RANKING_AUTHORITY')

    def test_late_odds_and_missing_receipts_denied_by_ledger(self):
        a,b,c=fixtures()
        b[0]=dataclasses.replace(b[0],orders=(dataclasses.replace(
            b[0].orders[0],odds_observed_at=T0+timedelta(hours=2)), b[0].orders[1]))
        self.check(a,b,c,'LEDGER_MISSING_OR_LATE_PURCHASE_EVIDENCE')
        a,b,c=fixtures()
        b[0]=dataclasses.replace(b[0],original_sha256='0'*64)
        self.check(a,b,c,'LEDGER_PREDECISION_RAW_SOURCE_UNBOUND')

    def test_missing_or_pending_result_and_void_pruning_refused(self):
        a,b,c=fixtures()
        self.check(a,b,c[:1],'LEDGER_MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')
        self.check(a,b,[c[0],dataclasses.replace(c[1],status='PENDING')],
                   'LEDGER_UNRESOLVED_OR_INVALID_SETTLEMENT')
        self.check(a[:1],b[:1],c[:1],'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD')
        # A postrace VOID may not remove only the result while retaining 2 buys.
        self.check(a,b,c[:1],'LEDGER_MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')

    def test_inconsistent_refund_rejected_and_report_frozen(self):
        a,b,c=fixtures()
        wrong_returns=tuple(dataclasses.replace(x,refund_yen=0) for x in c[1].returns)
        c[1]=dataclasses.replace(c[1],returns=wrong_returns)
        self.check(a,b,c,'LEDGER_VOID_REFUNDS_INCOMPLETE')
        a,b,c=fixtures()
        ans=self.check(a,b,c,'SYNTHETIC_SHADOW_CASH_JOIN_HARD_HOLD')
        with self.assertRaises(dataclasses.FrozenInstanceError):ans.buy_eligible=True

if __name__ == '__main__':
    unittest.main()
