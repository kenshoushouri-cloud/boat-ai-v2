"""Real offline parser -> raw-HTML binder -> opt-in plan integration.

Uses fictional 120-ticket HTML, NEVER an HTTP GET, DB read/write, or betting.
Every positive mock parity verdict must keep all live authority flags FALSE.
"""
from __future__ import annotations

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from itertools import permutations

from official_odds3t_parser import parse_official_odds3t
from v5.offline_odds_raw_ticket_binder import MockRawOddsCapture
from v5.offline_odds_capture_plan import (
    ProvisionalOddsReceipt, PROPOSAL_CONTRACT, prepare_offline_odds_capture_plan,
)

RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/odds3t?rno=4&jcd=03&hd=20261010'
JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 10, 10, tzinfo=JST)
ODDS = {'-'.join(map(str, x)): round(3 + i * .1, 1)
        for i, x in enumerate(permutations(range(1, 7), 3))}


def html(prices=ODDS):
    return ('<html><h2>3連単オッズ</h2>' +
            ''.join(f'<p>{ticket} {odds:.1f}</p>' for ticket, odds in prices.items()) +
            '</html>').encode('utf-8')


def fixture():
    raw = html()
    sha = hashlib.sha256(raw).hexdigest()
    capture = MockRawOddsCapture(
        'official_odds3t', URL, URL, 200, raw, sha, sha,
        NOW, NOW + timedelta(minutes=2), NOW + timedelta(minutes=2),
        NOW + timedelta(minutes=3), NOW + timedelta(minutes=4),
        NOW + timedelta(hours=1), 'fictional-first-write',
        'IMMUTABLE_FIRST_WRITE', 'official_odds3t',
    )
    proposal = ProvisionalOddsReceipt(
        PROPOSAL_CONTRACT, RID, URL, capture.response_completed_at, sha,
    )
    return capture, proposal, dict(ODDS)


def rehash(capture, raw):
    sha = hashlib.sha256(raw).hexdigest()
    return dataclasses.replace(capture, raw_bytes=raw, raw_sha256=sha, readback_sha256=sha)


class ActualDependencyOfflineIntegration(unittest.TestCase):
    def evaluate(self, capture=None, receipt=None, prices=None, enabled=True, expected='ODDS_CAPTURE_PLAN_SHADOW_ONLY'):
        c, r, p = fixture()
        out = prepare_offline_odds_capture_plan(
            expected_race_id=RID, capture=c if capture is None else capture,
            provisional_receipt=r if receipt is None else receipt,
            claimed_ticket_odds=p if prices is None else prices,
            enabled=enabled,
        )
        self.assertEqual(out.reason, expected)
        self.assertTrue(out.no_get and out.no_sql and out.no_write)
        for k in ('source_authenticated', 'independently_verified_first_write',
                  'six_active_starts_confirmed','selection_eligible',
                  'beforeinfo_first_write_eligible','forward_eligible','buy_eligible'):
            self.assertIs(getattr(out, k), False)
        if expected != 'ODDS_CAPTURE_PLAN_SHADOW_ONLY':
            self.assertEqual(out.parsed_tickets_sha256, '')
            self.assertEqual(out.parsed_ticket_count, 0)
        return out

    def test_raw_real_parser_emits_exact_120(self):
        raw = html()
        self.assertEqual(parse_official_odds3t(raw.decode('utf-8')), ODDS)
        self.assertEqual(len(ODDS), 120)

    def test_default_off_is_never_promoted(self):
        c,r,p = fixture()
        out = prepare_offline_odds_capture_plan(expected_race_id=RID, capture=c,
             claimed_ticket_odds=p, provisional_receipt=r)
        self.assertEqual(out.reason, 'OFFLINE_ODDS_CAPTURE_DISABLED')
        self.assertFalse(out.buy_eligible)

    def test_full_dependency_mock_parity_and_deterministic_digest(self):
        a = self.evaluate()
        b = self.evaluate()
        self.assertEqual((a.race_id, a.parsed_ticket_count, a.source_url), (RID, 120, URL))
        self.assertTrue(a.mock_raw_parity)
        self.assertEqual(a.parsed_tickets_sha256, b.parsed_tickets_sha256)
        self.assertEqual(len(a.parsed_tickets_sha256), 64)

    def test_changed_claimed_price_rejected_by_real_binder(self):
        c,r,p = fixture()
        p['1-2-3'] += .1
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_CLAIMED_ODDS_DO_NOT_MATCH_ORIGINAL')

    def test_changed_raw_but_unchanged_sha_rejected(self):
        c,r,p = fixture()
        self.evaluate(dataclasses.replace(c, raw_bytes=c.raw_bytes+b'a'),r,p,
                      expected='ODDS_RAW_BINDER_RAW_OR_READBACK_SHA256_MISMATCH')

    def test_rehashed_partial_html_rejected_by_real_parser(self):
        c,r,p = fixture()
        new = dict(ODDS); new.pop('1-2-3')
        c = rehash(c, html(new))
        r = dataclasses.replace(r, raw_sha256=c.raw_sha256)
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_PARTIAL_OR_UNPARSEABLE_ORIGINAL_ODDS')

    def test_rehashed_duplicate_html_rejected(self):
        c,r,p = fixture()
        c = rehash(c, c.raw_bytes.replace(b'</html>', b'<p>1-2-3 800.0</p></html>'))
        r = dataclasses.replace(r, raw_sha256=c.raw_sha256)
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_AMBIGUOUS_DUPLICATE_TICKET_IN_ORIGINAL')

    def test_race_query_mismatch_rejected_by_real_binder(self):
        c,r,p=fixture()
        url=URL.replace('rno=4','rno=5')
        c=dataclasses.replace(c,requested_url=url,final_url=url)
        r=dataclasses.replace(r,source_url=url)
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_OFFICIAL_ODDS_URL_RACE_ID_MISMATCH')

    def test_base_odds_fallback_rejected(self):
        c,r,p=fixture()
        c=dataclasses.replace(c, odds_selection_source='v2_odds_trifecta_fallback_complete')
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_UNVERIFIED_OR_FALLBACK_SOURCE')

    def test_cutoff_before_readback_rejected(self):
        c,r,p=fixture()
        c=dataclasses.replace(c,cutoff_at=c.readback_at)
        self.evaluate(c,r,p,expected='ODDS_RAW_BINDER_UNPROVEN_PREDEADLINE_FIRST_OBSERVATION_CLOCK')

    def test_receipt_claiming_first_write_refused(self):
        c,r,p=fixture()
        r=dataclasses.replace(r, first_write_confirmed=True)
        self.evaluate(c,r,p,expected='PREMATURE_ODDS_CAPTURE_AUTHORITY_CLAIM')

    def test_receipt_claiming_buy_refused(self):
        c,r,p=fixture()
        r=dataclasses.replace(r, buy_eligible=True)
        self.evaluate(c,r,p,expected='PREMATURE_ODDS_CAPTURE_AUTHORITY_CLAIM')


if __name__ == '__main__':
    unittest.main()
