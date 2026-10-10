"""Offline-only K receipt tests. Fake bytes, timestamps, and HMAC; no GET/DB."""
import dataclasses
import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone
from v5.offline_asof_eligibility import FeatureSnapshot, _witness_payload
from v5.offline_prior_day_k_receipt import OfflineKReceipt, check_offline_prior_day_k_receipt

JST = timezone(timedelta(hours=9))
RACE = '20261010_03_02'
CUTOFF = datetime(2026, 10, 10, 11, 30, tzinfo=JST)
DAY = datetime(2026, 10, 9, 8, 0, tzinfo=JST)
URL = 'https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh'
RAW = b'fictional-k-archive-not-actual-lzh'
KEY = b'fake-auditor-key-material-over-32bytes!'
TRUST = {'auditor': KEY}
PASS = 'SYNTHETIC_K_SHAPE_PASS_NO_AUTHENTICATED_FIRST_OBSERVATION'

def signed(r, race=RACE, cutoff=CUTOFF):
    s = r.feature_snapshot
    sig = hmac.new(KEY, _witness_payload(race, cutoff, s), hashlib.sha256).hexdigest()
    return dataclasses.replace(r, feature_snapshot=dataclasses.replace(s, witness_hmac=sig))

def build():
    s = FeatureSnapshot('prior_day_k', 'immutable_prior_day_k', 'official_k_file:261009',
        hashlib.sha256(RAW).hexdigest(), DAY+timedelta(seconds=5),
        DAY+timedelta(seconds=6), DAY+timedelta(seconds=7), DAY+timedelta(seconds=8),
        'collector', 'auditor', '')
    return signed(OfflineKReceipt(URL, RAW, DAY+timedelta(seconds=1),
                                  DAY+timedelta(seconds=4), s))

def change(r, **kw):
    return dataclasses.replace(r, feature_snapshot=dataclasses.replace(r.feature_snapshot, **kw))

class TestKReceipt(unittest.TestCase):
    def check(self, reason, receipt=None, **overrides):
        args = dict(race_id=RACE, decision_cutoff_at=CUTOFF,
                    receipt=build() if receipt is None else receipt,
                    trusted_mock_audit_keys=TRUST)
        args.update(overrides)
        v = check_offline_prior_day_k_receipt(**args)
        self.assertEqual(v.reason, reason)
        for flag in ('original_first_observation_verified', 'independently_authenticated_source',
                     'independently_authenticated_auditor', 'six_active_starts_confirmed',
                     'selection_eligible', 'beforeinfo_first_write_eligible',
                     'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(v, flag), False)
        return v

    def test_synthetic_pass_still_holds(self):
        v = self.check(PASS)
        self.assertTrue(v.synthetic_k_receipt_shape_consistent)
        with self.assertRaises(dataclasses.FrozenInstanceError): v.buy_eligible = True

    def test_legacy_row_alone_not_proof(self):
        self.check('K_RAW_RECEIPT_REQUIRED_LEGACY_CLOCKS_NOT_PROOF', receipt={},
                   legacy_result_row={'fetched_at': DAY, 'updated_at': DAY})

    def test_legacy_postrace_fields_do_not_upgrade(self):
        self.check(PASS, legacy_result_row={'fetched_at': CUTOFF, 'updated_at': CUTOFF,
                                            'winning_method': 'postrace', 'first_write_confirmed': True})

    def test_same_day_k_rejected(self):
        self.check('K_NOT_FROM_PRIOR_RACE_DAY', receipt=dataclasses.replace(build(),
                   source_url=URL.replace('k261009', 'k261010')))

    def test_future_k_rejected(self):
        self.check('K_NOT_FROM_PRIOR_RACE_DAY', receipt=dataclasses.replace(build(),
                   source_url=URL.replace('k261009', 'k261011')))

    def test_wrong_url_host_query_scheme_path(self):
        for url in (URL.replace('www1.mbrace.or.jp', 'invalid.example'),
                    URL+'?a=1', URL.replace('https:', 'http:'), URL.replace('/K/', '/B/')):
            with self.subTest(url=url):
                self.check('K_SOURCE_URL_UNVERIFIED', receipt=dataclasses.replace(build(), source_url=url))

    def test_archive_folder_date_mismatch(self):
        self.check('K_ARCHIVE_CALENDAR_INVALID', receipt=dataclasses.replace(build(),
                   source_url=URL.replace('202610/', '202609/')))

    def test_missing_oversized_or_tampered_raw(self):
        for raw, expected in ((b'', 'K_ORIGINAL_RAW_BYTES_MISSING'),
                               (b'x'*2097153, 'K_ORIGINAL_RAW_BYTES_MISSING'),
                               (b'mutated', 'K_ORIGINAL_LINEAGE_OR_DIGEST_INVALID')):
            with self.subTest(size=len(raw)):
                self.check(expected, receipt=dataclasses.replace(build(), original_raw_bytes=raw))

    def test_mismatched_original_key(self):
        self.check('K_ORIGINAL_LINEAGE_OR_DIGEST_INVALID', receipt=change(build(), original_ref='official_k_file:261008'))

    def test_mutable_and_postrace_sources(self):
        for values, expected in (({'source_mode':'upsert'}, 'K_FEATURE_SOURCE_KIND_MISMATCH'),
                                ({'mutable_or_upsert_only':True}, 'K_MUTABLE_OR_POSTRACE_FEATURE'),
                                ({'postrace_derived':True}, 'K_MUTABLE_OR_POSTRACE_FEATURE')):
            self.check(expected, receipt=signed(change(build(), **values)))

    def test_naive_clock(self):
        r=build()
        self.check('K_UNVERIFIED_CLOCK', receipt=dataclasses.replace(r,
                   response_completed_at=r.response_completed_at.replace(tzinfo=None)))

    def test_invalid_response_observation_order(self):
        r=build()
        self.check('K_INVALID_CAPTURE_FREEZE_ORDER', receipt=dataclasses.replace(r,
                   response_completed_at=r.feature_snapshot.source_observed_at+timedelta(seconds=1)))

    def test_cutoff_equal_audit_rejected(self):
        self.check('K_NOT_FROZEN_BEFORE_DECISION_CUTOFF', receipt=signed(change(build(), audited_at=CUTOFF)))

    def test_observation_before_archive_date_rejected(self):
        prior = DAY-timedelta(days=1)
        r = change(build(), source_observed_at=prior+timedelta(seconds=5),
                   original_frozen_at=prior+timedelta(seconds=6),
                   feature_observed_at=prior+timedelta(seconds=7), audited_at=prior+timedelta(seconds=8))
        r = dataclasses.replace(r, request_started_at=prior, response_completed_at=prior+timedelta(seconds=1))
        self.check('K_CLAIMED_BEFORE_ARCHIVE_DAY', receipt=signed(r))

    def test_untrusted_witness_and_missing_anchor(self):
        self.check('K_MOCK_WITNESS_INVALID', receipt=change(build(), witness_hmac='0'*64))
        self.check('K_MOCK_AUDITOR_ANCHOR_MISSING', trusted_mock_audit_keys={})

    def test_same_collector_and_auditor_rejected(self):
        self.check('K_INDEPENDENT_MOCK_AUDITOR_MISSING', receipt=change(build(), auditor_id='collector'))

    def test_invalid_race_or_naive_cutoff(self):
        self.check('K_RACE_OR_CUTOFF_INVALID', race_id='20261009_03_02')
        self.check('K_RACE_OR_CUTOFF_INVALID', decision_cutoff_at=CUTOFF.replace(tzinfo=None))

if __name__ == '__main__': unittest.main()
