"""V5 archived six-lane features -> research-only 120-ticket rank + fixed tickets.

The caller must supply previous-day-fitted model factors. This does NOT query
PostgreSQL or infer missing factors from later results/odds. Archival snapshot
availability is never proof of actual predeadline observation or eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from collections.abc import Mapping
from zoneinfo import ZoneInfo

from v5.offline_mainline_inference import (
    FROZEN_WEIGHTS, OfflineV5InferenceInput, check_offline_v5_inference,
)
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas
from v5.offline_retrospective_result_adapter import FrozenResearchRank

JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class ArchivedLane:
    lane: int
    racer_number: int
    racer_class: str
    recent_form: tuple[Mapping[str, object], ...]
    exhibition_time_rank: int | None
    exhibition_source: str | None
    exhibition_snapshot_at: datetime | None


@dataclass(frozen=True)
class ArchivedRaceFactors:
    race_id: str
    decision_cutoff_at: datetime
    deadline_at: datetime
    model_fitted_through: date
    base_probabilities: tuple[float, ...]
    factors: Mapping[str, tuple[float, ...]]
    lanes: tuple[ArchivedLane, ...]
    ticket_count: int
    stake_per_ticket_yen: int


@dataclass(frozen=True)
class ArchivedRankBridge:
    reason: str
    retrospective_race: bool = False
    historical_exhibition_lanes: int = 0
    late_or_unknown_snapshot_lanes: int = 0
    frozen_case: FrozenResearchRank | None = None
    scenario_only: bool = field(default=True, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    real_v5_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _day(value: object) -> date | None:
    if type(value) is not str:
        return None
    try:
        return date.fromisoformat(value) if len(value) == 10 else None
    except ValueError:
        return None


def build_archived_rank(case: object) -> ArchivedRankBridge:
    """Accept only explicitly dated six-lane research inputs, no outcome data.

    A successful synthetic rank can be handed to join_ranked_v5_scenarios;
    classification still forbids calling it a genuine historical decision.
    """
    def hold(reason: str) -> ArchivedRankBridge:
        return ArchivedRankBridge(reason)

    if type(case) is not ArchivedRaceFactors:
        return hold("INPUT_TYPE_INVALID")
    if (type(case.race_id) is not str or len(case.race_id) != 14
            or not case.race_id[:8].isdigit()):
        return hold("RACE_ID_INVALID")
    try:
        race_day = datetime.strptime(case.race_id[:8], "%Y%m%d").date()
    except ValueError:
        return hold("RACE_ID_INVALID")
    if (race_day < date(2025, 7, 1)
            or type(case.model_fitted_through) is not date
            or case.model_fitted_through >= race_day):
        return hold("HISTORICAL_MODEL_TIME_LEAK_OR_UNKNOWN")
    if (not _aware(case.decision_cutoff_at) or not _aware(case.deadline_at)
            or case.decision_cutoff_at >= case.deadline_at
            or case.decision_cutoff_at.astimezone(JST).date() != race_day
            or case.deadline_at.astimezone(JST).date() != race_day):
        return hold("DECISION_CLOCK_INVALID")
    if (type(case.ticket_count) is not int or not 1 <= case.ticket_count <= 120
            or type(case.stake_per_ticket_yen) is not int
            or case.stake_per_ticket_yen < 100
            or case.stake_per_ticket_yen % 100):
        return hold("EXPLICIT_TICKET_COUNT_AND_STAKE_REQUIRED")
    if (type(case.lanes) is not tuple or len(case.lanes) != 6
            or any(type(row) is not ArchivedLane for row in case.lanes)):
        return hold("SIX_LANE_ROWS_REQUIRED")
    ordered = sorted(case.lanes, key=lambda row: row.lane)
    if tuple(row.lane for row in ordered) != (1, 2, 3, 4, 5, 6):
        return hold("LANE_IDS_INVALID_OR_DUPLICATE")
    if (any(type(row.racer_number) is not int or not 1 <= row.racer_number <= 9999
            or type(row.racer_class) is not str or not row.racer_class.strip()
            for row in ordered)
            or len({row.racer_number for row in ordered}) != 6):
        return hold("RACER_ID_OR_CLASS_INVALID")
    if (any(type(row.recent_form) is not tuple
            or not 1 <= len(row.recent_form) <= 5 for row in ordered)):
        return hold("RECENT_FORM_INCOMPLETE")
    for row in ordered:
        for item in row.recent_form:
            if not isinstance(item, Mapping):
                return hold("RECENT_FORM_ENTRY_INVALID")
            prior = _day(item.get("race_date"))
            if prior is None or prior >= race_day:
                return hold("RECENT_FORM_NOT_PRIOR_DAY")
    ranks = [row.exhibition_time_rank for row in ordered]
    if (any(type(x) is not int or not 1 <= x <= 6 for x in ranks)
            or len(set(ranks)) != 6):
        return hold("EXHIBITION_RANK_INCOMPLETE_OR_DUPLICATE")
    if any(type(row.exhibition_source) is not str
           or not row.exhibition_source.strip()
           or not _aware(row.exhibition_snapshot_at) for row in ordered):
        return hold("EXHIBITION_PROVENANCE_MISSING")
    if (type(case.base_probabilities) is not tuple
            or type(case.factors) is not dict
            or set(case.factors) != {name for name, _ in FROZEN_WEIGHTS}
            or any(type(case.factors[k]) is not tuple or len(case.factors[k]) != 6
                   for k, _ in FROZEN_WEIGHTS)):
        return hold("PREVIOUS_DAY_FROZEN_FACTOR_VECTORS_REQUIRED")
    predicted = check_offline_v5_inference(OfflineV5InferenceInput(
        case.race_id, case.decision_cutoff_at,
        tuple(row.racer_number for row in ordered),
        case.base_probabilities, case.factors,
    ))
    if not predicted.synthetic_math_consistent:
        return hold("CORE_INFERENCE_" + predicted.reason)
    ranked = rank_offline_v5_trifectas(predicted, ticket_count=case.ticket_count)
    if not ranked.synthetic_math_consistent:
        return hold("TRIFECTA_RANKING_" + ranked.reason)
    late = sum(row.exhibition_snapshot_at >= case.decision_cutoff_at
               or row.exhibition_source == "official_beforeinfo_historical"
               for row in ordered)
    reconstructed_at = max(row.exhibition_snapshot_at for row in ordered)
    return ArchivedRankBridge(
        "ARCHIVED_SIX_LANE_V5_RECONSTRUCTION_NO_REAL_ASOF_PROOF",
        True, 6, late,
        FrozenResearchRank(ranked, case.decision_cutoff_at,
                           case.deadline_at, reconstructed_at,
                           case.stake_per_ticket_yen),
    )
