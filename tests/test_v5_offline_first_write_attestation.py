"""Only synthetic offline fixtures. Do not contact official or DB services."""
import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_first_write_attestation import (
    MockDecisionClock, MockPostcommitAudit, MockReadback, MockReceipt,
    MockRoleReview, verify_offline_first_write_attestation,
)

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 11, 11, 40, tzinfo=JST)
DATA = b"synthetic-only"  # no racer registration or official source bytes
DIGEST = hashlib.sha256(DATA).hexdigest()


def fixtures():
    receipt = MockReceipt("official_beforeinfo:20261011_03_02", "20261011_03_02",
                          DATA, DIGEST, T, T + timedelta(seconds=1))
    row = MockReadback(receipt.resource_key, receipt.race_id, DATA, DIGEST,
                       receipt.request_started_at, receipt.response_completed_at,
                       T + timedelta(seconds=3), T + timedelta(seconds=3))
    roles = MockRoleReview("writer", "owner", "auditor", "reviewer",
                           frozenset({"INSERT", "SELECT"}),
                           frozenset({"resource_key", "raw_bytes", "raw_sha256"}),
                           frozenset({"SELECT"}), False, False, False,
                           T + timedelta(seconds=2))
    audit = MockPostcommitAudit("auditor", "tx-write", "tx-audit",
                                receipt.resource_key, DIGEST, row.stored_at,
                                T + timedelta(seconds=4), T + timedelta(seconds=5),
                                "independent-fake-evidence-store")
    clock = MockDecisionClock(T + timedelta(minutes=20),
                              T + timedelta(minutes=15), "synthetic-deadline")
    return dict(receipt=receipt, row=row, roles=roles, audit=audit, clock=clock)


class OfflineProvenanceTests(unittest.TestCase):
    def verify(self, expected, **changed):
        args = fixtures()
        args.update(changed)
        result = verify_offline_first_write_attestation(**args)
        self.assertEqual(result.reason_code, expected)
        self.assertIs(result.first_observed_at, None)
        self.assertIs(result.first_write_confirmed, False)
        self.assertIs(result.six_active_starts_confirmed, False)
        self.assertIs(result.beforeinfo_first_write_eligible, False)
        self.assertIs(result.forward_eligible, False)
        self.assertIs(result.buy_eligible, False)
        self.assertIs(result.source_independently_authenticated, False)
        self.assertIs(result.audit_independently_authenticated, False)
        return result

    def test_synthetic_consistency_never_authorizes(self):
        r = self.verify("MOCK_SHAPE_CONSISTENT_NOT_AUTHENTICATED")
        self.assertTrue(r.synthetic_shape_consistent)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.forward_eligible = True

    def test_missing_or_malformed_stored_at(self):
        for stored in (None, "2026-10-11T11:40:03+09:00", T.replace(tzinfo=None)):
            with self.subTest(stored=stored):
                a = fixtures()
                self.verify("STORED_AT_NOT_READ_BACK", row=dataclasses.replace(a["row"], stored_at=stored))

    def test_tampered_original_row_and_digest(self):
        a = fixtures()
        for row in (dataclasses.replace(a["row"], raw_bytes=b"changed"),
                    dataclasses.replace(a["row"], raw_sha256="0"*64)):
            with self.subTest(row=row):
                self.verify("ROW_MUTATED_OR_COLLIDED", row=row)

    def test_untrusted_or_missing_receipt(self):
        self.verify("SOURCE_RECEIPT_UNAUTHENTICATED", receipt={"raw_sha256": DIGEST})
        a = fixtures()
        self.verify("ROW_MUTATED_OR_COLLIDED", receipt=dataclasses.replace(a["receipt"], raw_sha256="f"*64))

    def test_writer_privileges_cannot_escalate(self):
        a = fixtures()
        for privilege in ("UPDATE", "DELETE", "TRUNCATE", "ALTER", "DROP"):
            with self.subTest(privilege=privilege):
                self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=dataclasses.replace(
                    a["roles"], writer_effective_privileges=frozenset({"INSERT", "SELECT", privilege})))

    def test_owner_inheritance_privileged_bypass_audit_store(self):
        a = fixtures()
        for key in ("writer_inherits_owner_or_admin", "writer_has_privileged_bypass",
                    "writer_can_change_audit_store"):
            with self.subTest(key=key):
                self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=dataclasses.replace(a["roles"], **{key: True}))

    def test_writer_cannot_provide_stored_at(self):
        a = fixtures()
        self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=dataclasses.replace(
            a["roles"], writer_insert_columns=frozenset({"raw_bytes", "stored_at"})))

    def test_read_only_independent_auditor_and_reviewer(self):
        a = fixtures()
        self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=dataclasses.replace(a["roles"], auditor_role="writer"))
        self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=dataclasses.replace(a["roles"], auditor_effective_privileges=frozenset({"SELECT", "UPDATE"})))
        self.verify("POSTCOMMIT_AUDITOR_MISSING", audit=dataclasses.replace(a["audit"], auditor_transaction_ref="tx-write"))

    def test_postcommit_digest_and_timestamp_mismatch(self):
        a = fixtures()
        self.verify("POSTCOMMIT_AUDITOR_MISSING", audit=dataclasses.replace(a["audit"], raw_sha256="a"*64))
        self.verify("POSTCOMMIT_AUDITOR_MISSING", audit=dataclasses.replace(a["audit"], observed_stored_at=T))

    def test_late_response_stops(self):
        a = fixtures()
        self.verify("CAPTURE_AFTER_CUTOFF", clock=dataclasses.replace(a["clock"], decision_cutoff_at=T))

    def test_late_commit_or_audit_stops(self):
        a = fixtures()
        self.verify("COMMIT_OR_AUDIT_AFTER_CUTOFF", clock=dataclasses.replace(a["clock"], decision_cutoff_at=T + timedelta(seconds=4)))

    def test_unzoned_clock_and_wrong_race_day(self):
        a = fixtures()
        self.verify("CLOCK_OR_DEADLINE_UNVERIFIED", clock=dataclasses.replace(a["clock"], official_deadline_at=T.replace(tzinfo=None)))
        self.verify("CLOCK_OR_DEADLINE_UNVERIFIED", clock=dataclasses.replace(a["clock"], official_deadline_at=T + timedelta(days=1)))

    def test_transaction_start_time_is_not_commit(self):
        a = fixtures()
        self.verify("CLOCK_OR_DEADLINE_UNVERIFIED", row=dataclasses.replace(a["row"], db_transaction_started_at=T))
        self.verify("COMMIT_OR_AUDIT_AFTER_CUTOFF", clock=dataclasses.replace(a["clock"], decision_cutoff_at=T + timedelta(seconds=3)))

    def test_missing_attestation_parts(self):
        self.verify("DB_ROLE_POLICY_UNVERIFIED", roles=None)
        self.verify("POSTCOMMIT_AUDITOR_MISSING", audit=None)
        self.verify("CLOCK_OR_DEADLINE_UNVERIFIED", clock=None)


if __name__ == "__main__":
    unittest.main()
