"""Local synthetic roster gate tests; no external network, DB or real HTML."""
import dataclasses
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_paper_roster_gate import (
    CONTRACT, MockFrozenPage, check_offline_paper_roster,
)

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 10, 10, tzinfo=JST)
RID = '20261010_03_04'


def records(kind):
    return [dict(lane=i, racer_number=1000+i, **(
        {'exhibition_time': 6.51 + i/100, 'withdrawal': False}
        if kind == 'beforeinfo' else {})) for i in range(1, 7)]


def mk(kind, entries=None, *, rid=RID, at=None, raw=None):
    if raw is None:
        raw = json.dumps({'contract': CONTRACT, 'kind': kind, 'race_id': rid,
                          'entries': records(kind) if entries is None else entries},
                         separators=(',', ':'), sort_keys=True).encode()
    url = f'https://www.boatrace.jp/owpc/pc/race/{kind}?rno=4&jcd=03&hd=20261010'
    when = at or (T if kind == 'racelist' else T+timedelta(minutes=1))
    return MockFrozenPage(kind, url, url, raw, hashlib.sha256(raw).hexdigest(),
                          when, T+timedelta(minutes=2))


def case():
    return mk('racelist'), mk('beforeinfo')


class TestPaperRosterGate(unittest.TestCase):
    def audit(self, a=None, b=None, expected='SIX_LISTED_EXHIBITION_OBSERVED_ONLY', **kwargs):
        x, y = case()
        result = check_offline_paper_roster(expected_race_id=kwargs.get('rid', RID),
                    decision_cutoff_at=kwargs.get('cutoff', T+timedelta(minutes=5)),
                    racelist=x if a is None else a,
                    beforeinfo=y if b is None else b,
                    enabled=kwargs.get('enabled', True))
        self.assertEqual(result.reason, expected)
        for attr in ('original_first_observation_verified',
                     'independently_authenticated_source','six_active_starts_confirmed',
                     'beforeinfo_first_write_eligible','selection_eligible',
                     'forward_eligible','buy_eligible'):
            self.assertIs(getattr(result, attr), False)
        self.assertTrue(result.no_get_no_db_no_write)
        self.assertTrue(result.no_economic_odds_evidence)
        if expected != 'SIX_LISTED_EXHIBITION_OBSERVED_ONLY':
            self.assertFalse(result.paper_shadow_shape_eligible)
            self.assertEqual((result.matched_mock_lanes, result.race_id), (0, ''))
        return result

    def test_positive_mock_six_only_still_hard_hold(self):
        r = self.audit()
        self.assertEqual((r.status, r.matched_mock_lanes),
                         ('MOCK_PAPER_SHADOW_SHAPE_ONLY_HARD_HOLD', 6))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.buy_eligible = True

    def test_default_disabled(self):
        a,b = case()
        r = check_offline_paper_roster(expected_race_id=RID,
            decision_cutoff_at=T+timedelta(minutes=5), racelist=a, beforeinfo=b)
        self.assertEqual(r.reason, 'PAPER_SHADOW_OPT_IN_REQUIRED')

    def test_only_explicit_true_enabled(self):
        for opt in (False, 1, 'true', None):
            with self.subTest(opt=opt):
                self.audit(enabled=opt, expected='PAPER_SHADOW_OPT_IN_REQUIRED')

    def test_missing_page(self):
        self.audit(a='missing', expected='MISSING_SOURCE_PAGE')

    def test_race_and_url_mismatch(self):
        a,b = case()
        self.audit(a=dataclasses.replace(a,requested_url=a.requested_url.replace('rno=4','rno=5')),
                   expected='OFFICIAL_URL_SHAPE_OR_RACE_MISMATCH')
        self.audit(a=dataclasses.replace(a,final_url=a.final_url+'#redirect'),
                   expected='OFFICIAL_URL_SHAPE_OR_RACE_MISMATCH')
        self.audit(a=dataclasses.replace(a,requested_url=a.requested_url+'&rno=4',
                                         final_url=a.final_url+'&rno=4'),
                   expected='OFFICIAL_URL_SHAPE_OR_RACE_MISMATCH')
        self.audit(rid='20261010_03_05', expected='OFFICIAL_URL_SHAPE_OR_RACE_MISMATCH')

    def test_invalid_date_and_cutoff(self):
        self.audit(rid='20260230_03_04', expected='RACE_OR_CUTOFF_INVALID')
        self.audit(cutoff=T+timedelta(days=1), expected='RACE_OR_CUTOFF_INVALID')

    def test_missing_extra_duplicate_lanes(self):
        for entries in (records('racelist')[:-1], records('racelist')+[records('racelist')[0]]):
            with self.subTest(len=len(entries)):
                self.audit(a=mk('racelist', entries),expected='RACELIST_MISSING_OR_EXTRA_LANES')
        x = records('beforeinfo'); x[5]['lane']=1
        self.audit(b=mk('beforeinfo', x),expected='BEFOREINFO_DUPLICATE_OR_MISSING_LANE_RACER')

    def test_duplicate_racer_or_missing_field(self):
        x=records('racelist'); x[5]['racer_number']=x[0]['racer_number']
        self.audit(a=mk('racelist',x),expected='RACELIST_DUPLICATE_OR_MISSING_LANE_RACER')
        x=records('beforeinfo'); x[0].pop('racer_number')
        self.audit(b=mk('beforeinfo',x),expected='BEFOREINFO_MALFORMED_LANE_OR_RACER')

    def test_lane_racer_identity_conflict(self):
        x=records('beforeinfo'); x[0]['racer_number']=3333
        self.audit(b=mk('beforeinfo',x),expected='SIX_LANE_RACER_IDENTITY_CONFLICT')

    def test_displayed_withdrawal(self):
        x=records('beforeinfo'); x[2]['withdrawal']=True
        self.audit(b=mk('beforeinfo',x),expected='BEFOREINFO_DISPLAYED_WITHDRAWAL_OR_CANCELLATION')

    def test_invalid_exhibition_and_withdrawal_type(self):
        x=records('beforeinfo'); x[2]['exhibition_time']=None
        self.audit(b=mk('beforeinfo',x),expected='BEFOREINFO_INCOMPLETE_EXHIBITION')
        x=records('beforeinfo'); x[2]['withdrawal']='False'
        self.audit(b=mk('beforeinfo',x),expected='BEFOREINFO_UNVERIFIED_WITHDRAWAL_FIELD')

    def test_late_cutoff_and_reversed_source_order(self):
        self.audit(cutoff=T+timedelta(minutes=2),
                   expected='SOURCE_NOT_FROZEN_BEFORE_DECISION_CUTOFF')
        self.audit(a=mk('racelist', at=T+timedelta(minutes=2)),
                   expected='RACELIST_OBSERVED_AFTER_BEFOREINFO')

    def test_raw_hash_tamper_and_oversize(self):
        a,b=case()
        self.audit(a=dataclasses.replace(a,raw_sha256='0'*64),
                   expected='RAW_BYTES_OR_SHA256_MISMATCH')
        self.audit(a=dataclasses.replace(a,raw_bytes=a.raw_bytes+b'x'),
                   expected='RAW_BYTES_OR_SHA256_MISMATCH')
        self.audit(a=dataclasses.replace(a,raw_bytes=b'x'*65537),
                   expected='RAW_BYTES_OR_SHA256_MISMATCH')

    def test_json_duplicate_keys_and_invalid_utf8(self):
        raw=b'{"contract":"x","contract":"y"}'
        self.audit(a=mk('racelist',raw=raw),expected='RACELIST_SYNTHETIC_ORIGINAL_BYTES_UNPARSEABLE')
        self.audit(a=mk('racelist',raw=b'\xff'),
                   expected='RACELIST_SYNTHETIC_ORIGINAL_BYTES_UNPARSEABLE')

    def test_mutable_postrace_fake_source_claims(self):
        a,b=case()
        for key,value in (('mutable_or_upsert_only',True),('postrace_derived',True),
                          ('first_observed_at',T),('first_write_confirmed',True),
                          ('actual_source_authenticated',True)):
            with self.subTest(key=key):
                self.audit(a=dataclasses.replace(a,**{key:value}),
                           expected='FORGED_AUTHORITY_OR_MUTABLE_HISTORY')

    def test_clock_after_cutoff_or_wrong_day(self):
        a,b=case()
        self.audit(b=dataclasses.replace(b,response_completed_at=T+timedelta(minutes=6)),
                   expected='SOURCE_NOT_FROZEN_BEFORE_DECISION_CUTOFF')
        self.audit(a=dataclasses.replace(a,response_completed_at=T-timedelta(days=1)),
                   expected='SOURCE_NOT_FROZEN_BEFORE_DECISION_CUTOFF')

    def test_body_race_id_mismatch(self):
        a,b=case()
        self.audit(a=mk('racelist',rid='20261010_03_05'),
                   expected='RACELIST_MOCK_SOURCE_CONTRACT_OR_RACE_MISMATCH')


if __name__=='__main__':
    unittest.main()
