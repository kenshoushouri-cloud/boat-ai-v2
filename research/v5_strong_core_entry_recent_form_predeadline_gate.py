# -*- coding: utf-8 -*-
"""Research-only forward eligibility guard for six entrant rows + recent form.

This checks a PROPOSED immutable entry/feature freeze contract. The current
v2_race_entries.recent_form historical backfill is not a predeadline freeze:
its prior-day race dates do NOT certify when official results were available.

No database connector, mutation, Production, LINE or purchase. Callers MUST
independently establish first-write-wins capture provenance and publication
timestamps; this pure function cannot prove the supplied attestation itself.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

FREEZE_CONTRACT = "V5_RESEARCH_ENTRY_RECENT_FORM_FIRST_WRITE_V1"
ENTRY_SOURCE = "official_beforeinfo"
RESULT_SOURCE = "official_k_file"
MAX_PRIOR_RESULTS = 5


def _aware_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _race_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def check_frozen_entries_recent_form(
    race_id: str,
    race_date: Any,
    frozen_snapshot: Mapping[str, Any] | None,
    *,
    official_deadline_at: Any,
    prediction_cutoff_at: Any,
    immutable_provenance_verified: bool = False,
) -> dict[str, Any]:
    """Fail-closed; never mistake a retrospective K-file backfill for Forward.

    immutable_provenance_verified is a mandatory CALLER-SIDE attestation based
    on an externally verified first-write-wins artifact. Merely setting this
    boolean cannot prove immutability; this module is not an ingestion layer.
    """
    def fail(reason: str) -> dict[str, Any]:
        return {"eligible": False, "reason": reason, "scope": "entries_recent_form_only"}

    if immutable_provenance_verified is not True:
        return fail("IMMUTABLE_CAPTURE_NOT_ATTESTED")
    if not race_id or not isinstance(frozen_snapshot, Mapping) or not frozen_snapshot:
        return fail("MISSING_FROZEN_ENTRY_SNAPSHOT")
    if frozen_snapshot.get("contract") != FREEZE_CONTRACT:
        return fail("UNVERIFIED_FREEZE_CONTRACT")
    if frozen_snapshot.get("race_id") != race_id:
        return fail("RACE_ID_MISMATCH")
    if frozen_snapshot.get("source") != ENTRY_SOURCE:
        return fail("UNVERIFIED_ENTRY_SOURCE")
    target_day = _race_date(race_date)
    if target_day is None or _race_date(frozen_snapshot.get("race_date")) != target_day:
        return fail("RACE_DATE_MISMATCH")
    deadline = _aware_time(official_deadline_at)
    cutoff = _aware_time(prediction_cutoff_at)
    captured = _aware_time(frozen_snapshot.get("captured_at"))
    built = _aware_time(frozen_snapshot.get("feature_built_at"))
    frozen_deadline = _aware_time(frozen_snapshot.get("deadline_at"))
    if None in (deadline, cutoff, captured, built, frozen_deadline):
        return fail("MISSING_OR_UNZONED_TIMESTAMPS")
    if frozen_deadline != deadline:
        return fail("DEADLINE_MISMATCH")
    if not built <= captured < cutoff <= deadline:
        return fail("NOT_FROZEN_BEFORE_PREDICTION_CUTOFF")
    entries = frozen_snapshot.get("entries")
    if not isinstance(entries, (tuple, list)) or len(entries) != 6:
        return fail("NOT_SIX_ENTRY_ROWS")

    seen_lanes: set[int] = set()
    seen_racers: set[int] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            return fail("INVALID_ENTRY_ROW")
        if entry.get("race_id") != race_id:
            return fail("ENTRY_RACE_MISMATCH")
        lane, racer = entry.get("lane"), entry.get("racer_number")
        if type(lane) is not int or lane not in range(1, 7):
            return fail("INVALID_LANE")
        if type(racer) is not int or racer <= 0:
            return fail("INVALID_RACER")
        if lane in seen_lanes or racer in seen_racers:
            return fail("DUPLICATE_LANE_OR_RACER")
        seen_lanes.add(lane)
        seen_racers.add(racer)
        if entry.get("active") is not True:
            return fail("ACTIVE_STATUS_NOT_VERIFIED")
        if not isinstance(entry.get("racer_class"), str) or not entry["racer_class"].strip():
            return fail("MISSING_RACER_CLASS")
        # A neutral no-history strength is allowed only if the prior-result
        # query was independently certified complete as of the frozen build.
        if entry.get("recent_form_complete_asof") is not True:
            return fail("RECENT_FORM_ASOF_NOT_ATTESTED")
        history = entry.get("recent_form")
        if not isinstance(history, (list, tuple)) or len(history) > MAX_PRIOR_RESULTS:
            return fail("INVALID_RECENT_FORM")
        seen_history: set[str] = set()
        for item in history:
            if not isinstance(item, Mapping):
                return fail("INVALID_PRIOR_RESULT")
            if item.get("source") != RESULT_SOURCE:
                return fail("UNVERIFIED_PRIOR_SOURCE")
            history_day = _race_date(item.get("race_date"))
            if history_day is None or history_day >= target_day:
                return fail("NOT_STRICT_PRIOR_DAY")
            if item.get("racer_number") != racer:
                return fail("PRIOR_RACER_MISMATCH")
            prior_id = item.get("race_id")
            if not isinstance(prior_id, str) or not prior_id or prior_id in seen_history:
                return fail("MISSING_OR_DUPLICATE_PRIOR_RACE")
            seen_history.add(prior_id)
            published = _aware_time(item.get("published_at"))
            if published is None or published > built:
                return fail("PRIOR_RESULT_NOT_PUBLISHED_ASOF_BUILD")
            finish = item.get("finish_position")
            if type(finish) is not int or finish not in range(1, 7):
                return fail("INVALID_PRIOR_FINISH")
    if seen_lanes != {1, 2, 3, 4, 5, 6}:
        return fail("INCOMPLETE_SIX_LANES")
    return {"eligible": True, "reason": "FROZEN_SIX_ENTRIES_PRIOR_RESULT_PROVENANCE", "scope": "entries_recent_form_only"}
