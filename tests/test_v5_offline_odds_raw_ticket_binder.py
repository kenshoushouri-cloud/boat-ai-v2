"""Pure synthetic original-byte ticket/odds binding, exact real parser source."""
from __future__ import annotations

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from itertools import permutations

from v5.offline_odds_raw_ticket_binder import (
    MockRawOddsCapture, bind_offline_odds_raw_tickets,
)
from official_odds3t_parser import parse_official_odds3t

JST = timezone(timedelta(hours=9))
T = datetime(2026,10,10,10,0,tzinfo=JST)
RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/odds3t?rno=4&jcd=03&hd=20261010'
ODDS = {
    '-'.join(map(str,t)): round(3.0 + i * 0.1, 1)
    for i,t in enumerate(permutations(range(1,7),3))
}


def fake_html(odds=ODDS):
    return ('<html><h2>3連単オッズ</h2>' +
            ''.join(f'<p>{t} {v:.1f}</p>' for t,v in odds.items()) +
            '</html>').encode('utf-8')


def fixture():
    body = fake_html()
    digest = hashlib.sha256(body).hexdigest()
    capture = MockRawOddsCapture(
        'official_odds3t', URL, URL, 200, body, digest, digest,
        T, T+timedelta(minutes=2), T+timedelta(minutes=2),
        T+timedelta(minutes=3), T+timedelta(minutes=4),
        T+timedelta(hours=1), 'fictional-first-write-receipt',
        'IMMUTABLE_FIRST_WRITE', 'official_odds3t')
    return capture, dict(ODDS)


def rehash(capture, body):
    digest = hashlib.sha256(body).hexdigest()
    return dataclasses.replace(capture, raw_bytes=body, raw_sha256=digest,
                               readback_sha256=digest)


class TestOfflineOddsRawTicketBinder(unittest.TestCase):
    def check(self, capture=None, prices=None, race_id=RID,
              reason='MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD'):
        sample, odds = fixture()
        result = bind_offline_odds_raw_tickets(
            race_id, sample if capture is None else capture,
            odds if prices is None else prices,
        )
        self.assertEqual(result.reason, reason)
        for flag in ('original_official_http_verified','independently_authenticated_receipt',
                     'real_first_observed_verified','six_active_starts_confirmed',
                     'selection_eligible','beforeinfo_first_write_eligible',
                     'forward_eligible','buy_eligible'):
            self.assertIs(getattr(result,flag), False)
        self.assertIs(result.mock_raw_ticket_parity,
                      reason=='MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD')
        if reason!='MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD':
            self.assertEqual(result.checked_ticket_count,0)
        return result

    def test_120_tickets_exact_real_parser_and_frozen_result(self):
        capture,odds=fixture()
        self.assertEqual(parse_official_odds3t(capture.raw_bytes.decode()),odds)
        verdict=self.check(capture, odds)
        self.assertEqual((verdict.race_id,verdict.checked_ticket_count),(RID,120))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            verdict.buy_eligible=True

    def test_wrong_race_date_venue_or_race_number_in_url(self):
        cap,_=fixture()
        for url in (URL.replace('rno=4','rno=3'),URL.replace('jcd=03','jcd=04'),
                    URL.replace('hd=20261010','hd=20261009')):
            with self.subTest(url=url):
                self.check(dataclasses.replace(cap, requested_url=url,final_url=url),
                           reason='OFFICIAL_ODDS_URL_RACE_ID_MISMATCH')

    def test_noncanonical_or_suspicious_urls_and_redirect(self):
        cap,_=fixture()
        for url in (URL+'&jcd=03',URL+'&unexpected=1',URL.replace('rno=4','rno=04'),
                    URL.replace('https:', 'http:'),
                    URL.replace('www.boatrace.jp','www.boatrace.jp.evil.net'),
                    URL.replace('www.boatrace.jp','www.boatrace.jp:444'),
                    URL.replace('www.boatrace.jp','attacker@www.boatrace.jp'),
                    URL+'#frag', URL.replace('odds3t','racelist')):
            self.check(dataclasses.replace(cap,requested_url=url,final_url=url),
                       reason='OFFICIAL_ODDS_URL_RACE_ID_MISMATCH')
        self.check(dataclasses.replace(cap,final_url=URL+'&redirect=1'),
                   reason='OFFICIAL_ODDS_URL_RACE_ID_MISMATCH')

    def test_invalid_expected_race_id_fails_closed(self):
        cap,_=fixture()
        for rid in ('','20260230_03_04','20250630_03_04','20261010_99_01'):
            self.check(cap,race_id=rid,reason='EXPECTED_RACE_ID_INVALID')

    def test_http_errors_and_base_fallback_denied(self):
        cap,_=fixture()
        for updates in ({'http_status':404},{'http_status':True},
                        {'source':'v2_odds_trifecta_fallback_complete'},
                        {'odds_selection_source':'v2_odds_trifecta_fallback_complete'}):
            self.check(dataclasses.replace(cap,**updates),reason='UNVERIFIED_OR_FALLBACK_SOURCE')

    def test_upsert_or_missing_mock_first_write_does_not_pass(self):
        cap,_=fixture()
        for updates in ({'write_mode':'UPSERT'},{'receipt_ref':''}):
            self.check(dataclasses.replace(cap,**updates),
                       reason='ORIGINAL_FIRST_WRITE_RECEIPT_MISSING')

    def test_raw_digest_tamper_and_readback_mismatch(self):
        cap,_=fixture()
        for updates in ({'raw_sha256':'0'*64},{'readback_sha256':'0'*64},
                        {'raw_bytes':cap.raw_bytes+b'OTHER'}):
            self.check(dataclasses.replace(cap,**updates),
                       reason='RAW_OR_READBACK_SHA256_MISMATCH')

    def test_bad_first_seen_after_deadline_and_naive_clocks(self):
        cap,_=fixture()
        for updates in ({'readback_at':cap.cutoff_at},
                        {'response_completed_at':cap.first_observed_at-timedelta(seconds=1)},
                        {'first_observed_at':cap.first_observed_at.replace(tzinfo=None)},
                        {'cutoff_at':cap.cutoff_at+timedelta(days=1)}):
            self.check(dataclasses.replace(cap,**updates),
                       reason='UNPROVEN_PREDEADLINE_FIRST_OBSERVATION_CLOCK')

    def test_claimed_price_mismatch_cannot_reattach_other_values(self):
        cap,odds=fixture()
        odds['1-2-3']=odds['1-2-3']+0.1
        self.check(cap,odds,reason='CLAIMED_ODDS_DO_NOT_MATCH_ORIGINAL')

    def test_partial_or_noncanonical_claim_rejected(self):
        cap,odds=fixture()
        odds.pop('1-2-3')
        self.check(cap,odds,reason='INVALID_OR_INCOMPLETE_CLAIMED_TICKET_SET')
        cap,odds=fixture()
        odds['1-2-3']=float('nan')
        self.check(cap,odds,reason='INVALID_OR_INCOMPLETE_CLAIMED_TICKET_SET')

    def test_partial_original_html_even_if_claim_is_complete(self):
        cap,odds=fixture()
        short=dict(odds)
        short.pop('1-2-3')
        self.check(rehash(cap,fake_html(short)),odds,
                   reason='PARTIAL_OR_UNPARSEABLE_ORIGINAL_ODDS')

    def test_duplicate_explicit_original_ticket_is_ambiguous(self):
        cap,odds=fixture()
        body=cap.raw_bytes.replace(b'</html>',b'<p>1-2-3 888.8</p></html>')
        self.check(rehash(cap,body),odds,
                   reason='AMBIGUOUS_DUPLICATE_TICKET_IN_ORIGINAL')

    def test_bad_utf8_raw_and_malformed_empty_html(self):
        cap,odds=fixture()
        self.check(rehash(cap,b'\xff\xfe'),odds,reason='ORIGINAL_HTML_DECODE_FAILED')
        self.check(rehash(cap,b'<html>No trifecta tickets</html>'),odds,
                   reason='PARTIAL_OR_UNPARSEABLE_ORIGINAL_ODDS')

    def test_caller_can_forge_coherent_source_so_never_live_eligible(self):
        # URL is a user-held assertion; no independent HTTP witness exists.
        self.check()

    def test_legacy_historical_date_is_not_automatically_prospective(self):
        cap,odds=fixture()
        rid='20250701_03_04'
        url=URL.replace('20261010','20250701')
        clocks={name:getattr(cap,name).replace(year=2025,month=7,day=1)
                for name in ('request_started_at','response_completed_at',
                             'first_observed_at','committed_at','readback_at','cutoff_at')}
        cap=dataclasses.replace(cap,requested_url=url,final_url=url,**clocks)
        v=self.check(cap,odds,race_id=rid)
        self.assertFalse(v.real_first_observed_verified)

if __name__=='__main__':
    unittest.main()
