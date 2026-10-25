"""V5 entry-quality and missingness gate (pure, fail-closed).

This is a policy/validation layer, NOT the live prediction engine and never
a BUY authorization. Officially *unreported* statistics are not zero or an
indicator of low racer ability. Parser failures are a distinct failure mode.

A missing value is called OFFICIAL_UNREPORTED only if the caller possesses
trusted source evidence; an SQL NULL alone does not prove that status.
No HTTP/DB/filesystem/network IO or writes occur in this module.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional

# The thirteen fields currently emitted by repair_month_all_pg.py.
STATS = (
    "avg_st",
    "national_win_rate",
    "national_place2_rate",
    "national_place3_rate",
    "local_win_rate",
    "local_place2_rate",
    "local_place3_rate",
    "motor_no",
    "motor_place2_rate",
    "motor_place3_rate",
    "boat_no",
    "boat_place2_rate",
    "boat_place3_rate",
)
_OFFICIAL_UNREPORTED = "OFFICIAL_UNREPORTED"
_UNVERIFIED = "UNVERIFIED"
RECORDED = "RECORDED"
# Parser failure is not a legitimate official missing value.
RANGE = {
    "avg_st": (0., 1.),
    "national_win_rate": (0., 20.),
    "local_win_rate": (0., 20.),
    **{key: (0., 100.) for key in STATS if key.endswith("rate")
       and key not in ("national_win_rate", "local_win_rate")},
    "motor_no": (0., 999.),
    "boat_no": (0., 999.),
}


@dataclass(frozen=True)
class LaneInput:
    lane: int
    racer_number: int
    stats: Mapping[str, Optional[float]]
    # A higher-level model's already-calculated rating.  We NEVER recalculate
    # or reduce it solely because a legitimate official stat is unpublished.
    established_strength_rating: Optional[float] = None
    # Keys are missing fields; mark OFFICIAL_UNREPORTED only after validating
    # the original source. Otherwise omit or use UNVERIFIED.
    missing_evidence: Optional[Mapping[str, str]] = None
    # Must be true if the collector reported ENTRY_STATS_PARSE_FAILED.
    parser_failed: bool = False


@dataclass(frozen=True)
class LaneQuality:
    lane: int
    racer_number: int
    established_strength_rating: Optional[float]
    status: str
    missing_fields: tuple[str, ...]
    official_unreported: tuple[str, ...]
    unverified_missing: tuple[str, ...]
    research_candidate: bool
    requires_missing_aware_model: bool
    buy_eligible: bool = False


@dataclass(frozen=True)
class RaceQuality:
    status: str
    lanes: tuple[LaneQuality, ...]
    research_candidate: bool
    buy_eligible: bool = False


def _valid_rating(v: object) -> bool:
    return v is None or (
        type(v) in (int, float) and math.isfinite(v)
    )


def _valid_stat(key: str, value: object) -> bool:
    if type(value) not in (int, float) or not math.isfinite(value):
        return False
    lo, hi = RANGE[key]
    if not lo <= value <= hi:
        return False
    if key in ("motor_no", "boat_no") and value != int(value):
        return False
    return True


def inspect_lane(entry: LaneInput) -> LaneQuality:
    """Preserve independent strength rating while diagnosing source quality."""
    if type(entry) is not LaneInput:
        raise TypeError("Expected LaneInput")
    rating = entry.established_strength_rating
    invalid_shape = (
        type(entry.lane) is not int or not (1 <= entry.lane <= 6)
        or type(entry.racer_number) is not int
        or not (1 <= entry.racer_number <= 9999)
        or not isinstance(entry.stats, Mapping)
        or set(entry.stats) != set(STATS)
        or not isinstance(entry.missing_evidence or {}, Mapping)
        or not _valid_rating(rating)
        or type(entry.parser_failed) is not bool
    )
    values = entry.stats if isinstance(entry.stats, Mapping) else {}
    evidence = entry.missing_evidence or {}
    missing = tuple(k for k in STATS if values.get(k) is None)
    official = tuple(k for k in missing
                     if evidence.get(k) == _OFFICIAL_UNREPORTED)
    uncertain = tuple(k for k in missing
                      if evidence.get(k) != _OFFICIAL_UNREPORTED)
    evidence_bad = (
        set(evidence) - set(STATS)
        or any(v not in (_OFFICIAL_UNREPORTED, _UNVERIFIED, RECORDED)
               for v in evidence.values())
        or any(values.get(k) is not None and evidence.get(k) == _OFFICIAL_UNREPORTED
               for k in STATS)
    )
    invalid_values = any(
        values.get(k) is not None and not _valid_stat(k, values[k])
        for k in STATS
    )
    if invalid_shape or evidence_bad or invalid_values:
        status = "INVALID_OR_CONFLICTING_INPUT_HOLD"
    elif entry.parser_failed:
        status = "PARSER_FAILURE_HOLD"
    elif len(missing) == len(STATS):
        status = "ALL_STATS_MISSING_HOLD"
    elif uncertain:
        status = "UNVERIFIED_MISSING_HOLD"
    elif official:
        status = "OFFICIAL_UNREPORTED_RESEARCH_ONLY"
    else:
        status = "COMPLETE_STATS_RESEARCH_ONLY"
    research = status in (
        "COMPLETE_STATS_RESEARCH_ONLY",
        "OFFICIAL_UNREPORTED_RESEARCH_ONLY",
    )
    return LaneQuality(
        lane=entry.lane, racer_number=entry.racer_number,
        established_strength_rating=rating, status=status,
        missing_fields=missing, official_unreported=official,
        unverified_missing=uncertain, research_candidate=research,
        requires_missing_aware_model=bool(official),
    )


def inspect_race(entries: tuple[LaneInput, ...]) -> RaceQuality:
    """No full-venue ban: six-lane identity and each actual lane are checked."""
    if type(entries) is not tuple or len(entries) != 6:
        return RaceQuality("SIX_LANE_INPUT_SHAPE_HOLD", (), False)
    try:
        outcomes = tuple(inspect_lane(x) for x in entries)
    except (TypeError, ValueError, AttributeError):
        return RaceQuality("SIX_LANE_INPUT_SHAPE_HOLD", (), False)
    if ({x.lane for x in outcomes} != set(range(1, 7))
            or len({x.racer_number for x in outcomes}) != 6):
        return RaceQuality("SIX_LANE_IDENTITY_HOLD", outcomes, False)
    if not all(x.research_candidate for x in outcomes):
        return RaceQuality("AT_LEAST_ONE_LANE_QUALITY_HOLD", outcomes, False)
    if any(x.requires_missing_aware_model for x in outcomes):
        return RaceQuality("MISSING_AWARE_RESEARCH_ONLY", outcomes, True)
    return RaceQuality("COMPLETE_STATS_RESEARCH_ONLY", outcomes, True)
