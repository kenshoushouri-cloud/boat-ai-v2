"""Six extracted archival lanes + dated V5 factors -> RESEARCH-ONLY input.

No DB, HTTP, results, odds, frozen purchase, Forward or BUY operations.
A supplied cutoff is not proof of an actual historic decision timestamp.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from v5.offline_archived_six_lane_bridge import ArchivedLane, ArchivedRaceFactors
from v5.offline_prior_day_factor_export import FactorVectors
from v5.offline_six_lane_raw_extract_guard import (
    RACE, RACE_DAY, inspect_six_lane_raw_extract,
)

JST = ZoneInfo("Asia/Tokyo")
FACTOR_KEYS = frozenset((
    "recent_form", "exhibition_rank", "racer_course", "opponent", "venue_lane",
))
# Exact projected columns of ops/v5_oomura12_six_lane_values_readonly_20260501.sql.
# This rejects accident-prone result/odds/settlement data before prediction.
APPROVED_RAW_COLUMNS = frozenset((
    "race_id", "race_date", "deadline_at", "lane", "racer_number",
    "racer_class", "recent_form_json_type", "parsed_history",
    "exhibition_source", "exhibition_time_rank", "exhibition_snapshot_at",
    "exhibition_reuse_contract", "exhibition_source_contract",
    "source_snapshot_label", "source_snapshot_at_text",
    "independent_official_six_active_verified",
    "original_first_observation_verified", "forward_eligible", "buy_eligible",
))


@dataclass(frozen=True)
class ArchivedInputBoundary:
    reason: str
    blockers: tuple[str, ...]
    archived_case: ArchivedRaceFactors | None = None
    source_warnings: tuple[str, ...] = ()
    retrospective_only: bool = field(default=True, init=False)
    prior_day_model_origin_independently_verified: bool = field(default=False, init=False)
    original_predeadline_cutoff_verified: bool = field(default=False, init=False)
    official_six_active_verified: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _clock(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _six_vector(values: object, *, normalized: bool) -> bool:
    if (type(values) is not tuple or len(values) != 6
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   or not 0 < v <= (1. if normalized else 1e6)
                   for v in values)):
        return False
    return not normalized or math.isclose(
        math.fsum(values), 1., rel_tol=0., abs_tol=1e-9)


def prepare_archived_research_input(
    raw_rows: object,
    prior_day_factors: object,
    *,
    decision_cutoff_at: object = None,
    ticket_count: object = None,
    stake_per_ticket_yen: object = None,
) -> ArchivedInputBoundary:
    """Return an ArchivedRaceFactors only if each research datum is supplied.

    No defaults, no backward inference of cutoff, no substitute for missing
    counters and no promotion to authenticated live or historical decisions.
    """
    audit = inspect_six_lane_raw_extract(raw_rows)
    if not audit.research_value_shape_complete:
        return ArchivedInputBoundary(
            "HOLD_SIX_LANE_RAW_VALUES", tuple(audit.reasons))

    assert isinstance(raw_rows, (list, tuple))  # implied by the complete audit
    if any(not isinstance(r, Mapping) or set(r) - APPROVED_RAW_COLUMNS
           for r in raw_rows):
        return ArchivedInputBoundary(
            "HOLD_UNREVIEWED_RAW_COLUMNS", ("RESULT_ODDS_OR_UNKNOWN_COLUMNS_PRESENT",))

    # Raw extract dates/history MUST retain evidence-like unaltered provenance.
    # No parsing/coercion of incomplete or non-string dates.
    for row in raw_rows:
        if (type(row["parsed_history"]) not in (list, tuple)
                or any(not isinstance(h, Mapping)
                       or type(h.get("race_date")) is not str
                       or len(h["race_date"]) != 10
                       for h in row["parsed_history"])):
            return ArchivedInputBoundary(
                "HOLD_HISTORY_RAW_FORMAT", ("UNSUPPORTED_HISTORY_DATE_FORMAT",))

    if type(prior_day_factors) is not FactorVectors:
        return ArchivedInputBoundary(
            "HOLD_PRIOR_DAY_FACTORS_MISSING", ("FACTORS_NOT_EXPORTED",))
    state = prior_day_factors
    if (state.reason != "RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY"
            or state.race_id != RACE
            or type(state.fitted_through) is not date
            or not date(2025, 7, 1) <= state.fitted_through < RACE_DAY
            or any(getattr(state, name) is not False for name in (
                "source_state_independently_verified",
                "original_first_observation_verified", "forward_eligible",
                "buy_eligible"))):
        return ArchivedInputBoundary(
            "HOLD_UNVERIFIED_OR_LEAKING_FACTOR_DATE",
            ("PRIOR_DAY_FACTOR_SOURCE_OR_DATE_INVALID",))
    if (not _six_vector(state.base_probabilities, normalized=True)
            or not isinstance(state.factors, Mapping)
            or set(state.factors) != FACTOR_KEYS
            or any(not _six_vector(state.factors[k], normalized=False)
                   for k in FACTOR_KEYS)):
        return ArchivedInputBoundary(
            "HOLD_FACTOR_VALUES_INCOMPLETE", ("FIVE_SIX_LANE_VECTORS_REQUIRED",))

    if (not _clock(decision_cutoff_at)
            or decision_cutoff_at.astimezone(JST).date() != RACE_DAY
            or decision_cutoff_at >= raw_rows[0]["deadline_at"]):
        return ArchivedInputBoundary(
            "HOLD_DECISION_CUTOFF_UNVERIFIED", ("EXPLICIT_PREDEADLINE_CLOCK_REQUIRED",))
    if (type(ticket_count) is not int or not 1 <= ticket_count <= 120
            or type(stake_per_ticket_yen) is not int
            or stake_per_ticket_yen < 100 or stake_per_ticket_yen % 100):
        return ArchivedInputBoundary(
            "HOLD_EXPLICIT_RESEARCH_TICKET_POLICY",
            ("TICKET_COUNT_AND_STAKE_MUST_BE_EXPLICIT",))

    rows = sorted(raw_rows, key=lambda r: r["lane"])
    six_lanes = tuple(ArchivedLane(
        row["lane"], row["racer_number"], row["racer_class"],
        tuple(dict(h) for h in row["parsed_history"]),
        row["exhibition_time_rank"], row["exhibition_source"],
        row["exhibition_snapshot_at"],
    ) for row in rows)
    # This is a *scenario input*, not proof it was selected or staked then.
    archived = ArchivedRaceFactors(
        RACE, decision_cutoff_at, raw_rows[0]["deadline_at"],
        state.fitted_through, tuple(state.base_probabilities),
        {key: tuple(state.factors[key]) for key in FACTOR_KEYS},
        six_lanes, ticket_count, stake_per_ticket_yen,
    )
    return ArchivedInputBoundary(
        "ARCHIVED_RESEARCH_INPUT_ONLY_NO_ORIGINAL_ASOF_PROOF", (),
        archived, tuple(audit.reasons),
    )
