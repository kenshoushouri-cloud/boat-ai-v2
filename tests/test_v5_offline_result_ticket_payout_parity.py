"""Byte-bound synthetic result HTML tests; no publisher access or real refund proof."""
import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from v5.offline_result_ticket_payout_parity import ClaimedResultHtml, compare_result_html_payout

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 10, 10, tzinfo=JST)
RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/raceresult?rno=4&jcd=03&hd=20261010'
OK = 'MOCK_RESULT_TICKET_PAYOUT_PARITY_REFUND_UNVERIFIED_HARD_HOLD'


def make(text='<table><tr><td>3連単</td><td>1-2-3</td><td>¥12,340円</td></tr></table>'):
    raw = text.encode('utf-8')
    return ClaimedResultHtml(URL, raw, hashlib.sha256(raw).hexdigest(),
                             T + timedelta(hours=4), T+timedelta(hours=1),
                             '1-2-3', 12340)


class ResultParityTests(unittest.TestCase):
    def check(self, x=None, *, reason=OK, rid=RID, enabled=True):
        v = compare_result_html_payout(expected_race_id=rid, capture=x or make(), enabled=enabled)
        self.assertEqual(v.reason, reason)
        for name in ('refund_ticket_details_verified','official_source_authenticated',
                     'original_first_write_verified','economic_roi_eligible',
                     'selection_eligible','forward_eligible','buy_eligible'):
            self.assertIs(getattr(v, name), False)
        self.assertTrue(v.no_get_sql_write)
        if reason != OK:
            self.assertFalse(v.content_ticket_payout_parity)
            self.assertEqual((v.race_id, v.parsed_payout_yen), ('', 0))
        return v

    def test_fixture_content_match_but_hard_hold(self):
        v = self.check()
        self.assertEqual((v.race_id, v.parsed_ticket, v.parsed_payout_yen),
                         (RID, '1-2-3', 12340))
        with self.assertRaises(dataclasses.FrozenInstanceError):v.buy_eligible = True

    def test_off_by_default(self):
        v=compare_result_html_payout(expected_race_id=RID,capture=make())
        self.assertEqual(v.reason,'RESULT_HTML_PARITY_DISABLED')

    def test_truthy_is_not_explicit_opt_in(self):
        for e in (False,1,None,'true'):
            with self.subTest(e=e):self.check(reason='RESULT_HTML_PARITY_DISABLED',enabled=e)

    def test_raw_digest_tamper(self):
        x=make(); self.check(dataclasses.replace(x,raw_bytes=x.raw_bytes+b'x'),reason='RESULT_ORIGINAL_BYTES_SHA_MISMATCH')
        self.check(dataclasses.replace(x,raw_sha256='0'*64),reason='RESULT_ORIGINAL_BYTES_SHA_MISMATCH')

    def test_url_mismatch_or_redirect(self):
        self.check(dataclasses.replace(make(),source_url=URL.replace('rno=4','rno=5')),
                   reason='RESULT_URL_RACE_ID_MISMATCH')
        self.check(dataclasses.replace(make(),redirected=True),reason='RESULT_PREMATURE_AUTHORITY_CLAIM')

    def test_premature_proof_claim(self):
        self.check(dataclasses.replace(make(),claimed_first_write_verified=True),
                   reason='RESULT_PREMATURE_AUTHORITY_CLAIM')
        self.check(dataclasses.replace(make(),claimed_official_authenticated=True),
                   reason='RESULT_PREMATURE_AUTHORITY_CLAIM')

    def test_missing_or_ambiguous_rows(self):
        self.check(make('<p>3連単 オッズなし</p>'),reason='RESULT_MISSING_OR_AMBIGUOUS_TRIFECTA_ROW')
        self.check(make('<p>3連単 1-2-3 ¥12,340円 3連単 1-2-3 ¥12,340円</p>'),
                   reason='RESULT_MISSING_OR_AMBIGUOUS_TRIFECTA_ROW')

    def test_wrong_claim_ticket_and_amount(self):
        self.check(dataclasses.replace(make(),claimed_winning_ticket='1-3-2'),
                   reason='RESULT_CLAIM_NOT_IN_ORIGINAL_HTML')
        self.check(dataclasses.replace(make(),claimed_trifecta_payout_yen=12341),
                   reason='RESULT_CLAIM_NOT_IN_ORIGINAL_HTML')

    def test_bad_ticket_or_payout(self):
        self.check(make('<p>3連単 1-1-3 ¥12,340</p>'),reason='RESULT_TRIFECTA_TICKET_OR_PAYOUT_INVALID')
        self.check(make('<p>3連単 1-2-3 ¥0</p>'),reason='RESULT_TRIFECTA_TICKET_OR_PAYOUT_INVALID')

    def test_cancel_and_invalid_reason_deny(self):
        self.check(make('<p>レース中止 3連単 1-2-3 ¥12,340</p>'),
                   reason='RESULT_CANCEL_OR_TRIFECTA_INVALID_UNRESOLVED')

    def test_late_clock_missing(self):
        self.check(dataclasses.replace(make(),response_completed_at=T+timedelta(minutes=30)),
                   reason='RESULT_NOT_POSTRACE_OR_RACE_DAY_MISMATCH')

    def test_early_date_invalid(self):
        self.check(rid='20260230_03_04',reason='RESULT_RACE_OR_CLOCK_INVALID')

    def test_refund_heading_does_not_prove_refund_amounts(self):
        self.check(make('<p>3連単 1-2-3 ¥12,340円 返還欄 F艇番4</p>'))

    def test_oversize_bytes_fail(self):
        x=make();raw=b'x'*(2_097_153)
        self.check(dataclasses.replace(x,raw_bytes=raw,raw_sha256=hashlib.sha256(raw).hexdigest()),
                   reason='RESULT_ORIGINAL_BYTES_SHA_MISMATCH')


if __name__ == '__main__': unittest.main()
