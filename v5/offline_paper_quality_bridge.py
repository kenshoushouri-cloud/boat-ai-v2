"""Offline-only bridge between entry data quality and synthetic V5 math.

A conservative research scaffold; NOT connected to ConoHa, PostgreSQL,
live VIEWs, the shadow watcher, or a real model feature adapter.
It never accesses the network, writes data, or authorizes BUY.

The current frozen five-factor math is *not* certified missing-aware.
Officially unpublished stats preserve a racer's established strength, but
must not be passed to that math as zero or silently imputed.
"""
from __future__ import annotations

from dataclasses import dataclass

from v5.entry_quality_policy import LaneInput, inspect_race
from v5.offline_mainline_inference import (
    OfflineV5InferenceInput, check_offline_v5_inference,
)


@dataclass(frozen=True)
class SyntheticPaperCandidate:
    entries: tuple[LaneInput, ...]
    math_input: OfflineV5InferenceInput
    # Must be explicitly set by a synthetic-only caller.
    synthetic_only: bool


@dataclass(frozen=True)
class SyntheticPaperVerdict:
    reason: str
    entry_quality_status: str = ""
    lane_probabilities: tuple[float, ...] = ()
    synthetic_scoring_executed: bool = False
    independently_authenticated_source: bool = False
    original_first_observation_verified: bool = False
    six_active_starts_confirmed: bool = False
    selection_eligible: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False


def evaluate_synthetic_paper(candidate: object) -> SyntheticPaperVerdict:
    """Fail closed on missing/invalid entry evidence before synthetic math.

    The returned distribution, when present, concerns *first place only*.
    It is neither a 3連単 ranking nor real before-deadline model validation.
    """
    if (type(candidate) is not SyntheticPaperCandidate
            or candidate.synthetic_only is not True):
        return SyntheticPaperVerdict("SYNTHETIC_ONLY_REQUIRED_HOLD")
    quality = inspect_race(candidate.entries)
    if not quality.research_candidate:
        return SyntheticPaperVerdict("ENTRY_QUALITY_HOLD", quality.status)
    if any(l.requires_missing_aware_model for l in quality.lanes):
        return SyntheticPaperVerdict(
            "MISSING_AWARE_MODEL_NOT_VALIDATED_HOLD", quality.status)
    inference = candidate.math_input
    if type(inference) is not OfflineV5InferenceInput:
        return SyntheticPaperVerdict("MATH_INPUT_INVALID_HOLD", quality.status)
    ordered_racers = tuple(
        lane.racer_number for lane in sorted(candidate.entries, key=lambda x: x.lane))
    if (type(inference.lane_racer_numbers) is not tuple
            or inference.lane_racer_numbers != ordered_racers):
        return SyntheticPaperVerdict("LANE_IDENTITY_MISMATCH_HOLD", quality.status)
    math_result = check_offline_v5_inference(inference)
    if not math_result.synthetic_math_consistent:
        return SyntheticPaperVerdict(
            "MATH_INPUT_INVALID_HOLD", quality.status)
    return SyntheticPaperVerdict(
        reason="SYNTHETIC_FIRST_PLACE_RESEARCH_ONLY_HARD_HOLD",
        entry_quality_status=quality.status,
        lane_probabilities=math_result.lane_probabilities,
        synthetic_scoring_executed=True,
    )
