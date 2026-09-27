"""Pure companion-artifact contract for prospective V4 F-count diagnostics.

This module never reads a database/network, writes files, sends LINE, changes
Production, or authorizes purchase. It binds caller-supplied F counts to an
already-frozen formal V4 artifact by canonical core SHA256.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from typing import Any, Mapping

from research.candidate_discovery_v4_capture_arbiter import (
    canonical_core_payload_sha256,
)

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
CORE_RACES = 6
LANES = tuple(range(1, 7))
CONTRACT = "candidate_discovery_v4_fcount_companion_v1"


def _aware(value: Any) -> datetime:
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception as exc:
        raise ValueError("timezone-aware ISO datetime required") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return dt.astimezone(JST)


def _strict_nonnegative_int(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("F count must be a non-negative integer")
    return value


def _formal_core_rows(formal: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    feed = formal.get("feed")
    if not isinstance(feed, list):
        raise ValueError("formal V4 feed required")
    rows = [
        row for row in feed
        if isinstance(row, Mapping)
        and row.get("daily_rank") is not None
        and row.get("legacy_carryover") is False
    ]
    if len(rows) != CORE_RACES:
        raise ValueError("exact six formal V4 core races required")
    rows.sort(key=lambda row: int(row["daily_rank"]))
    if [int(row["daily_rank"]) for row in rows] != list(range(1, CORE_RACES + 1)):
        raise ValueError("formal daily ranks must be 1..6")
    return rows


def build_companion(
    formal: Mapping[str, Any],
    *,
    f_counts_by_race: Mapping[str, Mapping[int | str, int]],
    captured_at_jst: Any,
) -> dict[str, Any]:
    """Build a deterministic pre-result F-count companion in memory."""
    if formal.get("purchase_action") is not False:
        raise ValueError("formal purchase_action must be false")
    if formal.get("prospective_evidence_eligible") is not True:
        raise ValueError("formal prospective evidence must be eligible")

    provenance = formal.get("freeze_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("formal freeze provenance required")
    if provenance.get("outcome_read") is not False:
        raise ValueError("formal freeze must be outcome-free")
    if provenance.get("all_frozen_rows_pre_deadline") is not True:
        raise ValueError("formal rows must be pre-deadline")

    target_date = str(provenance.get("target_date") or "")
    if not target_date:
        raise ValueError("formal target_date required")
    captured = _aware(captured_at_jst)
    cutoff = datetime.combine(
        datetime.fromisoformat(target_date).date(), SOURCE_CUTOFF, tzinfo=JST
    )
    if captured.date().isoformat() != target_date or captured < cutoff:
        raise ValueError("companion capture must be target-day and after 08:15 JST")

    formal_generated = _aware(formal.get("generated_at_jst"))
    if captured < formal_generated:
        raise ValueError("companion cannot precede the formal V4 freeze")

    core = _formal_core_rows(formal)
    expected_ids = {str(row.get("race_id") or "") for row in core}
    supplied_ids = {str(key) for key in f_counts_by_race}
    if supplied_ids != expected_ids:
        raise ValueError("F-count race set must exactly equal formal V4 core")

    out_rows = []
    for row in core:
        race_id = str(row.get("race_id") or "")
        deadline = _aware(row.get("deadline_at"))
        if captured >= deadline:
            raise ValueError("companion capture must precede every core deadline")
        head = int(row.get("head_lane") or 0)
        if head not in LANES:
            raise ValueError("formal predicted head must be 1..6")
        raw_counts = f_counts_by_race[race_id]
        normalized = {}
        for lane in LANES:
            value = raw_counts.get(lane, raw_counts.get(str(lane)))
            normalized[str(lane)] = _strict_nonnegative_int(value)
        if len(raw_counts) != 6:
            raise ValueError("exact six F-count lanes required")
        out_rows.append({
            "race_id": race_id,
            "daily_rank": int(row["daily_rank"]),
            "predicted_head": head,
            "predicted_head_f_count": normalized[str(head)],
            "f_counts": normalized,
            "deadline_at": deadline.isoformat(),
        })

    companion = {
        "contract": CONTRACT,
        "target_date": target_date,
        "captured_at_jst": captured.isoformat(),
        "formal_v4_generated_at_jst": formal_generated.isoformat(),
        "formal_v4_canonical_core_sha256": canonical_core_payload_sha256(formal),
        "core": out_rows,
        "outcome_read": False,
        "odds_read": False,
        "payout_read": False,
        "db_write": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    return companion


def canonical_companion_sha256(companion: Mapping[str, Any]) -> str:
    if companion.get("contract") != CONTRACT:
        raise ValueError("unexpected companion contract")
    if companion.get("purchase_action") is not False:
        raise ValueError("purchase_action must be false")
    if companion.get("outcome_read") is not False:
        raise ValueError("outcome_read must be false")
    encoded = json.dumps(
        companion,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
