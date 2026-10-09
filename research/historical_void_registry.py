# -*- coding: utf-8 -*-
"""Research-only, immutable registry of officially confirmed race cancellations.

Source: official BOAT RACE K files for 2026-08-11, 2026-09-09,
2026-09-21 and 2026-09-22; exact race-by-race cancellation headers
confirmed by GitHub Issue #581 result comment 6077502477.

This is a narrowly scoped evidence register, NOT a general incident classifier.
Not listed does NOT mean race eligible: other incident checks still apply.
No DB reads/writes, model changes, or fabricated outcomes occur here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EVIDENCE_SOURCE = "official_k_file_explicit_cancellation_header"
EVIDENCE_REF = "github_issue_581_comment_6077502477"

# Inclusive race-number ranges. Venue IDs match the official 01..24 codes.
# The 2026-09-21 津4R and 三国9R settled normally and are NOT listed.
_CANCELLED_GROUPS: tuple[tuple[str, str, int, int], ...] = (
    ("2026-08-11", "03", 1, 12),  # 江戸川: full day
    ("2026-09-09", "03", 1, 12),  # 江戸川: full day
    ("2026-09-21", "02", 1, 12),  # 戸田: full day
    ("2026-09-21", "03", 1, 12),  # 江戸川: full day
    ("2026-09-21", "09", 5, 12),  # 津: from 5R
    ("2026-09-21", "10", 10, 12), # 三国: from 10R
    ("2026-09-22", "09", 1, 12),  # 津: full day
)


def _manifest_ids() -> frozenset[str]:
    ids: list[str] = []
    for date, venue, first, last in _CANCELLED_GROUPS:
        if not (len(date) == 10 and len(venue) == 2 and 1 <= first <= last <= 12):
            raise ValueError("Invalid verified cancellation group")
        for race in range(first, last + 1):
            ids.append(f"{date.replace('-', '')}_{venue}_{race:02d}")
    if len(ids) != 71 or len(set(ids)) != 71:
        raise ValueError("Verified K cancellation registry must have exactly 71 unique IDs")
    return frozenset(ids)


VERIFIED_VOID_RACE_IDS = _manifest_ids()


@dataclass(frozen=True)
class HistoricalVoidDecision:
    race_id: str
    state: Literal["VERIFIED_VOID", "UNDETERMINED"]
    evidence_source: str | None
    evidence_ref: str | None
    primary_training_eligible: bool | None
    backtest_treatment: Literal["VOID", "CHECK_OTHER_ELIGIBILITY"]
    hypothetical_investment: int | None


def classify_historical_void(race_id: str) -> HistoricalVoidDecision:
    """Fail-closed for confirmed cancellations; abstain for every other race.

    A non-cancelled ID must STILL pass ordinary six-boat/incident/timing checks.
    Unknown is never an implicit assertion of train or bet eligibility.
    """
    if not isinstance(race_id, str):
        raise TypeError("race_id must be a string")
    if race_id in VERIFIED_VOID_RACE_IDS:
        return HistoricalVoidDecision(
            race_id=race_id,
            state="VERIFIED_VOID",
            evidence_source=EVIDENCE_SOURCE,
            evidence_ref=EVIDENCE_REF,
            primary_training_eligible=False,
            backtest_treatment="VOID",
            hypothetical_investment=0,
        )
    return HistoricalVoidDecision(
        race_id=race_id,
        state="UNDETERMINED",
        evidence_source=None,
        evidence_ref=None,
        primary_training_eligible=None,
        backtest_treatment="CHECK_OTHER_ELIGIBILITY",
        hypothetical_investment=None,
    )
