"""Held V5 per-key occupancy rehearsal from real-shape proposals.

This extends 13-family SHAPE totals to anonymous distinct-counter-cell counts.
It NEVER returns usable Counter maps, PriorDayCounters, model coefficients,
betting predictions, result refunds, or original capture assertions.
Observed race data are retrospective, not verified as original predecision
features; all source authority and fit gates remain HOLD.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from v5.conoha_research_source_contract import SourceProposals
from v5.offline_prior_day_factor_export import MAP_KEYS
from v5.offline_unverified_counter_shape_preview import (
    rehearse_unverified_counter_shapes,
)


@dataclass(frozen=True)
class UnverifiedCounterCellAudit:
    day: date
    fit_candidates: int
    k_course_candidates: int
    # Each family: (name, total exposures, distinct nonzero category keys).
    # Never expose racer IDs or the original category-valued maps.
    family_cells: tuple[tuple[str, int, int], ...]
    reason: str = "RETROSPECTIVE_UNVERIFIED_CELL_COUNTS_NO_MODEL_STATE"
    source_authenticated: bool = field(default=False, init=False)
    prior_state_fitted: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def count_unverified_cells(src: SourceProposals) -> UnverifiedCounterCellAudit:
    """Rehearse exact cell occupancy separately for fit and K-course cohorts.

    This is NOT historical model parity or a complete pre-day model state.
    """
    audited = rehearse_unverified_counter_shapes(src)  # all HOLD guards
    observed = {name: Counter() for name in MAP_KEYS}
    for race in src.fit_proposals:
        winner = race.winner_lane
        venue = race.race_id[9:11]
        b = {row.lane: row for row in race.boats}
        observed["lw"][winner] += 1
        observed["vc"][(venue, winner)] += 1
        observed["vn"][venue] += 1
        for lane in range(1, 7):
            row = b[lane]
            cl = row.racer_class
            rk = str(row.exhibition_rank)
            observed["lcs"][(lane, cl)] += 1
            observed["rks"][(lane, cl, rk)] += 1
            for opp in range(1, 7):
                if lane == opp:
                    continue
                key = (lane, cl, opp, b[opp].racer_class)
                observed["ps"][key] += 1
                if winner == lane:
                    observed["pw"][key] += 1
        w = b[winner]
        observed["lcw"][(winner, w.racer_class)] += 1
        observed["rkw"][(winner, w.racer_class, str(w.exhibition_rank))] += 1
    for race in src.course_proposals:
        for b in race.boats:
            course = b.start_course
            observed["cs"][course] += 1
            observed["rcs"][(course, b.racer_number)] += 1
            if b.finish_position <= 3:
                observed["ct"][course] += 1
                observed["rct"][(course, b.racer_number)] += 1
    expected = dict(audited.aggregates)
    if set(observed) != MAP_KEYS:
        raise RuntimeError("COUNTER_FAMILY_SET_MISMATCH")
    cells = []
    for name in sorted(observed):
        total = sum(observed[name].values())
        if total != expected[name]:
            raise ValueError("COUNTER_FAMILY_TOTAL_PARITY_FAILURE")
        cells.append((name, total, len(observed[name])))
    return UnverifiedCounterCellAudit(
        src.day, audited.fit_candidates, audited.course_candidates,
        tuple(cells),
    )


def cell_summary(out: UnverifiedCounterCellAudit) -> str:
    if type(out) is not UnverifiedCounterCellAudit:
        raise ValueError("EXACT_HELD_CELL_AUDIT_REQUIRED")
    return "\n".join((
        f"V5_RESEARCH_CELL_PREVIEW_DAY={out.day.isoformat()}",
        f"FIT_SHAPE_CANDIDATES_UNVERIFIED={out.fit_candidates}",
        f"K_HISTORY_SHAPE_CANDIDATES_UNVERIFIED={out.k_course_candidates}",
        *(f"CELL_{key.upper()}_TOTAL={total}_DISTINCT_NONZERO={n}"
          for key, total, n in out.family_cells),
        "FIRST_OBSERVATION_AUTHENTICATED=0",
        "REFUND_AND_INCIDENT_INDEPENDENTLY_PROVEN=0",
        "PRIOR_STATE_FITTED=0",
        "FORWARD_ELIGIBLE=0",
        "BUY_ELIGIBLE=0",
        out.reason,
    ))
