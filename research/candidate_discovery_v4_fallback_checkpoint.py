# -*- coding: utf-8 -*-
"""Pure/offline decision contract for the Candidate Discovery V4 fallback checkpoint.

This module decides only whether an independently scheduled fallback *may attempt*
a capture at/after the preregistered 08:25 JST checkpoint. It does not access
GitHub, Railway, PostgreSQL, files, LINE, results, payouts, or purchase systems.

An ATTEMPT_FALLBACK decision is not evidence eligibility. The existing guarded
prospective-freeze wrapper remains the final authority for same-date source cutoff,
complete 6-race/12-ticket core, and completion before the earliest frozen-feed
deadline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Mapping, Any

from research.candidate_discovery_v4_capture_arbiter import (
    Capture,
    JST,
    arbitrate_captures,
    capture_from_mapping,
    is_formally_valid,
)

FALLBACK_CHECKPOINT_JST = time(8, 25)
PRIMARY_CHANNEL = "github-primary"


@dataclass(frozen=True)
class FallbackCheckpointDecision:
    action: str
    reason: str
    valid_primary: Capture | None
    rejected_primary_count: int

    @property
    def should_attempt(self) -> bool:
        return self.action == "ATTEMPT_FALLBACK"


def _observed_jst(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("observed_at_jst must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at_jst must be timezone-aware")
    return value.astimezone(JST)


def decide_fallback_checkpoint(
    primary_captures: Iterable[Capture | Mapping[str, Any]],
    *,
    target_date: date,
    observed_at_jst: datetime,
) -> FallbackCheckpointDecision:
    """Classify the preregistered 08:25 JST fallback checkpoint.

    Rules:
    - never act for a different JST calendar date;
    - before 08:25 JST, the fallback is not due;
    - only same-channel primary captures observable by ``observed_at_jst`` count;
    - one formally valid primary, or duplicate copies of the same formal primary,
      means fallback NOOP;
    - ambiguous same-earliest primary payloads fail closed and are not rescued by
      fallback;
    - absent/invalid primary evidence means the fallback may ATTEMPT only. The
      prospective wrapper still decides whether that attempted capture is valid.
    - non-primary channel metadata never suppresses the primary-missing fallback.
    """
    observed = _observed_jst(observed_at_jst)
    if observed.date() != target_date:
        return FallbackCheckpointDecision(
            action="FAIL_CLOSED_WRONG_DATE",
            reason="observed JST date does not equal target date",
            valid_primary=None,
            rejected_primary_count=0,
        )

    checkpoint = datetime.combine(target_date, FALLBACK_CHECKPOINT_JST, tzinfo=JST)
    if observed < checkpoint:
        return FallbackCheckpointDecision(
            action="NOT_DUE",
            reason="fallback checkpoint is 08:25 JST and has not been reached",
            valid_primary=None,
            rejected_primary_count=0,
        )

    normalized: list[Capture] = []
    rejected_count = 0
    for item in primary_captures:
        capture = item if isinstance(item, Capture) else capture_from_mapping(item)
        if capture.channel != PRIMARY_CHANNEL:
            continue
        generated = capture.generated_at_jst.astimezone(JST)
        if generated > observed:
            # Metadata from the future was not independently observable at this
            # checkpoint and must not suppress the fallback.
            rejected_count += 1
            continue
        if not is_formally_valid(capture, target_date=target_date):
            rejected_count += 1
            continue
        normalized.append(capture)

    if not normalized:
        return FallbackCheckpointDecision(
            action="ATTEMPT_FALLBACK",
            reason="no valid same-date primary capture observable at checkpoint",
            valid_primary=None,
            rejected_primary_count=rejected_count,
        )

    arbitration = arbitrate_captures(normalized, target_date=target_date)
    if arbitration.classification == "UNAVAILABLE_AMBIGUOUS_DUPLICATE_CAPTURE":
        return FallbackCheckpointDecision(
            action="FAIL_CLOSED_AMBIGUOUS_PRIMARY",
            reason="same-earliest valid primary captures disagree on canonical core hash",
            valid_primary=None,
            rejected_primary_count=rejected_count,
        )
    if not arbitration.formal_available or arbitration.formal_capture is None:
        # Defensive fail-closed branch: normalized contains only formally valid
        # captures, so an unexpected arbitration result must not authorize work.
        return FallbackCheckpointDecision(
            action="FAIL_CLOSED_PRIMARY_ARBITRATION",
            reason=arbitration.classification,
            valid_primary=None,
            rejected_primary_count=rejected_count,
        )

    return FallbackCheckpointDecision(
        action="NOOP_VALID_PRIMARY",
        reason="valid same-date primary capture already observable",
        valid_primary=arbitration.formal_capture,
        rejected_primary_count=rejected_count,
    )
