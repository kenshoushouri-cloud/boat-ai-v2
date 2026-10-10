"""Narrow offline mock tests for the V5 first-row stored_at readback contract."""
import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_first_row_readback import (
    DbFirstRowFixture, OriginalFixture, review_offline_first_row_readback,
)

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 11, 11, 10, tzinfo=JST)
RAW = b"fake-no-real-racer-data"
SHA = hashlib.sha256(RAW).hexdigest()


def samples():
    orig = OriginalFixture(
        "official_beforeinfo:20261011_03_02", "official_beforeinfo",
        "20261011_03_02",
        "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=2&jcd=03&hd=20261011",
        T, T + timedelta(seconds=1), RAW, SHA,
    )
    row = DbFirstRowFixture(
        orig.resource_key, orig.source_kind, orig.race_id, orig.source_url,
        orig.request_started_at, orig.response_completed_at,
        orig.raw_bytes, orig.raw_sha256,
        T + timedelta(seconds=3), T + timedelta(seconds=3),
        T + timedelta(seconds=5),
    )
    return orig, row


class OfflineFirstRowReadbackTests(unittest.TestCase):
    def check(self, reason, orig=None, row=None):
        base_orig, base_row = samples()
        verdict = review_offline_first_row_readback(
            base_orig if orig is None else orig,
            base_row if row is None else row,
        )
        self.assertEqual(verdict.reason_code, reason)
        self.assertIsNone(verdict.first_observed_at)
        for key in ("first_write_confirmed", "six_active_starts_confirmed",
                    "beforeinfo_first_write_eligible", "forward_eligible",
                    "buy_eligible", "db_commit_authenticated",
                    "db_role_immutability_verified"):
            self.assertFalse(getattr(verdict, key))
        return verdict

    def test_matching_mock_never_authorizes(self):
        result = self.check("MOCK_ROW_MATCH_NO_INDEPENDENT_PROVENANCE")
        self.assertTrue(result.synthetic_shape_consistent)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.forward_eligible = True

    def test_no_row(self):
        self.assertEqual(review_offline_first_row_readback(samples()[0], None).reason_code,
                         "ORIGINAL_OR_ROW_MISSING")

    def test_missing_stored_at(self):
        orig, row = samples()
        self.check("STORED_AT_NOT_READ_BACK", row=dataclasses.replace(row, stored_at=None))

    def test_invalid_stored_at(self):
        orig, row = samples()
        for value in ("2026-10-11T11:10:03+09:00", T.replace(tzinfo=None), True):
            with self.subTest(value=value):
                self.check("STORED_AT_INVALID", row=dataclasses.replace(row, stored_at=value))

    def test_now_transaction_start_not_commit(self):
        orig, row = samples()
        self.check("PG_NOW_TRANSACTION_START_MISMATCH", row=dataclasses.replace(
            row, stored_at=row.db_transaction_started_at+timedelta(seconds=1)))

    def test_transaction_start_earlier_than_capture(self):
        orig, row = samples()
        previous = T - timedelta(seconds=2)
        self.check("TX_STARTED_BEFORE_RESPONSE_COMPLETE", row=dataclasses.replace(
            row, stored_at=previous, db_transaction_started_at=previous))

    def test_mutated_body_or_sha(self):
        orig, row = samples()
        for modified in (dataclasses.replace(row, raw_bytes=b"bad"),
                         dataclasses.replace(row, raw_sha256="0"*64)):
            with self.subTest(modified=modified):
                self.check("FIRST_ROW_MISMATCH_OR_MUTATION", row=modified)

    def test_modified_original_digest(self):
        orig, row = samples()
        self.check("ORIGINAL_BYTES_OR_SHA_INVALID", orig=dataclasses.replace(
            orig, raw_sha256="0"*64))

    def test_forged_canonical_key(self):
        orig, row = samples()
        altered = "official_beforeinfo:20261012_03_02"
        self.check("CANONICAL_RESOURCE_IDENTITY_INVALID",
                   orig=dataclasses.replace(orig, resource_key=altered),
                   row=dataclasses.replace(row, resource_key=altered))

    def test_bad_race_calendar_date(self):
        orig, row = samples()
        self.check("CANONICAL_RESOURCE_IDENTITY_INVALID",
                   orig=dataclasses.replace(orig, race_id="20260230_03_02"))

    def test_url_exact_matching(self):
        orig, row = samples()
        for url in (orig.source_url.replace("www.boatrace.jp", "evil.example"),
                    orig.source_url + "&extra=1", orig.source_url.replace("rno=2", "rno=1")):
            with self.subTest(url=url):
                self.check("CANONICAL_RESOURCE_IDENTITY_INVALID",
                           orig=dataclasses.replace(orig, source_url=url),
                           row=dataclasses.replace(row, source_url=url))

    def test_mismatched_row_identity(self):
        orig, row = samples()
        self.check("FIRST_ROW_MISMATCH_OR_MUTATION",
                   row=dataclasses.replace(row, resource_key="official_beforeinfo:20261011_03_03"))

    def test_reject_unzoned_times(self):
        orig, row = samples()
        self.check("CLOCK_PROVENANCE_INVALID", orig=dataclasses.replace(
            orig, response_completed_at=orig.response_completed_at.replace(tzinfo=None)),
            row=dataclasses.replace(row, response_completed_at=row.response_completed_at.replace(tzinfo=None)))

    def test_invalid_claimed_readback_chronology(self):
        orig, row = samples()
        self.check("CLOCK_ORDER_INVALID", row=dataclasses.replace(
            row, claimed_postcommit_read_at=T))

    def test_no_body_or_oversize(self):
        orig, row = samples()
        for body in (b"", b"x" * (2*1024*1024 + 1)):
            with self.subTest(length=len(body)):
                self.check("ORIGINAL_BYTES_OR_SHA_INVALID", orig=dataclasses.replace(
                    orig, raw_bytes=body, raw_sha256=hashlib.sha256(body).hexdigest()))


if __name__ == "__main__":
    unittest.main()
