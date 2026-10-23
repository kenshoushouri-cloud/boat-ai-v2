# -*- coding: utf-8 -*-
"""Pure research prototype for Opponent Pressure Forward timing eligibility.

This module performs no I/O and is not imported by Production. It exists to
make the proposed pre-production contract executable before any operations or
Production change is considered.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

JST = timezone(timedelta(hours=9))
FIXED_CUTOFF = time(8, 15)


@dataclass(frozen=True)
class OpponentSnapshotEvidence:
    race_date: date
    deadline_at: datetime
    created_at: datetime
    updated_at: datetime
    train_end: date
    model_version: int
    matched_opponents: tuple[int, ...]


def _jst(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("naive datetime is not admissible timing evidence")
    return value.astimezone(JST)


def forward_eligibility(evidence: OpponentSnapshotEvidence | None) -> tuple[bool, str]:
    """Return a fail-closed eligibility decision for a research snapshot."""
    if evidence is None:
        return False, "missing_snapshot"

    try:
        deadline = _jst(evidence.deadline_at)
        created = _jst(evidence.created_at)
        updated = _jst(evidence.updated_at)
    except (TypeError, ValueError):
        return False, "invalid_timestamp"

    if deadline.date() != evidence.race_date:
        return False, "deadline_date_mismatch"
    if created.date() != evidence.race_date or updated.date() != evidence.race_date:
        return False, "snapshot_date_mismatch"
    if evidence.model_version != 2:
        return False, "model_version_mismatch"
    if evidence.train_end != evidence.race_date - timedelta(days=1):
        return False, "train_end_mismatch"
    if len(evidence.matched_opponents) != 6 or any(x < 4 for x in evidence.matched_opponents):
        return False, "opponent_coverage_incomplete"
    if updated < created:
        return False, "updated_before_created"
    if created.time().replace(tzinfo=None) > FIXED_CUTOFF:
        return False, "created_after_cutoff"
    if updated.time().replace(tzinfo=None) > FIXED_CUTOFF:
        return False, "updated_after_cutoff"
    if created >= deadline:
        return False, "created_at_or_after_deadline"
    if updated >= deadline:
        return False, "updated_at_or_after_deadline"
    return True, "timing_clean"
