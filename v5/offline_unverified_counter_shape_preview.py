"""Unverified V5 13-Counter daily *shape* rehearsal; NEVER a fitted state.

Accepts the readonly SourceProposals emitted from actual/conservative K+exhibition
matching. Produces 13 integer aggregate cell totals as a structural dry-run.
Does NOT generate PriorDayCounters, official-first-write evidence, decision
features, learned probability, historical ROI, or betting eligibility.
No file/SQL/HTTP side effects. Unknown refund/incident always stays UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from v5.conoha_research_source_contract import SourceProposals
from v5.offline_prior_day_factor_export import MAP_KEYS


@dataclass(frozen=True)
class HeldCounterShapePreview:
    day: date
    fit_candidates: int
    course_candidates: int
    aggregates: tuple[tuple[str, int], ...]
    reason: str = "UNVERIFIED_STRUCTURAL_REHEARSAL_NO_FIT_NO_STATE"
    fitted_prior_day_state: bool = field(default=False, init=False)
    source_provenance_authenticated: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def rehearse_unverified_counter_shapes(src: SourceProposals) -> HeldCounterShapePreview:
    """Compute only cross-checkable COUNT totals; never yield model Counter maps.

    Fit cohort contributes win/lane/class/exhibition/opponent/venue counters.
    All K-course cohort contributes course/recent-course exposures and top3.
    A fit race must have the same racer, course and position in K history.
    """
    if type(src) is not SourceProposals:
        raise ValueError("EXACT_SOURCE_PROPOSALS_REQUIRED")
    if src.retrospective_fit_authorized or src.first_capture_verified or src.forward_eligible or src.buy_eligible:
        raise ValueError("AUTHORIZED_SOURCE_NOT_ALLOWED_IN_UNVERIFIED_PREVIEW")
    fit = src.fit_proposals
    course = src.course_proposals
    if (len(fit) != src.fit_source_shape6 or
            len(course) != src.k_course_shape6):
        raise ValueError("SOURCE_PROPOSAL_CARDINALITY_MISMATCH")
    fit_ids = [r.race_id for r in fit]
    course_ids = [r.race_id for r in course]
    if len(set(fit_ids)) != len(fit_ids) or len(set(course_ids)) != len(course_ids):
        raise ValueError("DUPLICATE_CANDIDATE_RACE")
    k_by_id = {r.race_id: r for r in course}
    for race in fit:
        if (race.race_id not in k_by_id
            or race.result_status != "UNVERIFIED"
            or race.incident_free_verified is not None
            or race.refund_boats is not None
            or type(race.winner_lane) is not int
            or race.winner_lane not in range(1, 7)):
            raise ValueError("FIT_CANDIDATE_NOT_UNVERIFIED_MATCHED")
        boats = {b.lane: b for b in race.boats}
        actual = {b.lane: b for b in k_by_id[race.race_id].boats}
        if (len(race.boats) != 6 or set(boats) != set(range(1,7))
                or set(boats) != set(actual)
                or len({b.exhibition_rank for b in race.boats}) != 6
                or set(b.exhibition_rank for b in race.boats) != set(range(1,7))
                or any(
                    b.racer_number != actual[b.lane].racer_number
                    or b.start_course != actual[b.lane].start_course
                    or b.finish_position != actual[b.lane].finish_position
                    or b.is_flying is not False
                    or b.is_late is not False
                    or not isinstance(b.racer_class,str)
                    or b.racer_class not in ("A1","A2","B1","B2")
                    for b in race.boats
                ) or boats[race.winner_lane].finish_position != 1):
            raise ValueError("FIT_AND_K_FIELDS_INCONSISTENT")
    for race in course:
        b = race.boats
        if (race.result_status != "UNVERIFIED"
                or race.incident_free_verified is not None
                or race.refund_boats is not None
                or type(race.race_id) is not str
                or race.race_id[:8] != src.day.strftime("%Y%m%d")
                or len(b) != 6
                or {x.lane for x in b} != set(range(1,7))
                or {x.start_course for x in b} != set(range(1,7))
                or {x.finish_position for x in b} != set(range(1,7))
                or len({x.racer_number for x in b}) != 6
                or any(x.is_flying is not False or x.is_late is not False for x in b)):
            raise ValueError("K_COURSE_CANDIDATE_INCONSISTENT")
    if any(r.race_id[:8] != src.day.strftime("%Y%m%d") for r in fit):
        raise ValueError("FIT_DAY_MISMATCH")

    f = len(fit)
    h = len(course)
    # Totals of the 13 research Counter *families*. These are NOT the counts
    # per racer/category needed for real model fitting or any Forward decision.
    totals = {
        "lw": f,
        "lcs": 6*f,
        "lcw": f,
        "rks": 6*f,
        "rkw": f,
        "cs": 6*h,
        "ct": 3*h,
        "rcs": 6*h,
        "rct": 3*h,
        "ps": 30*f,
        "pw": 5*f,
        "vc": f,
        "vn": f,
    }
    if set(totals) != MAP_KEYS:
        raise RuntimeError("V5_THIRTEEN_COUNTER_KEYS_CHANGED")
    return HeldCounterShapePreview(
        src.day, f, h, tuple(sorted(totals.items()))
    )


def preview_summary(r: HeldCounterShapePreview) -> str:
    if type(r) is not HeldCounterShapePreview:
        raise ValueError("HELD_PREVIEW_REQUIRED")
    return "\n".join((
        "V5_SHAPE_ONLY_13_COUNTER_FAMILIES=13",
        "FIT_CANDIDATES_NOT_AUTHORIZED=" + str(r.fit_candidates),
        "K_COURSE_CANDIDATES_NOT_AUTHORIZED=" + str(r.course_candidates),
        *(f"SHAPE_{key.upper()}_TOTAL={value}" for key,value in r.aggregates),
        "PRIOR_STATE_FITTED=0",
        "REFUND_AND_INCIDENT_PROVEN=0",
        "FIRST_WRITE_PROVEN=0",
        "FORWARD_ELIGIBLE=0",
        "BUY_ELIGIBLE=0",
        r.reason,
    ))
