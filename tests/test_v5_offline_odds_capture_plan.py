"""Offline-only focused adapter contract tests; binder dependency is a stub.

The real GitHub raw binder is unchanged and its own 15 synthetic tests have
already been run separately. These tests verify the opt-in orchestration seam,
including the arguments given to the binder, without network or DB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from itertools import permutations
from unittest.mock import patch

# Scoped dependency stub only; no false claim of actual raw HTML parsing here.
BINDER_IMPORT = 'v5.offline_odds_raw_ticket_binder'
mock_binder = types.ModuleType(BINDER_IMPORT)


@dataclasses.dataclass(frozen=True, slots=True)
class MockRawOddsCapture:
    requested_url: str
    raw_sha256: str
    response_completed_at: datetime


@dataclasses.dataclass(frozen=True, slots=True)
class BinderResult:
    reason: str
    race_id: str
    mock_raw_ticket_parity: bool = True
    checked_ticket_count: int = 120
    original_official_http_verified: bool = False
    independently_authenticated_receipt: bool = False
    real_first_observed_verified: bool = False
    six_active_starts_confirmed: bool = False
    selection_eligible: bool = False
    beforeinfo_first_write_eligible: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False


def binder(race_id, capture, claimed):
    return BinderResult('MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD', race_id)


mock_binder.MockRawOddsCapture = MockRawOddsCapture
mock_binder.bind_offline_odds_raw_tickets = binder
with patch.dict(sys.modules, {BINDER_IMPORT: mock_binder}):
    tested = importlib.import_module('v5.offline_odds_capture_plan')

JST = timezone(timedelta(hours=9))
RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/odds3t?rno=4&jcd=03&hd=20261010'
TIME = datetime(2026, 10, 10, 10, tzinfo=JST)
ODDS = {'-'.join(map(str, ticket)): round(4. + i*.1, 1)
        for i, ticket in enumerate(permutations(range(1,7),3))}
RAW = b'fictional raw content never fetched'
HASH = hashlib.sha256(RAW).hexdigest()


def fixture():
    c = MockRawOddsCapture(URL, HASH, TIME)
    p = tested.ProvisionalOddsReceipt(tested.PROPOSAL_CONTRACT, RID, URL, TIME, HASH)
    return c, p, dict(ODDS)


class OfflineOddsCapturePlanTests(unittest.TestCase):
    def audit(self, c=None, p=None, odds=None, enabled=True):
        cc, pp, oo = fixture()
        result = tested.prepare_offline_odds_capture_plan(
            expected_race_id=RID, capture=cc if c is None else c,
            provisional_receipt=pp if p is None else p,
            claimed_ticket_odds=oo if odds is None else odds, enabled=enabled,
        )
        for k, val in {'no_get': True, 'no_sql': True, 'no_write': True,
                       'source_authenticated': False,
                       'independently_verified_first_write': False,
                       'six_active_starts_confirmed': False, 'selection_eligible': False,
                       'beforeinfo_first_write_eligible': False,
                       'forward_eligible': False, 'buy_eligible': False}.items():
            self.assertIs(getattr(result, k), val)
        return result

    def test_default_disabled_rejects_without_binder_call(self):
        c,p,odds=fixture()
        with patch.object(tested,'bind_offline_odds_raw_tickets',side_effect=AssertionError('SHOULD NOT CALL')):
            v = tested.prepare_offline_odds_capture_plan(expected_race_id=RID,
                 capture=c,claimed_ticket_odds=odds,provisional_receipt=p)
        self.assertEqual(v.reason, 'OFFLINE_ODDS_CAPTURE_DISABLED')
        self.assertEqual(v.parsed_ticket_count,0)

    def test_opt_in_explicit_true_not_truthy(self):
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value):
                self.assertEqual(self.audit(enabled=value).reason, 'OFFLINE_ODDS_CAPTURE_DISABLED')

    def test_mock_success_still_hard_hold_and_stable_sha(self):
        a=self.audit()
        b=self.audit()
        self.assertEqual(a.reason,'ODDS_CAPTURE_PLAN_SHADOW_ONLY')
        self.assertTrue(a.mock_raw_parity)
        self.assertEqual((a.race_id,a.source_url,a.raw_sha256,a.parsed_ticket_count),
                         (RID,URL,HASH,120))
        self.assertEqual(a.parsed_tickets_sha256,b.parsed_tickets_sha256)
        self.assertEqual(len(a.parsed_tickets_sha256),64)
        with self.assertRaises(dataclasses.FrozenInstanceError):a.buy_eligible=True

    def test_binder_receives_same_unmodified_race_capture_prices(self):
        c,p,odds=fixture()
        original=dict(odds)
        with patch.object(tested,'bind_offline_odds_raw_tickets', wraps=binder) as spy:
            v=self.audit(c,p,odds)
            spy.assert_called_once_with(RID,c,odds)
        self.assertEqual(v.reason,'ODDS_CAPTURE_PLAN_SHADOW_ONLY')
        self.assertEqual(odds,original)

    def test_missing_or_forged_receipt_rejected(self):
        c,p,odds=fixture()
        self.assertEqual(self.audit(c,p={'raw_sha256':HASH},odds=odds).reason,
                         'PROVISIONAL_ODDS_RECEIPT_REQUIRED')
        self.assertEqual(self.audit(c='not a mock',p=p,odds=odds).reason,
                         'PROVISIONAL_ODDS_RECEIPT_REQUIRED')

    def test_positive_authority_claims_denied(self):
        c,p,odds=fixture()
        changes=({'first_observed_at':TIME}, {'first_write_confirmed':True},
                 {'readback_confirmed':True}, {'forward_eligible':True},
                 {'buy_eligible':True}, {'storage_executed':True},
                 {'http_executed':True})
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.audit(c,dataclasses.replace(p,**change),odds).reason,
                                 'PREMATURE_ODDS_CAPTURE_AUTHORITY_CLAIM')

    def test_receipt_wrong_race_or_url_rejected_before_binder(self):
        c,p,odds=fixture()
        for change in ({'race_id':'20261010_03_05'},
                       {'source_url':URL.replace('rno=4','rno=5')},
                       {'contract':'V5_LIVE_CAPTURE'}):
            with self.subTest(change=change), patch.object(tested,'bind_offline_odds_raw_tickets',side_effect=AssertionError):
                self.assertEqual(self.audit(c,dataclasses.replace(p,**change),odds).reason,
                                 'PROVISIONAL_RECEIPT_IDENTITY_OR_DIGEST_MISMATCH')

    def test_raw_sha_mismatch_fails_before_binder(self):
        c,p,odds=fixture()
        self.assertEqual(self.audit(c,dataclasses.replace(p,raw_sha256='0'*64),odds).reason,
                         'PROVISIONAL_RECEIPT_IDENTITY_OR_DIGEST_MISMATCH')

    def test_capture_timestamp_mismatch_fails_before_binder(self):
        c,p,odds=fixture()
        self.assertEqual(self.audit(c,dataclasses.replace(p,response_completed_at=TIME+timedelta(minutes=1)),odds).reason,
                         'PROVISIONAL_RECEIPT_IDENTITY_OR_DIGEST_MISMATCH')

    def test_binder_failure_denies_everything_and_no_digest(self):
        c,p,odds=fixture()
        with patch.object(tested,'bind_offline_odds_raw_tickets',return_value=BinderResult('CLAIMED_ODDS_DO_NOT_MATCH_ORIGINAL',RID,False,0)):
            result=self.audit(c,p,odds)
        self.assertEqual(result.reason,'ODDS_RAW_BINDER_CLAIMED_ODDS_DO_NOT_MATCH_ORIGINAL')
        self.assertEqual(result.parsed_tickets_sha256,'')
        self.assertEqual(result.race_id,'')

    def test_forged_binder_authority_rejected(self):
        c,p,odds=fixture()
        forged=BinderResult('MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD',RID,buy_eligible=True)
        with patch.object(tested,'bind_offline_odds_raw_tickets',return_value=forged):
            self.assertEqual(self.audit(c,p,odds).reason,'UNVERIFIED_ODDS_RAW_BINDER')

    def test_missing_prices_and_nan_rejected_on_stub_binder_pass(self):
        c,p,odds=fixture()
        self.assertEqual(self.audit(c,p,{key:v for key,v in list(odds.items())[:-1]}).reason,
                         'INVALID_CLAIMED_ODDS_DIGEST_INPUT')
        odds['1-2-3']=float('nan')
        self.assertEqual(self.audit(c,p,odds).reason,'INVALID_CLAIMED_ODDS_DIGEST_INPUT')

    def test_ticket_digest_sensitive_to_one_odds_change(self):
        c,p,odds=fixture()
        a=self.audit(c,p,odds)
        odds['1-2-3']+=0.1
        b=self.audit(c,p,odds)
        self.assertNotEqual(a.parsed_tickets_sha256,b.parsed_tickets_sha256)


if __name__=='__main__': unittest.main()
