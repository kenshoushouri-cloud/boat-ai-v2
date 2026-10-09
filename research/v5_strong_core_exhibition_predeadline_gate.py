# -*- coding: utf-8 -*-
"""Research-only, fail-closed exhibition provenance gate for prospective V5.

A historical 'historical' snapshot may be overwritten after the race and must
NEVER count as first-availability evidence. A caller must load the target row
from the immutable first-write-wins dedicated shadow table and supply the
independently verified race deadline and actual prediction cutoff.

This checks ONLY the exhibition input. It cannot certify recent_form, entry
features, six active racers, odds, incident knowledge, or BUY readiness.
No database, network, Production, LINE, stake or purchase actions.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

FROZEN_TABLE = "v2_bao_exhibition_shadow_snapshots"
OFFICIAL_SOURCE = "official_beforeinfo"
MIN_MINUTES_BEFORE = 8.0
MAX_MINUTES_BEFORE = 15.0


def _aware_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def check_frozen_exhibition_predeadline(
    race_id: str,
    frozen_row: Mapping[str, Any] | None,
    *,
    source_table: str,
    official_deadline_at: Any,
    prediction_cutoff_at: Any,
) -> dict[str, Any]:
    """Return a single reason; fail closed on missing/mutable/late evidence.

    `source_table` is the actual table read by the caller, NOT a historical
    alias inferred from the row. The caller must independently verify cutoff
    and deadline, and retain the original frozen capture row unchanged.
    """
    def rejected(reason: str) -> dict[str, Any]:
        return {"eligible": False, "reason": reason, "scope": "exhibition_only"}

    if source_table != FROZEN_TABLE:
        return rejected("MUTABLE_OR_UNVERIFIED_SOURCE")
    if not race_id or not isinstance(frozen_row, Mapping) or not frozen_row:
        return rejected("MISSING_FROZEN_ROW")
    if str(frozen_row.get("race_id") or "") != race_id:
        return rejected("RACE_ID_MISMATCH")
    if frozen_row.get("source") != OFFICIAL_SOURCE:
        return rejected("UNVERIFIED_OFFICIAL_SOURCE")

    captured = _aware_timestamp(frozen_row.get("captured_at"))
    frozen_deadline = _aware_timestamp(frozen_row.get("deadline_at"))
    official_deadline = _aware_timestamp(official_deadline_at)
    cutoff = _aware_timestamp(prediction_cutoff_at)
    if None in (captured, frozen_deadline, official_deadline, cutoff):
        return rejected("MISSING_OR_UNZONED_TIME")
    if frozen_deadline != official_deadline:
        return rejected("DEADLINE_MISMATCH")
    if not captured < cutoff <= official_deadline:
        return rejected("NOT_CAPTURED_BEFORE_CUTOFF")
    minutes = (official_deadline - captured).total_seconds() / 60.0
    if not MIN_MINUTES_BEFORE <= minutes <= MAX_MINUTES_BEFORE:
        return rejected("OUTSIDE_FROZEN_CAPTURE_WINDOW")

    # Never trust the stored minutes_before without comparing timestamps.
    try:
        stored_minutes = float(frozen_row.get("minutes_before"))
    except (ValueError, TypeError):
        return rejected("INVALID_STORED_WINDOW")
    if not math.isfinite(stored_minutes):
        return rejected("INVALID_STORED_WINDOW")
    if abs(stored_minutes - minutes) > 0.25:
        return rejected("STORED_WINDOW_CONFLICT")

    ranks = frozen_row.get("exhibition_time_ranks")
    times = frozen_row.get("exhibition_times")
    if not isinstance(ranks, (list, tuple)) or len(ranks) != 6:
        return rejected("INCOMPLETE_SIX_LANE_RANKS")
    if any(type(v) is not int for v in ranks) or sorted(ranks) != [1, 2, 3, 4, 5, 6]:
        return rejected("INVALID_SIX_LANE_RANKS")
    if not isinstance(times, (list, tuple)) or len(times) != 6:
        return rejected("INCOMPLETE_SIX_LANE_TIMES")
    try:
        numeric_times = [float(v) for v in times]
    except (ValueError, TypeError):
        return rejected("INVALID_SIX_LANE_TIMES")
    if any(not math.isfinite(v) or v <= 0 for v in numeric_times):
        return rejected("INVALID_SIX_LANE_TIMES")
    return {
        "eligible": True,
        "reason": "FROZEN_OFFICIAL_BEFORE_CUTOFF",
        "scope": "exhibition_only",
    }
