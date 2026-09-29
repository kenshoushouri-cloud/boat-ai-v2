"""Pure adapter from current v2_race_entries-shaped rows to the F-count companion.

No database/network/file access. No persistence. The future approved I/O layer
must supply already-read entry rows and an already-frozen formal V4 artifact.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from research.candidate_discovery_v4_capture_arbiter import (
    canonical_core_payload_sha256,
)
from research.v4_fcount_companion_contract import (
    build_companion,
    canonical_companion_sha256,
)

LANES = set(range(1, 7))
FORBIDDEN_OUTCOME_KEYS = {
    "winner_lane",
    "actual_head",
    "finish_order",
    "finish_position",
    "payout",
    "payoff",
    "result",
}
FUTURE_APPROVED_SELECT = (
    "select race_id,lane,f_count "
    "from v2_race_entries "
    "where race_id=any(%s) "
    "order by race_id,lane"
)


def _formal_core_ids(formal: Mapping[str, Any]) -> tuple[str, ...]:
    feed = formal.get("feed")
    if not isinstance(feed, list):
        raise ValueError("formal V4 feed required")
    rows = [
        row
        for row in feed
        if isinstance(row, Mapping)
        and row.get("daily_rank") is not None
        and row.get("legacy_carryover") is False
    ]
    if len(rows) != 6:
        raise ValueError("exact six formal core races required")
    rows.sort(key=lambda row: int(row["daily_rank"]))
    if [int(row["daily_rank"]) for row in rows] != list(range(1, 7)):
        raise ValueError("formal daily ranks must be 1..6")
    ids = tuple(str(row.get("race_id") or "") for row in rows)
    if any(not rid for rid in ids) or len(set(ids)) != 6:
        raise ValueError("six unique formal race IDs required")
    return ids


def normalize_f_counts(
    formal: Mapping[str, Any],
    entry_rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[int, int]]:
    """Normalize exactly 36 pre-result entry rows into six race/lane F-count maps."""
    formal_ids = _formal_core_ids(formal)
    allowed = set(formal_ids)
    grouped: dict[str, dict[int, int]] = defaultdict(dict)
    seen_rows = 0

    for raw in entry_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("entry row must be a mapping")
        if any(key in raw for key in FORBIDDEN_OUTCOME_KEYS):
            raise ValueError("outcome-like fields forbidden in F-count input rows")

        rid = str(raw.get("race_id") or "")
        if rid not in allowed:
            raise ValueError("entry row race_id outside formal six")
        lane = raw.get("lane")
        if type(lane) is not int or lane not in LANES:
            raise ValueError("entry lane must be exact integer 1..6")
        value = raw.get("f_count")
        if type(value) is not int or value < 0:
            raise ValueError("f_count must be a non-negative integer")
        if lane in grouped[rid]:
            raise ValueError("duplicate race/lane F-count row")
        grouped[rid][lane] = value
        seen_rows += 1

    if seen_rows != 36:
        raise ValueError("exactly 36 F-count entry rows required")
    if set(grouped) != allowed:
        raise ValueError("F-count race set must equal formal six")
    for rid in formal_ids:
        if set(grouped[rid]) != LANES:
            raise ValueError("each formal race requires lanes 1..6 exactly")

    return {rid: dict(grouped[rid]) for rid in formal_ids}


def build_companion_from_entry_rows(
    formal: Mapping[str, Any],
    entry_rows: Iterable[Mapping[str, Any]],
    *,
    captured_at_jst: Any,
) -> tuple[dict[str, Any], str]:
    """Build the companion in memory and return it with its deterministic SHA256."""
    formal_hash_before = canonical_core_payload_sha256(formal)
    counts = normalize_f_counts(formal, entry_rows)
    companion = build_companion(
        formal,
        f_counts_by_race=counts,
        captured_at_jst=captured_at_jst,
    )
    formal_hash_after = canonical_core_payload_sha256(formal)
    if formal_hash_before != formal_hash_after:
        raise RuntimeError("formal V4 canonical core changed during F-count adaptation")
    if companion["formal_v4_canonical_core_sha256"] != formal_hash_before:
        raise RuntimeError("companion/formal canonical core hash mismatch")
    return companion, canonical_companion_sha256(companion)
