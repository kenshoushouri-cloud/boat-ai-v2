# -*- coding: utf-8 -*-
"""V5-only pure mock attestation shape review; never a trust or Forward gate.

No DB, SQL, network, filesystem, source-schema approval or Production I/O.
Even a consistent synthetic attestation cannot prove original first observation,
official six-active status or predeadline eligibility.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
RACE = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")


@dataclass(frozen=True, slots=True)
class MockReceipt:
    resource_key: str
    race_id: str
    raw_bytes: bytes
    raw_sha256: str
    request_started_at: datetime
    response_completed_at: datetime


@dataclass(frozen=True, slots=True)
class MockReadback:
    resource_key: str
    race_id: str
    raw_bytes: bytes
    raw_sha256: str
    request_started_at: datetime
    response_completed_at: datetime
    stored_at: datetime | None
    db_transaction_started_at: datetime


@dataclass(frozen=True, slots=True)
class MockRoleReview:
    writer_role: str
    owner_role: str
    auditor_role: str
    reviewer_role: str
    writer_effective_privileges: frozenset[str]
    writer_insert_columns: frozenset[str]
    auditor_effective_privileges: frozenset[str]
    writer_inherits_owner_or_admin: bool
    writer_has_privileged_bypass: bool
    writer_can_change_audit_store: bool
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class MockPostcommitAudit:
    auditor_role: str
    writer_transaction_ref: str
    auditor_transaction_ref: str
    resource_key: str
    raw_sha256: str
    observed_stored_at: datetime
    commit_acknowledged_at: datetime
    audit_observed_at: datetime
    evidence_store_ref: str


@dataclass(frozen=True, slots=True)
class MockDecisionClock:
    official_deadline_at: datetime
    decision_cutoff_at: datetime
    deadline_source_ref: str


@dataclass(frozen=True, slots=True)
class OfflineAttestationVerdict:
    reason_code: str
    synthetic_shape_consistent: bool = False
    # These flags remain denied even for structurally consistent fake inputs.
    first_observed_at: None = field(default=None, init=False)
    first_write_confirmed: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)
    source_independently_authenticated: bool = field(default=False, init=False)
    audit_independently_authenticated: bool = field(default=False, init=False)


def _aware(value: Any) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _nonblank(value: Any) -> bool:
    return type(value) is str and 0 < len(value.strip()) <= 256


def verify_offline_first_write_attestation(
    receipt: object, row: object, roles: object, audit: object,
    clock: object,
) -> OfflineAttestationVerdict:
    """Validate only internally consistent, nonauthoritative mock evidence.

    No caller may turn a TRUE mock consistency result into Forward authority.
    PostgreSQL DEFAULT now() is transaction-start time, not commit time.
    External provenance/signatures and real DB grants are OUT OF SCOPE.
    """
    def deny(reason: str) -> OfflineAttestationVerdict:
        return OfflineAttestationVerdict(reason)

    if type(receipt) is not MockReceipt or type(row) is not MockReadback:
        return deny("SOURCE_RECEIPT_UNAUTHENTICATED")
    if not (_nonblank(receipt.resource_key) and type(receipt.race_id) is str
            and RACE.fullmatch(receipt.race_id)
            and type(receipt.raw_bytes) is bytes and receipt.raw_bytes
            and len(receipt.raw_bytes) <= 10_485_760
            and type(receipt.raw_sha256) is str
            and SHA256.fullmatch(receipt.raw_sha256)):
        return deny("SOURCE_RECEIPT_UNAUTHENTICATED")
    try:
        datetime.strptime(receipt.race_id[:8], "%Y%m%d")
    except ValueError:
        return deny("SOURCE_RECEIPT_UNAUTHENTICATED")
    # The first-write storage identity contract is source-kind:race_id.
    # Matching arbitrary forged keys across the receipt/row/audit is not proof.
    if receipt.resource_key not in (
        f"official_racelist:{receipt.race_id}",
        f"official_beforeinfo:{receipt.race_id}",
    ):
        return deny("RESOURCE_KEY_RACE_BINDING_INVALID")
    if not _aware(row.stored_at):
        return deny("STORED_AT_NOT_READ_BACK")
    if (type(row.raw_bytes) is not bytes
            or row.resource_key != receipt.resource_key
            or row.race_id != receipt.race_id
            or row.raw_bytes != receipt.raw_bytes
            or row.raw_sha256 != receipt.raw_sha256
            or hashlib.sha256(receipt.raw_bytes).hexdigest() != receipt.raw_sha256
            or row.request_started_at != receipt.request_started_at
            or row.response_completed_at != receipt.response_completed_at):
        return deny("ROW_MUTATED_OR_COLLIDED")
    if type(roles) is not MockRoleReview:
        return deny("DB_ROLE_POLICY_UNVERIFIED")
    ids = (roles.writer_role, roles.owner_role, roles.auditor_role, roles.reviewer_role)
    if (not all(_nonblank(i) for i in ids) or len(set(ids)) != 4
            or type(roles.writer_effective_privileges) is not frozenset
            or not {"INSERT", "SELECT"}.issubset(roles.writer_effective_privileges)
            or not roles.writer_effective_privileges <= {"INSERT", "SELECT"}
            or type(roles.writer_insert_columns) is not frozenset
            or not roles.writer_insert_columns
            or "stored_at" in roles.writer_insert_columns
            or type(roles.auditor_effective_privileges) is not frozenset
            or roles.auditor_effective_privileges != frozenset({"SELECT"})
            or roles.writer_inherits_owner_or_admin is not False
            or roles.writer_has_privileged_bypass is not False
            or roles.writer_can_change_audit_store is not False
            or not _aware(roles.reviewed_at)):
        return deny("DB_ROLE_POLICY_UNVERIFIED")
    if type(audit) is not MockPostcommitAudit or not (
        audit.auditor_role == roles.auditor_role
        and _nonblank(audit.writer_transaction_ref)
        and _nonblank(audit.auditor_transaction_ref)
        and audit.writer_transaction_ref != audit.auditor_transaction_ref
        and _nonblank(audit.evidence_store_ref)
        and audit.resource_key == receipt.resource_key
        and audit.raw_sha256 == receipt.raw_sha256
        and audit.observed_stored_at == row.stored_at
        and _aware(audit.commit_acknowledged_at)
        and _aware(audit.audit_observed_at)
    ):
        return deny("POSTCOMMIT_AUDITOR_MISSING")
    if type(clock) is not MockDecisionClock or not (
        _aware(clock.official_deadline_at)
        and _aware(clock.decision_cutoff_at)
        and _nonblank(clock.deadline_source_ref)
    ):
        return deny("CLOCK_OR_DEADLINE_UNVERIFIED")
    if not all(_aware(t) for t in (
        receipt.request_started_at, receipt.response_completed_at,
        row.db_transaction_started_at, roles.reviewed_at,
    )):
        return deny("CLOCK_OR_DEADLINE_UNVERIFIED")
    if not (receipt.request_started_at <= receipt.response_completed_at
            <= row.db_transaction_started_at <= row.stored_at
            <= audit.commit_acknowledged_at <= audit.audit_observed_at
            and roles.reviewed_at <= audit.audit_observed_at
            and clock.decision_cutoff_at < clock.official_deadline_at
            and clock.official_deadline_at.astimezone(JST).strftime("%Y%m%d")
            == receipt.race_id[:8]):
        return deny("CLOCK_OR_DEADLINE_UNVERIFIED")
    if not receipt.response_completed_at < clock.decision_cutoff_at:
        return deny("CAPTURE_AFTER_CUTOFF")
    if not audit.audit_observed_at < clock.decision_cutoff_at:
        return deny("COMMIT_OR_AUDIT_AFTER_CUTOFF")
    return OfflineAttestationVerdict("MOCK_SHAPE_CONSISTENT_NOT_AUTHENTICATED", True)
