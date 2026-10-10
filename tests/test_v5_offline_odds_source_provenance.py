"""Test fake source/first-write odds shapes; no API/SQL/official downloads."""
from __future__ import annotations

import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_odds_source_provenance import (
    LegacyOddsSnapshot, MockImmutableOddsReceipt, classify_offline_odds_source,
)

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 10, 10, 0, tzinfo=JST)
SRC = b'fictional official-like HTML, not actual publisher data'
HASH = hashlib.sha256(SRC).hexdigest()
RID = '20261010_03_04'
URL = 'https://www.boatrace.jp/owpc/pc/race/odds3t?rno=4&jcd=03&hd=20261010'


def fixture(rid=RID, clock=T):
    row = LegacyOddsSnapshot(rid, '1-2-3', 12.4, 'PRE', clock + timedelta(minutes=5),
                             'OFFICIAL_HTTP_DIRECT', {'race_id':rid, 'ticket':'1-2-3',
                                                      'odds':12.4, 'original_sha256': HASH},
                             'IMMUTABLE_FIRST_WRITE')
    proof = MockImmutableOddsReceipt(rid, '1-2-3', clock + timedelta(hours=1), URL,
                                      SRC, HASH, clock, clock + timedelta(minutes=2),
                                      clock + timedelta(minutes=6),
                                      clock + timedelta(minutes=8), HASH,
                                      'unverifiable-fictional-owner-reference')
    return row, proof


class OddsSourceClassifierTests(unittest.TestCase):
    def check(self, row=None, proof=None, expected='MOCK_ORIGINAL_ODDS_SHAPE_ONLY_HARD_HOLD'):
        x, y = fixture()
        v = classify_offline_odds_source(x if row is None else row,
                                          receipt=y if proof is None else proof)
        self.assertEqual(v.reason, expected)
        for flag in ('parsed_odds_bound_to_original_bytes', 'official_publisher_verified',
                     'immutable_first_observation_verified','independently_authenticated_source',
                     'real_predeadline_odds_eligible','selection_eligible','forward_eligible',
                     'buy_eligible'):
            self.assertFalse(getattr(v, flag))
        self.assertIs(v.mock_original_receipt_shape_consistent,
                      expected == 'MOCK_ORIGINAL_ODDS_SHAPE_ONLY_HARD_HOLD')
        return v

    def test_fictional_receipts_only_confirm_shape_not_trust(self):
        v = self.check()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            v.buy_eligible = True

    def test_legacy_mutable_upsert_fail_closed_even_with_receipt(self):
        x,y=fixture()
        self.check(dataclasses.replace(x,write_mode='UPSERT'),y,
                   'MUTABLE_UPSERT_NOT_ORIGINAL_FIRST_WRITE')

    def test_legacy_raw_empty_fail_closed_even_with_receipt(self):
        x,y=fixture()
        self.check(dataclasses.replace(x,raw={}),y,'EMPTY_OR_UNBOUND_SNAPSHOT_RAW')

    def test_fallback_source_denied_even_if_complete_odds_set(self):
        x,y=fixture()
        for source in ('legacy_base', 'BASE_FALLBACK', 'official_beforeinfo', None):
            with self.subTest(source=source):
                self.check(dataclasses.replace(x,source=source),y,
                           'FALLBACK_OR_UNVERIFIED_ODDS_SOURCE')

    def test_missing_receipt_and_malformed_sources(self):
        x,y=fixture()
        self.check(x, {},'MISSING_INDEPENDENT_ORIGINAL_RECEIPT')
        self.check(x, dataclasses.replace(y,official_url='https://evil.example/owpc/pc/race/odds3t'),
                   'RECEIPT_SOURCE_OR_IDENTITY_MISMATCH')
        self.check(x, dataclasses.replace(y,official_url='https://www.boatrace.jp.evil.com/owpc/pc/race/odds3t'),
                   'RECEIPT_SOURCE_OR_IDENTITY_MISMATCH')

    def test_original_hash_missing_or_tampered(self):
        x,y=fixture()
        self.check(x,dataclasses.replace(y,original_sha256='0'*64),
                   'ORIGINAL_RAW_OR_READBACK_SHA_MISMATCH')
        self.check(x,dataclasses.replace(y,readback_sha256='0'*64),
                   'ORIGINAL_RAW_OR_READBACK_SHA_MISMATCH')
        self.check(dataclasses.replace(x,raw={**x.raw,'original_sha256':'0'*64}),y,
                   'ORIGINAL_RAW_OR_READBACK_SHA_MISMATCH')

    def test_race_or_ticket_invalid(self):
        x,y=fixture()
        for bad in ('20260230_03_04','20250630_03_04','20261010_99_04',''):
            self.check(dataclasses.replace(x,race_id=bad),y,'RACE_OR_TICKET_INVALID')
        self.check(dataclasses.replace(x,ticket='1-1-3'),y,'RACE_OR_TICKET_INVALID')

    def test_bad_odds_and_naive_snapshot_timestamp(self):
        x,y=fixture()
        for bad in (0,float('nan'),float('inf'),True):
            self.check(dataclasses.replace(x,odds=bad),y,'ODDS_OR_SNAPSHOT_CLOCK_INVALID')
        self.check(dataclasses.replace(x,snapshot_at=x.snapshot_at.replace(tzinfo=None)),y,
                   'ODDS_OR_SNAPSHOT_CLOCK_INVALID')

    def test_early_publication_or_late_readback_claim_fails(self):
        x,y=fixture()
        self.check(x,dataclasses.replace(y,published_at=y.first_observed_at+timedelta(seconds=1)),
                   'UNVERIFIED_FIRST_SEEN_PUBLICATION_OR_CUTOFF_ORDER')
        self.check(x,dataclasses.replace(y,readback_at=y.cutoff_at),
                   'UNVERIFIED_FIRST_SEEN_PUBLICATION_OR_CUTOFF_ORDER')
        self.check(x,dataclasses.replace(y,first_observed_at=x.snapshot_at+timedelta(seconds=1)),
                   'UNVERIFIED_FIRST_SEEN_PUBLICATION_OR_CUTOFF_ORDER')

    def test_missing_owner_receipt_holds(self):
        x,y=fixture()
        self.check(x,dataclasses.replace(y,independent_owner_receipt_ref=''),
                   'INDEPENDENT_OWNER_RECEIPT_MISSING')

    def test_raw_odds_or_race_not_bound_denied(self):
        x,y=fixture()
        self.check(dataclasses.replace(x,raw={**x.raw,'odds':99}),y,
                   'SNAPSHOT_RAW_VALUE_MISMATCH')
        self.check(x,dataclasses.replace(y,race_id='20261010_03_05'),
                   'RECEIPT_SOURCE_OR_IDENTITY_MISMATCH')

    def test_historic_2025_label_does_not_prove_first_seen(self):
        rid='20250701_03_04'
        clock=datetime(2025,7,1,10,tzinfo=JST)
        x,y=fixture(rid,clock)
        self.check(x,y)
        self.check(dataclasses.replace(x,write_mode='UPSERT'),y,
                   'MUTABLE_UPSERT_NOT_ORIGINAL_FIRST_WRITE')

if __name__ == '__main__':
    unittest.main()
