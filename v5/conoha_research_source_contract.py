"""Stable V5 one-day read-only source proposal type.

This dataclass lives outside the executable -m module so exact type identity
survives Python's __main__ / canonical module import split. Research only;
no source authentication, no state fit, no Forward or BUY authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from v5.offline_retrospective_counter_seed import RetrospectiveResearchRace
from v5.offline_research_two_population_day import CourseHistoryRace


@dataclass(frozen=True)
class SourceProposals:
    day: date
    race_total: int
    roster6: int
    k_course_shape6: int
    exhibition6: int
    fit_source_shape6: int
    fit_proposals: tuple[RetrospectiveResearchRace, ...]
    course_proposals: tuple[CourseHistoryRace, ...]
    # No independent incident/refund/first-write attestation has been made.
    first_capture_verified: bool = False
    retrospective_fit_authorized: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False
