# -*- coding: utf-8 -*-
"""Pure formal-artifact arbitration contract for Candidate Discovery V4.

This module does not run a capture, access GitHub/Railway, read a database,
write files, send LINE, or authorize purchase/promotion.  It only classifies
already-produced capture metadata that has been supplied by the caller.

The contract intentionally ignores provider-local run IDs when deciding the
formal artifact.  Evidence precedence is based only on validated prospective
eligibility, target date, generation timestamp and canonical payload SHA-256.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Mapping, Any

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
CORE_RACES = 6
CORE_TICKETS = 12


@dataclass(frozen=True)
class Capture:
    channel: str
    provider_run_id: str
    target_date: date
    generated_at_jst: datetime
    canonical_payload_sha256: str
    prospective_evidence_eligible: bool
    purchase_action: bool
    promotion_allowed: bool
    core_races: int
    core_tickets: int
    all_frozen_rows_pre_deadline: bool


@dataclass(frozen=True)
class ArbitrationResult:
    classification: str
    formal_capture: Capture | None
    duplicate_copies: tuple[Capture, ...]
    later_diagnostics: tuple[Capture, ...]
    rejected_captures: tuple[Capture, ...]

    @property
    def formal_available(self) -> bool:
        return self.classification == "FORMAL_AVAILABLE"


def _aware_jst(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at_jst must be timezone-aware")
    return value.astimezone(JST)


def _valid_sha256(value: str) -> bool:
    text = (value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def capture_from_mapping(row: Mapping[str, Any]) -> Capture:
    raw_date = row.get("target_date")
    target = raw_date if isinstance(raw_date, date) and not isinstance(raw_date, datetime) else date.fromisoformat(str(raw_date))
    generated = row.get("generated_at_jst")
    if not isinstance(generated, datetime):
        generated = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
    return Capture(
        channel=str(row.get("channel") or ""),
        provider_run_id=str(row.get("provider_run_id") or ""),
        target_date=target,
        generated_at_jst=generated,
        canonical_payload_sha256=str(row.get("canonical_payload_sha256") or "").lower(),
        prospective_evidence_eligible=bool(row.get("prospective_evidence_eligible")),
        purchase_action=bool(row.get("purchase_action")),
        promotion_allowed=bool(row.get("promotion_allowed")),
        core_races=int(row.get("core_races") or 0),
        core_tickets=int(row.get("core_tickets") or 0),
        all_frozen_rows_pre_deadline=bool(row.get("all_frozen_rows_pre_deadline")),
    )


def is_formally_valid(capture: Capture, *, target_date: date) -> bool:
    try:
        generated = _aware_jst(capture.generated_at_jst)
    except ValueError:
        return False
    cutoff = datetime.combine(target_date, SOURCE_CUTOFF, tzinfo=JST)
    return (
        capture.target_date == target_date
        and generated.date() == target_date
        and generated >= cutoff
        and _valid_sha256(capture.canonical_payload_sha256)
        and capture.prospective_evidence_eligible is True
        and capture.purchase_action is False
        and capture.promotion_allowed is False
        and capture.core_races == CORE_RACES
        and capture.core_tickets == CORE_TICKETS
        and capture.all_frozen_rows_pre_deadline is True
    )


def arbitrate_captures(
    captures: Iterable[Capture | Mapping[str, Any]],
    *,
    target_date: date,
) -> ArbitrationResult:
    """Choose the formal V4 artifact from already-produced capture metadata.

    Rules frozen before the 2026-09-16 primary:
    - invalid/ineligible captures are rejected, never rescued;
    - no valid capture => unavailable;
    - unique earliest valid generated_at_jst => formal artifact;
    - same earliest timestamp + same canonical payload SHA => duplicate copies;
    - same earliest timestamp + different SHA => fail closed as ambiguous;
    - later valid captures are diagnostic only;
    - provider/channel/run ID never breaks a tie.
    """
    normalized = [
        item if isinstance(item, Capture) else capture_from_mapping(item)
        for item in captures
    ]
    valid: list[Capture] = []
    rejected: list[Capture] = []
    for capture in normalized:
        (valid if is_formally_valid(capture, target_date=target_date) else rejected).append(capture)

    if not valid:
        return ArbitrationResult(
            classification="UNAVAILABLE_NO_VALID_CAPTURE",
            formal_capture=None,
            duplicate_copies=(),
            later_diagnostics=(),
            rejected_captures=tuple(rejected),
        )

    keyed = sorted(valid, key=lambda c: _aware_jst(c.generated_at_jst))
    earliest_time = _aware_jst(keyed[0].generated_at_jst)
    earliest = [c for c in keyed if _aware_jst(c.generated_at_jst) == earliest_time]
    later = [c for c in keyed if _aware_jst(c.generated_at_jst) > earliest_time]
    earliest_hashes = {c.canonical_payload_sha256 for c in earliest}

    if len(earliest_hashes) != 1:
        return ArbitrationResult(
            classification="UNAVAILABLE_AMBIGUOUS_DUPLICATE_CAPTURE",
            formal_capture=None,
            duplicate_copies=tuple(earliest),
            later_diagnostics=tuple(later),
            rejected_captures=tuple(rejected),
        )

    # All same-time earliest copies carry the same canonical payload.  Pick a
    # deterministic metadata representative without implying evidence priority.
    representative = sorted(
        earliest,
        key=lambda c: (c.channel, c.provider_run_id),
    )[0]
    duplicates = tuple(c for c in earliest if c is not representative)
    return ArbitrationResult(
        classification="FORMAL_AVAILABLE",
        formal_capture=representative,
        duplicate_copies=duplicates,
        later_diagnostics=tuple(later),
        rejected_captures=tuple(rejected),
    )
