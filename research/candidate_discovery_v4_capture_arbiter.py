# -*- coding: utf-8 -*-
"""Pure formal-artifact arbitration contract for Candidate Discovery V4.

This module does not run a capture, access GitHub/Railway, read a database,
write files, send LINE, or authorize purchase/promotion. It only classifies
already-produced capture metadata and derives a deterministic hash for the
formal structural core of an already-produced artifact.

The contract intentionally ignores provider-local run IDs when deciding the
formal artifact. Evidence precedence is based only on validated prospective
eligibility, target date, generation timestamp and canonical core payload
SHA-256.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Mapping, Any

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
CORE_RACES = 6
CORE_TICKETS = 12
V4_CONTRACT = "candidate_discovery_v4_main_feed_v1"

FORMAL_SUMMARY_KEYS = (
    "date",
    "scheduled_races",
    "evaluable_races",
    "skipped_incomplete_entries_or_deadline",
    "core_races",
    "core_tickets",
    "course_supported_races",
    "course_usable_lanes",
    "opponent_pressure_supported_races",
    "motor2_complete_races",
)
FORMAL_POLICY_KEYS = (
    "course_coefficient",
    "course_missing_lane",
    "course_source_cutoff_jst",
    "opponent_pressure_coefficient",
    "opponent_pressure_role",
    "motor2_beta",
    "motor2_position_weights",
    "core_races_per_day",
    "core_tickets_per_race",
    "expected_value_filter",
    "odds_filter",
    "odds_read",
)
EXPECTED_FORMAL_POLICY = {
    "course_coefficient": 0.5,
    "course_missing_lane": "neutral",
    "course_source_cutoff_jst": "08:15",
    "opponent_pressure_coefficient": 1.0,
    "opponent_pressure_role": "first_place_only",
    "motor2_beta": 0.06,
    "motor2_position_weights": [1.0, 0.6, 0.3],
    "core_races_per_day": 6,
    "core_tickets_per_race": 2,
    "expected_value_filter": False,
    "odds_filter": False,
    "odds_read": False,
}
CORE_ROW_KEYS = (
    "race_id",
    "race_date",
    "venue_id",
    "race_no",
    "deadline_at",
    "tier",
    "daily_rank",
    "race_score",
    "head_lane",
    "head_p1",
    "course_usable_lanes",
    "opponent_pressure_available",
    "motor2_complete",
)


@dataclass(frozen=True)
class Capture:
    channel: str
    provider_run_id: str
    target_date: date
    generated_at_jst: datetime
    canonical_payload_sha256: str
    prospective_evidence_eligible: bool
    purchase_action: bool
    promotion_allowed: bool
    core_races: int
    core_tickets: int
    all_frozen_rows_pre_deadline: bool


@dataclass(frozen=True)
class ArbitrationResult:
    classification: str
    formal_capture: Capture | None
    duplicate_copies: tuple[Capture, ...]
    later_diagnostics: tuple[Capture, ...]
    rejected_captures: tuple[Capture, ...]

    @property
    def formal_available(self) -> bool:
        return self.classification == "FORMAL_AVAILABLE"


def _aware_jst(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("generated_at_jst must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at_jst must be timezone-aware")
    return value.astimezone(JST)


def _valid_sha256(value: str) -> bool:
    text = (value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_keys(row: Mapping[str, Any], keys: Iterable[str], name: str) -> None:
    missing = [key for key in keys if key not in row or row.get(key) is None]
    if missing:
        raise ValueError(f"{name} missing required fields: {','.join(sorted(missing))}")


def _strict_bool(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be an exact boolean")
    return value


def _strict_int(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an exact integer")
    return value


def _parse_iso_date(value: Any, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def _parse_aware_datetime(value: Any, name: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _valid_ticket(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 3 and len(set(parts)) == 3 and all(part in {"1", "2", "3", "4", "5", "6"} for part in parts)


def canonical_core_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic formal-core payload used for cross-channel hash comparison.

    Volatile capture metadata is intentionally excluded: generated/freeze timestamps,
    provider/run identity and file/archive hashes. Candidate-shadow legacy carryover is
    also excluded because it is auxiliary to the frozen 6-race/12-ticket structural core.
    In particular, LEGACY annotations added to an otherwise identical core ticket do not
    change the canonical core payload.

    Structural universe diagnostics, the frozen formal policy and all six ranked core
    race outputs remain included. Any malformed/incomplete core fails closed.
    """
    if str(artifact.get("contract") or "") != V4_CONTRACT:
        raise ValueError("unexpected V4 contract")

    summary = _mapping(artifact.get("summary"), "summary")
    policy = _mapping(artifact.get("policy"), "policy")
    feed = artifact.get("feed")
    if not isinstance(feed, list):
        raise ValueError("feed must be a list")

    _require_keys(summary, FORMAL_SUMMARY_KEYS, "summary")
    _require_keys(policy, FORMAL_POLICY_KEYS, "policy")

    target_date = _parse_iso_date(summary["date"], "summary.date")
    scheduled = _strict_int(summary["scheduled_races"], "summary.scheduled_races")
    evaluable = _strict_int(summary["evaluable_races"], "summary.evaluable_races")
    skipped = _strict_int(
        summary["skipped_incomplete_entries_or_deadline"],
        "summary.skipped_incomplete_entries_or_deadline",
    )
    if scheduled <= 0 or evaluable != scheduled or skipped != 0:
        raise ValueError("race universe incomplete")
    if _strict_int(summary["core_races"], "summary.core_races") != CORE_RACES:
        raise ValueError("core race count mismatch")
    if _strict_int(summary["core_tickets"], "summary.core_tickets") != CORE_TICKETS:
        raise ValueError("core ticket count mismatch")
    for key in (
        "course_supported_races",
        "course_usable_lanes",
        "opponent_pressure_supported_races",
        "motor2_complete_races",
    ):
        if _strict_int(summary[key], f"summary.{key}") < 0:
            raise ValueError(f"summary.{key} must be non-negative")

    for key, expected in EXPECTED_FORMAL_POLICY.items():
        actual = policy[key]
        if key in ("expected_value_filter", "odds_filter", "odds_read"):
            actual = _strict_bool(actual, f"policy.{key}")
        if actual != expected:
            raise ValueError(f"frozen policy mismatch: {key}")

    core_rows: list[Mapping[str, Any]] = []
    for raw in feed:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("daily_rank") is None:
            continue
        _require_keys(raw, CORE_ROW_KEYS + ("tickets", "legacy_carryover"), "core row")
        if _strict_bool(raw["legacy_carryover"], "core row legacy_carryover") is not False:
            raise ValueError("ranked formal core row cannot be legacy carryover")
        core_rows.append(raw)

    if len(core_rows) != CORE_RACES:
        raise ValueError("formal core feed must contain exactly six races")
    ranks = [row.get("daily_rank") for row in core_rows]
    if any(type(rank) is not int for rank in ranks):
        raise ValueError("daily_rank must be an integer")
    if sorted(int(rank) for rank in ranks) != list(range(1, CORE_RACES + 1)):
        raise ValueError("formal core ranks must be 1..6 exactly")

    normalized_rows: list[dict[str, Any]] = []
    for row in sorted(core_rows, key=lambda item: int(item["daily_rank"])):
        rank = _strict_int(row["daily_rank"], "core row daily_rank")
        race_no = _strict_int(row["race_no"], "core row race_no")
        head_lane = _strict_int(row["head_lane"], "core row head_lane")
        course_lanes = _strict_int(row["course_usable_lanes"], "core row course_usable_lanes")
        if not 1 <= race_no <= 12:
            raise ValueError("core row race_no out of range")
        if not 1 <= head_lane <= 6:
            raise ValueError("core row head_lane out of range")
        if not 0 <= course_lanes <= 6:
            raise ValueError("core row course_usable_lanes out of range")
        _strict_bool(row["opponent_pressure_available"], "core row opponent_pressure_available")
        _strict_bool(row["motor2_complete"], "core row motor2_complete")
        if str(row["race_id"]).strip() == "" or str(row["venue_id"]).strip() == "":
            raise ValueError("core row race identity required")
        if _parse_iso_date(row["race_date"], "core row race_date") != target_date:
            raise ValueError("core row race_date mismatch")
        deadline = _parse_aware_datetime(row["deadline_at"], "core row deadline_at").astimezone(JST)
        if deadline.date() != target_date:
            raise ValueError("core row deadline date mismatch")
        expected_tier = "A" if rank <= 2 else ("B" if rank <= 4 else "C")
        if str(row["tier"]) != expected_tier:
            raise ValueError("core row tier/rank mismatch")

        raw_tickets = row.get("tickets")
        if not isinstance(raw_tickets, list):
            raise ValueError("core race tickets must be a list")
        core_tickets: list[dict[str, Any]] = []
        for ticket in raw_tickets:
            if not isinstance(ticket, Mapping):
                continue
            order = ticket.get("core_order")
            if type(order) is not int or order not in (1, 2):
                continue
            value = str(ticket.get("ticket") or "").strip()
            if not _valid_ticket(value):
                raise ValueError("valid exact-order trifecta core ticket required")
            core_tickets.append({"core_order": order, "ticket": value})
        core_tickets.sort(key=lambda item: item["core_order"])
        if len(core_tickets) != 2 or [item["core_order"] for item in core_tickets] != [1, 2]:
            raise ValueError("each formal core race must contain core_order 1 and 2 exactly")

        normalized = {key: row.get(key) for key in CORE_ROW_KEYS}
        normalized["tickets"] = core_tickets
        normalized_rows.append(normalized)

    return {
        "contract": V4_CONTRACT,
        "summary": {key: summary.get(key) for key in FORMAL_SUMMARY_KEYS},
        "policy": {key: policy.get(key) for key in FORMAL_POLICY_KEYS},
        "core_feed": normalized_rows,
    }


def canonical_core_payload_sha256(artifact: Mapping[str, Any]) -> str:
    payload = canonical_core_payload(artifact)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def capture_from_mapping(row: Mapping[str, Any]) -> Capture:
    _require_keys(
        row,
        (
            "target_date",
            "generated_at_jst",
            "canonical_payload_sha256",
            "prospective_evidence_eligible",
            "purchase_action",
            "promotion_allowed",
            "core_races",
            "core_tickets",
            "all_frozen_rows_pre_deadline",
        ),
        "capture metadata",
    )
    raw_date = row["target_date"]
    target = raw_date if isinstance(raw_date, date) and not isinstance(raw_date, datetime) else _parse_iso_date(raw_date, "target_date")
    generated = row["generated_at_jst"]
    if not isinstance(generated, datetime):
        generated = _parse_aware_datetime(generated, "generated_at_jst")
    else:
        generated = _parse_aware_datetime(generated, "generated_at_jst")
    return Capture(
        channel=str(row.get("channel") or ""),
        provider_run_id=str(row.get("provider_run_id") or ""),
        target_date=target,
        generated_at_jst=generated,
        canonical_payload_sha256=str(row["canonical_payload_sha256"]).lower(),
        prospective_evidence_eligible=_strict_bool(
            row["prospective_evidence_eligible"], "prospective_evidence_eligible"
        ),
        purchase_action=_strict_bool(row["purchase_action"], "purchase_action"),
        promotion_allowed=_strict_bool(row["promotion_allowed"], "promotion_allowed"),
        core_races=_strict_int(row["core_races"], "core_races"),
        core_tickets=_strict_int(row["core_tickets"], "core_tickets"),
        all_frozen_rows_pre_deadline=_strict_bool(
            row["all_frozen_rows_pre_deadline"], "all_frozen_rows_pre_deadline"
        ),
    )


def is_formally_valid(capture: Capture, *, target_date: date) -> bool:
    try:
        generated = _aware_jst(capture.generated_at_jst)
    except ValueError:
        return False
    cutoff = datetime.combine(target_date, SOURCE_CUTOFF, tzinfo=JST)
    return (
        capture.target_date == target_date
        and generated.date() == target_date
        and generated >= cutoff
        and _valid_sha256(capture.canonical_payload_sha256)
        and capture.prospective_evidence_eligible is True
        and capture.purchase_action is False
        and capture.promotion_allowed is False
        and type(capture.core_races) is int
        and capture.core_races == CORE_RACES
        and type(capture.core_tickets) is int
        and capture.core_tickets == CORE_TICKETS
        and capture.all_frozen_rows_pre_deadline is True
    )


def arbitrate_captures(
    captures: Iterable[Capture | Mapping[str, Any]],
    *,
    target_date: date,
) -> ArbitrationResult:
    """Choose the formal V4 artifact from already-produced capture metadata.

    Rules frozen before the 2026-09-16 primary:
    - invalid/ineligible captures are rejected, never rescued;
    - no valid capture => unavailable;
    - unique earliest valid generated_at_jst => formal artifact;
    - same earliest timestamp + same canonical payload SHA => duplicate copies;
    - same earliest timestamp + different SHA => fail closed as ambiguous;
    - later valid captures are diagnostic only;
    - provider/channel/run ID never breaks a tie.
    """
    normalized = [
        item if isinstance(item, Capture) else capture_from_mapping(item)
        for item in captures
    ]
    valid: list[Capture] = []
    rejected: list[Capture] = []
    for capture in normalized:
        (valid if is_formally_valid(capture, target_date=target_date) else rejected).append(capture)

    if not valid:
        return ArbitrationResult(
            classification="UNAVAILABLE_NO_VALID_CAPTURE",
            formal_capture=None,
            duplicate_copies=(),
            later_diagnostics=(),
            rejected_captures=tuple(rejected),
        )

    keyed = sorted(valid, key=lambda c: _aware_jst(c.generated_at_jst))
    earliest_time = _aware_jst(keyed[0].generated_at_jst)
    earliest = [c for c in keyed if _aware_jst(c.generated_at_jst) == earliest_time]
    later = [c for c in keyed if _aware_jst(c.generated_at_jst) > earliest_time]
    earliest_hashes = {c.canonical_payload_sha256 for c in earliest}

    if len(earliest_hashes) != 1:
        return ArbitrationResult(
            classification="UNAVAILABLE_AMBIGUOUS_DUPLICATE_CAPTURE",
            formal_capture=None,
            duplicate_copies=tuple(earliest),
            later_diagnostics=tuple(later),
            rejected_captures=tuple(rejected),
        )

    # All same-time earliest copies carry the same canonical payload. Pick a
    # deterministic metadata representative without implying evidence priority.
    representative = sorted(
        earliest,
        key=lambda c: (c.channel, c.provider_run_id),
    )[0]
    duplicates = tuple(c for c in earliest if c is not representative)
    return ArbitrationResult(
        classification="FORMAL_AVAILABLE",
        formal_capture=representative,
        duplicate_copies=duplicates,
        later_diagnostics=tuple(later),
        rejected_captures=tuple(rejected),
    )
