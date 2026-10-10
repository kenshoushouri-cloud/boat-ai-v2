"""Synthetic result text and refund rules; never real official-byte provenance."""
import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from v5.offline_trifecta_refund_section import (
    FrozenResultSection, HypotheticalTicket, inspect_offline_refund_section,
)

D = datetime(2026, 10, 10, 10, tzinfo=timezone(timedelta(hours=9)))
RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/raceresult?hd=20261010&jcd=03&rno=4'
OK = 'MOCK_EXPLICIT_REFUND_BOATS_PARSED_SOURCE_UNVERIFIED_HARD_HOLD'
TICKETS = (HypotheticalTicket('1-2-3', 100), HypotheticalTicket('2-3-4', 200),
           HypotheticalTicket('4-5-6', 100))


def fixture(boats='1', *, prefix='', suffix=''):
    raw = ('<div>結果</div><div>3連単 2-3-4 ¥3,500</div><div>'
           + prefix + '</div><div>返還</div><div>' + boats
           + '</div><div>決まり手</div><div>' + suffix + '</div>').encode('utf-8')
    return FrozenResultSection(URL, raw, hashlib.sha256(raw).hexdigest(),
                               D+timedelta(minutes=20), D+timedelta(hours=4))


class TestRefundSection(unittest.TestCase):
    def check(self, result=None, *, reason=OK, tickets=TICKETS, rid=RID, enabled=True):
        v = inspect_offline_refund_section(race_id=rid, result=fixture() if result is None else result,
                                          hypothetical_tickets=tickets, enabled=enabled)
        self.assertEqual(v.reason, reason)
        for name in ('official_result_authenticated','ticket_refunds_officially_verified',
                     'original_first_write_verified','roi_eligible','selection_eligible',
                     'forward_eligible','buy_eligible'):
            self.assertIs(getattr(v, name), False)
        self.assertTrue(v.no_network_sql_write)
        if reason != OK:
            self.assertFalse(v.section_shape_consistent)
            self.assertEqual(v.mock_refund_yen, 0)
        return v

    def test_one_explicit_refund_boat(self):
        x = self.check()
        self.assertEqual((x.mock_refund_boats,x.mock_refunded_tickets,x.mock_refund_yen),
                         ((1,),('1-2-3',),100))
        with self.assertRaises(dataclasses.FrozenInstanceError): x.buy_eligible=True

    def test_two_refund_boats_combined(self):
        x=self.check(fixture('1 4'))
        self.assertEqual((x.mock_refund_boats,x.mock_refunded_tickets,x.mock_refund_yen),
                         ((1,4),tuple(t.ticket for t in TICKETS),400))

    def test_explicit_empty_refund_section(self):
        x=self.check(fixture(''))
        self.assertEqual((x.mock_refund_boats,x.mock_refunded_tickets,x.mock_refund_yen),((),(),0))

    def test_footnote_does_not_become_refund(self):
        x=self.check(fixture('1',suffix='備考 返還艇あり 6'))
        self.assertEqual(x.mock_refund_boats,(1,))

    def test_default_disabled(self):
        v=inspect_offline_refund_section(race_id=RID,result=fixture(),hypothetical_tickets=TICKETS)
        self.assertEqual(v.reason,'REFUND_SECTION_DISABLED')

    def test_truthy_not_enabled(self):
        for e in (1, False, 'yes', None):
            with self.subTest(e=e): self.check(enabled=e,reason='REFUND_SECTION_DISABLED')

    def test_missing_refund_heading_rejected(self):
        x=fixture('1');raw=x.raw_bytes.replace('返還'.encode(),b'Refund')
        self.check(dataclasses.replace(x,raw_bytes=raw,raw_sha256=hashlib.sha256(raw).hexdigest()),
                   reason='EXPLICIT_REFUND_SECTION_NOT_ISOLATED')

    def test_unknown_section_not_forced(self):
        self.check(fixture('1 返還艇あり'),reason='REFUND_SECTION_AMBIGUOUS')

    def test_duplicate_refund_boat_rejected(self):
        self.check(fixture('1 1'),reason='REFUND_SECTION_AMBIGUOUS')

    def test_full_race_invalidation_rejected(self):
        self.check(fixture('1',prefix='3連単不成立'),reason='FULL_RACE_OR_TRIFECTA_INVALID_UNRESOLVED')

    def test_hash_and_url_identity(self):
        x=fixture()
        self.check(dataclasses.replace(x,raw_sha256='0'*64),reason='RESULT_BYTES_SHA_MISMATCH')
        self.check(dataclasses.replace(x,source_url=URL.replace('rno=4','rno=5')),
                   reason='RESULT_URL_RACE_MISMATCH')

    def test_claimed_authority_does_not_promote(self):
        self.check(dataclasses.replace(fixture(),purported_first_write=True),
                   reason='UNTRUSTED_AUTHORITY_CLAIM')

    def test_invalid_ticket_denied(self):
        self.check(tickets=(HypotheticalTicket('1-1-3', 100),),
                   reason='MOCK_TICKETS_OR_STAKES_INVALID')

    def test_cutoff_is_prior_to_result_observation(self):
        self.check(dataclasses.replace(fixture(),response_completed_at=D),
                   reason='RESULT_NOT_AFTER_DECISION')


if __name__ == '__main__': unittest.main()
