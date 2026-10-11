"""Fail-closed inspection for ONE archived six-lane raw-value SQL result.

Pure offline structural check. No DB, official GET, results, odds or purchases.
Even a complete result is only an archival research candidate; it NEVER
authenticates the official six starters or an original predeadline capture.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

RACE = "20260501_24_12"
RACE_DAY = date(2026, 5, 1)
JST = ZoneInfo("Asia/Tokyo")
CLASSES = frozenset(("A1", "A2", "B1", "B2"))
PROOF_COLUMNS = (
    "independent_official_six_active_verified",
    "original_first_observation_verified",
    "forward_eligible", "buy_eligible",
)
DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")


@dataclass(frozen=True)
class SixLaneExtractAudit:
    status: str
    row_count: int
    reasons: tuple[str, ...]
    research_value_shape_complete: bool
    retrospective_only: bool = field(default=True, init=False)
    official_six_active_verified: bool = field(default=False, init=False)
    original_first_observation_verified: bool = field(default=False, init=False)
    v5_real_roi_verified: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _aware(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


def _race_date(value: object) -> date | None:
    if type(value) is date:
        return value
    if type(value) is str and DATE_RE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


def inspect_six_lane_raw_extract(rows: object) -> SixLaneExtractAudit:
    """Require complete six-row values; no null coercion or duplicate dropping.

    Does NOT build ArchivedRaceFactors: true dated prior-day factor vectors,
    selected tickets, model version, and decision_cutoff are separate proofs.
    """
    if type(rows) not in (tuple, list):
        return SixLaneExtractAudit(
            "HOLD_INVALID_ROWS", 0, ("ROWS_TYPE_INVALID",), False)
    reasons: list[str] = []
    count = len(rows)
    if count != 6:
        reasons.append("EXACTLY_SIX_ROWS_REQUIRED")
    seen_lanes: set[int] = set()
    seen_racers: set[int] = set()
    seen_ranks: set[int] = set()
    deadlines: set[datetime] = set()
    archival_warnings: set[str] = set()
    for i, row in enumerate(rows):
        prefix = f"ROW_{i+1}_"
        if not isinstance(row, Mapping):
            reasons.append(prefix + "MAPPING_REQUIRED")
            continue
        if row.get("race_id") != RACE or _race_date(row.get("race_date")) != RACE_DAY:
            reasons.append(prefix + "RACE_ID_OR_DAY_MISMATCH")
        lane = row.get("lane")
        if type(lane) is not int or lane not in range(1, 7) or lane in seen_lanes:
            reasons.append(prefix + "LANE_MISSING_INVALID_OR_DUPLICATE")
        else:
            seen_lanes.add(lane)
        number = row.get("racer_number")
        if (type(number) is not int or not 1 <= number <= 9999
                or number in seen_racers):
            reasons.append(prefix + "RACER_MISSING_INVALID_OR_DUPLICATE")
        else:
            seen_racers.add(number)
        if row.get("racer_class") not in CLASSES:
            reasons.append(prefix + "RACER_CLASS_MISSING_OR_INVALID")
        history = row.get("parsed_history")
        if (type(history) not in (tuple, list) or not 1 <= len(history) <= 5
                or row.get("recent_form_json_type") not in ("array", "object")):
            reasons.append(prefix + "RECENT_FORM_MISSING_OR_INVALID")
        else:
            for value in history:
                if (not isinstance(value, Mapping)
                        or _race_date(value.get("race_date")) is None
                        or not _race_date(value.get("race_date")) < RACE_DAY):
                    reasons.append(prefix + "RECENT_FORM_NOT_PRIOR_DAY")
                    break
        rank = row.get("exhibition_time_rank")
        if type(rank) is not int or rank not in range(1, 7) or rank in seen_ranks:
            reasons.append(prefix + "EXHIBITION_RANK_MISSING_OR_DUPLICATE")
        else:
            seen_ranks.add(rank)
        source = row.get("exhibition_source")
        if type(source) is not str or not source.strip():
            reasons.append(prefix + "EXHIBITION_SOURCE_MISSING")
        elif source == "official_beforeinfo_historical":
            archival_warnings.add("HISTORICAL_SOURCE_NOT_PREDECISION_PROOF")
        captured = row.get("exhibition_snapshot_at")
        deadline = row.get("deadline_at")
        if not _aware(deadline) or deadline.astimezone(JST).date() != RACE_DAY:
            reasons.append(prefix + "DEADLINE_TIMEZONE_OR_DATE_UNVERIFIED")
        else:
            deadlines.add(deadline)
        if not _aware(captured):
            reasons.append(prefix + "SNAPSHOT_TIMEZONE_OR_VALUE_UNVERIFIED")
        elif _aware(deadline) and captured >= deadline:
            archival_warnings.add("EXHIBITION_SNAPSHOT_AFTER_DEADLINE")
        if any(row.get(key) is not False for key in PROOF_COLUMNS):
            reasons.append(prefix + "PROOF_COLUMNS_NOT_FALSE")
    if len(deadlines) > 1:
        reasons.append("INCONSISTENT_LANE_DEADLINES")
    if count == 6 and (len(seen_lanes) != 6 or len(seen_racers) != 6
                       or len(seen_ranks) != 6):
        reasons.append("SIX_DISTINCT_LANES_RACERS_RANKS_REQUIRED")
    complete = not reasons
    return SixLaneExtractAudit(
        "ARCHIVED_VALUE_SHAPE_ONLY" if complete
        else "HOLD_INCOMPLETE_SIX_LANE_VALUES",
        count, tuple(reasons + sorted(archival_warnings)), complete)
