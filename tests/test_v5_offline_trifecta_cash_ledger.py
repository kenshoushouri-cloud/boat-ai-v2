"""Synthetic-only cash/odds/refund cohort tests. Never actual BUY/GET/DB."""
from __future__ import annotations

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_trifecta_cash_ledger import (
    MockOrder, MockTicketReturn, PredeadlineMockRace, PostraceMockResult,
    audit_synthetic_trifecta_cash_ledger,
)

JST = timezone(timedelta(hours=9))
RACE = '20261010_03_01'
RACE2 = '20261010_03_02'
SRC = b'fictional source not official data'
RES = b'fictional result not official data'
D = datetime(2026, 10, 10, 10, 0, tzinfo=JST)


def preb(rid=RACE):
    return PredeadlineMockRace(
        rid, D+timedelta(hours=1), D, D+timedelta(minutes=20),
        'mock-capture', SRC, hashlib.sha256(SRC).hexdigest(),
        (MockOrder('1-2-3', 100, 8.4, D+timedelta(minutes=2),
                   D+timedelta(minutes=5), 'fictional-order-1'),
         MockOrder('1-3-2', 200, 10.8, D+timedelta(minutes=3),
                   D+timedelta(minutes=6), 'fictional-order-2')),
    )


def post(rid=RACE, *, status='OFFICIAL', winner='1-2-3'):
    orders = preb(rid).orders
    if status == 'VOID':
        returns = tuple(MockTicketReturn(x.ticket, 0, x.stake_yen) for x in orders)
        winner = None
    else:
        returns = (MockTicketReturn('1-2-3', 840, 0), MockTicketReturn('1-3-2', 0, 0))
    return PostraceMockResult(rid, D+timedelta(hours=4), 'fake-result-source',
                              RES, hashlib.sha256(RES).hexdigest(),
                              status, winner, returns)


class OfflineLedgerTests(unittest.TestCase):
    def check(self, pre=None, results=None, reason=None):
        verdict = audit_synthetic_trifecta_cash_ledger(
            [preb()] if pre is None else pre,
            [post()] if results is None else results,
        )
        if reason is not None:
            self.assertEqual(verdict.reason, reason)
        for key in ('independently_authenticated_source', 'actual_purchase_verified',
                    'six_active_starts_confirmed', 'selection_eligible',
                    'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(verdict, key), False)
        return verdict

    def test_synthetic_return_math_and_daily_ticket_counts(self):
        v = self.check(reason='SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED')
        self.assertTrue(v.mock_shape_consistent)
        self.assertEqual((v.predecision_races, v.purchased_tickets, v.winning_tickets), (1, 2, 1))
        self.assertEqual((v.synthetic_paid_yen, v.synthetic_returns_yen,
                          v.synthetic_net_yen), (300, 840, 540))
        self.assertEqual((v.synthetic_roi_pct, v.synthetic_ticket_hit_pct), (280., 50.))
        self.assertEqual((v.days[0].candidate_races, v.days[0].purchased_tickets,
                          v.days[0].net_yen), (1, 2, 540))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.buy_eligible = True

    def test_void_remains_original_cohort_and_full_cash_refund(self):
        v = self.check(pre=[preb(), preb(RACE2)], results=[post(RACE2, status='VOID'), post()],
                       reason='SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED')
        self.assertEqual((v.predecision_races, v.official_races, v.void_races), (2, 1, 1))
        self.assertEqual((v.purchased_tickets, v.synthetic_paid_yen,
                          v.synthetic_returns_yen, v.synthetic_net_yen), (4, 600, 1140, 540))
        self.assertEqual(v.days[0].candidate_races, 2)
        self.assertEqual(v.synthetic_ticket_hit_pct, 25.)

    def test_missing_postrace_or_pending_no_economics(self):
        v = self.check(results=[], reason='MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')
        self.assertEqual(v.synthetic_paid_yen, 0)
        self.check(results=[dataclasses.replace(post(), status='PENDING')],
                   reason='UNRESOLVED_OR_INVALID_SETTLEMENT')

    def test_missing_purchase_ticket_or_receipt_holds(self):
        self.check(pre=[dataclasses.replace(preb(), orders=())],
                   reason='MISSING_PURCHASE_RECEIPTS_OR_ORDERS')
        x = preb()
        orders = (dataclasses.replace(x.orders[0], purchase_receipt_ref=''), x.orders[1])
        self.check(pre=[dataclasses.replace(x, orders=orders)],
                   reason='MISSING_OR_LATE_PURCHASE_EVIDENCE')

    def test_missing_predeadline_odds_or_late_purchase_holds(self):
        x = preb()
        for bad in (float('nan'), 0., float('inf')):
            orders = (dataclasses.replace(x.orders[0], odds_decimal=bad), x.orders[1])
            self.check(pre=[dataclasses.replace(x, orders=orders)],
                       reason='MISSING_OR_INVALID_PREDEADLINE_ODDS')
        orders = (dataclasses.replace(x.orders[0], purchase_executed_at=x.cutoff_at), x.orders[1])
        self.check(pre=[dataclasses.replace(x, orders=orders)],
                   reason='MISSING_OR_LATE_PURCHASE_EVIDENCE')

    def test_bad_predecision_provenance_and_clock_holds(self):
        self.check(pre=[dataclasses.replace(preb(), original_sha256='0'*64)],
                   reason='PREDECISION_RAW_SOURCE_UNBOUND')
        self.check(pre=[dataclasses.replace(preb(), frozen_at=preb().cutoff_at)],
                   reason='PREDECISION_CLOCK_INVALID')

    def test_bad_refund_void_or_payout_holds(self):
        r = post(status='VOID')
        changed = (MockTicketReturn('1-2-3', 0, 0), r.returns[1])
        self.check(results=[dataclasses.replace(r, returns=changed)],
                   reason='VOID_REFUNDS_INCOMPLETE')
        r = post()
        changed = (MockTicketReturn('1-2-3', 0, 0), r.returns[1])
        self.check(results=[dataclasses.replace(r, returns=changed)],
                   reason='OFFICIAL_PAYOUT_OR_REFUND_INCONSISTENT')

    def test_race_mismatch_duplicate_and_incomplete_returns_hold(self):
        self.check(results=[post(RACE2)], reason='SETTLEMENT_RACE_SET_MISMATCH')
        self.check(pre=[preb(), preb()], reason='DUPLICATE_PREDECISION_RACE')
        self.check(results=[dataclasses.replace(post(), returns=(post().returns[0],))],
                   reason='MISSING_SETTLEMENT_OR_REFUND_EVIDENCE')

    def test_unhashable_settlement_race_id_fails_closed(self):
        self.check(results=[dataclasses.replace(post(), race_id=[])],
                   reason='SETTLEMENT_RACE_SET_MISMATCH')

    def test_bad_ticket_stake_and_duplicate_tickets_hold(self):
        x = preb()
        order = dataclasses.replace(x.orders[0], ticket='1-1-3')
        self.check(pre=[dataclasses.replace(x, orders=(order, x.orders[1]))], reason='INVALID_TICKET')
        order = dataclasses.replace(x.orders[0], stake_yen=150)
        self.check(pre=[dataclasses.replace(x, orders=(order, x.orders[1]))], reason='INVALID_STAKE')
        self.check(pre=[dataclasses.replace(x, orders=(x.orders[0], x.orders[0]))], reason='DUPLICATE_TICKET')

    def test_fake_postrace_source_must_exist_after_cutoff(self):
        r = post()
        self.check(results=[dataclasses.replace(r, observed_at=preb().cutoff_at)],
                   reason='POSTRACE_SOURCE_OR_CLOCK_UNVERIFIED')
        self.check(results=[dataclasses.replace(r, raw_result_sha256='0'*64)],
                   reason='POSTRACE_SOURCE_OR_CLOCK_UNVERIFIED')

    def test_valid_nonwinning_ticket_and_partial_refund(self):
        r = post()
        # The official winning ticket might not have been purchased.
        losing = (MockTicketReturn('1-2-3', 0, 0), MockTicketReturn('1-3-2', 0, 200))
        v = self.check(results=[dataclasses.replace(r, winning_ticket='2-1-3', returns=losing)],
                       reason='SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED')
        self.assertEqual((v.synthetic_paid_yen, v.synthetic_returns_yen,
                          v.synthetic_net_yen, v.winning_tickets), (300, 200, -100, 0))

    def test_candidate_count_not_auto_capped_to_v4_six_or_top_two(self):
        x = preb()
        one = dataclasses.replace(x, orders=(x.orders[0],))
        r = post()
        single = dataclasses.replace(r, returns=(r.returns[0],))
        v = self.check(pre=[one], results=[single],
                       reason='SYNTHETIC_CASH_LEDGER_SHAPE_HOLD_UNAUTHENTICATED')
        self.assertEqual((v.predecision_races, v.purchased_tickets), (1, 1))


if __name__ == '__main__':
    unittest.main()
