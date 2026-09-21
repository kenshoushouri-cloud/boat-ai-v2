# -*- coding: utf-8 -*-
"""Pure preregistered guard for pre-freeze official race availability.

Research-only. This module consumes already-captured data supplied by a caller.
It has no network, database, Railway, LINE, purchase, or Production mutation path.

The guard is intentionally non-constructive: it may block a formal artifact when
an already-selected core race was officially unavailable before the artifact
freeze, but it never removes/re-ranks/replaces candidates.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


ARTIFACT_CONTRACT = "candidate_discovery_v4_main_feed_v1"
SNAPSHOT_CONTRACT = "candidate_discovery_v4_official_availability_snapshot_v1"
ACTIVE = "active"
UNAVAILABLE = "cancelled_postponed"
ALLOWED_STATUSES = {ACTIVE, UNAVAILABLE}
RACE_SCOPE = "race"
VENUE_SCOPE = "venue"
VENUE_RANGE_SCOPE = "venue_race_range"
ALLOWED_SCOPES = {RACE_SCOPE, VENUE_SCOPE, VENUE_RANGE_SCOPE}


class V4AvailabilityGuardError(ValueError):
    pass


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4AvailabilityGuardError(f"{field} must be an ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4AvailabilityGuardError(f"{field} is not valid ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4AvailabilityGuardError(f"{field} must be timezone-aware")
    return parsed


def _formal_core(artifact: Any) -> list[dict[str, Any]]:
    if not isinstance(artifact, dict):
        raise V4AvailabilityGuardError("artifact must be an object")
    if artifact.get("contract") != ARTIFACT_CONTRACT:
        raise V4AvailabilityGuardError("unexpected artifact contract")
    if artifact.get("prospective_evidence_eligible") is not True:
        raise V4AvailabilityGuardError("artifact is not eligible prospective evidence")
    if artifact.get("purchase_action") is not False:
        raise V4AvailabilityGuardError("artifact purchase_action must be false")

    provenance = artifact.get("freeze_provenance")
    if not isinstance(provenance, dict):
        raise V4AvailabilityGuardError("artifact freeze_provenance missing")
    if provenance.get("all_frozen_rows_pre_deadline") is not True:
        raise V4AvailabilityGuardError("artifact lacks pre-deadline provenance")

    feed = artifact.get("feed")
    if not isinstance(feed, list):
        raise V4AvailabilityGuardError("artifact feed must be a list")

    core: list[dict[str, Any]] = []
    seen_races: set[str] = set()
    for row in feed:
        if not isinstance(row, dict):
            raise V4AvailabilityGuardError("feed row must be an object")
        core_tickets = [
            ticket
            for ticket in row.get("tickets", [])
            if isinstance(ticket, dict) and isinstance(ticket.get("core_order"), int)
        ]
        if not core_tickets:
            continue

        core_orders = sorted(ticket["core_order"] for ticket in core_tickets)
        if core_orders != [1, 2]:
            raise V4AvailabilityGuardError(
                f"core race must contain exact orders 1 and 2: {row.get('race_id')!r}"
            )

        race_id = row.get("race_id")
        venue_id = row.get("venue_id")
        daily_rank = row.get("daily_rank")
        if not isinstance(race_id, str) or not race_id:
            raise V4AvailabilityGuardError("core race_id missing")
        if race_id in seen_races:
            raise V4AvailabilityGuardError(f"duplicate core race_id: {race_id}")
        seen_races.add(race_id)
        if (
            not isinstance(venue_id, str)
            or len(venue_id) != 2
            or not venue_id.isdigit()
            or not (1 <= int(venue_id) <= 24)
        ):
            raise V4AvailabilityGuardError(f"invalid core venue_id: {venue_id!r}")
        if not isinstance(daily_rank, int) or isinstance(daily_rank, bool):
            raise V4AvailabilityGuardError(f"invalid core daily_rank: {daily_rank!r}")

        parts = race_id.split("_")
        if (
            len(parts) != 3
            or len(parts[0]) != 8
            or len(parts[2]) != 2
            or not all(part.isdigit() for part in parts)
            or not (1 <= int(parts[2]) <= 12)
        ):
            raise V4AvailabilityGuardError(f"malformed core race_id: {race_id!r}")
        if parts[1] != venue_id:
            raise V4AvailabilityGuardError(
                f"core race_id venue mismatch: {race_id} vs {venue_id}"
            )

        core.append(
            {
                "race_id": race_id,
                "venue_id": venue_id,
                "daily_rank": daily_rank,
            }
        )

    if len(core) != 6:
        raise V4AvailabilityGuardError(f"formal core must contain exactly 6 races: {len(core)}")
    ranks = sorted(row["daily_rank"] for row in core)
    if ranks != [1, 2, 3, 4, 5, 6]:
        raise V4AvailabilityGuardError(f"formal core daily_rank must be exactly 1..6: {ranks}")
    return sorted(core, key=lambda row: row["daily_rank"])


def _load_evidence_sources(snapshot: dict[str, Any], *, generated_at: datetime) -> dict[str, dict[str, Any]]:
    raw_sources = snapshot.get("evidence_sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise V4AvailabilityGuardError("snapshot evidence_sources must be a non-empty list")

    sources: dict[str, dict[str, Any]] = {}
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise V4AvailabilityGuardError("availability evidence source must be an object")
        evidence_id = raw.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise V4AvailabilityGuardError("availability evidence_id missing")
        if evidence_id in sources:
            raise V4AvailabilityGuardError(f"duplicate availability evidence_id: {evidence_id}")

        observed_at = _aware_datetime(
            raw.get("observed_at"),
            field=f"evidence {evidence_id} observed_at",
        )
        if observed_at > generated_at:
            raise V4AvailabilityGuardError(
                f"availability evidence observed after artifact freeze: {evidence_id}"
            )

        source_updated_raw = raw.get("source_updated_at")
        source_updated_at = None
        if source_updated_raw is not None:
            source_updated_at = _aware_datetime(
                source_updated_raw,
                field=f"evidence {evidence_id} source_updated_at",
            )
            if source_updated_at > observed_at:
                raise V4AvailabilityGuardError(
                    f"source update time is after evidence observation: {evidence_id}"
                )

        source_url = raw.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://www.boatrace.jp/"):
            raise V4AvailabilityGuardError(
                f"availability source must be BOAT RACE official: {evidence_id}"
            )

        source_content_sha256 = raw.get("source_content_sha256")
        if (
            not isinstance(source_content_sha256, str)
            or len(source_content_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in source_content_sha256)
        ):
            raise V4AvailabilityGuardError(
                f"availability source_content_sha256 must be lowercase SHA-256 hex: {evidence_id}"
            )

        sources[evidence_id] = {
            "evidence_id": evidence_id,
            "observed_at": raw["observed_at"],
            "source_updated_at": source_updated_raw,
            "source_url": source_url,
            "source_content_sha256": source_content_sha256,
        }

    return sources


def evaluate_availability_guard(artifact: Any, snapshot: Any) -> dict[str, Any]:
    """Evaluate caller-supplied pre-freeze official availability evidence.

    This function never fetches evidence and never produces replacement
    candidates. Any unavailable selected core race blocks the artifact.
    """
    core = _formal_core(artifact)
    provenance = artifact["freeze_provenance"]
    target_date = provenance.get("target_date")
    if not isinstance(target_date, str) or not target_date:
        raise V4AvailabilityGuardError("artifact target_date missing")
    try:
        target_day = date.fromisoformat(target_date)
    except ValueError as exc:
        raise V4AvailabilityGuardError("artifact target_date is not valid ISO date") from exc

    expected_race_prefix = target_day.strftime("%Y%m%d") + "_"
    for row in core:
        if not row["race_id"].startswith(expected_race_prefix):
            raise V4AvailabilityGuardError(
                f"core race_id target_date mismatch: {row['race_id']}"
            )

    generated_at = _aware_datetime(artifact.get("generated_at"), field="artifact generated_at")

    if not isinstance(snapshot, dict):
        raise V4AvailabilityGuardError("snapshot must be an object")
    if snapshot.get("contract") != SNAPSHOT_CONTRACT:
        raise V4AvailabilityGuardError("unexpected availability snapshot contract")
    if snapshot.get("target_date") != target_date:
        raise V4AvailabilityGuardError("availability target_date mismatch")

    evidence_sources = _load_evidence_sources(snapshot, generated_at=generated_at)

    races = snapshot.get("races")
    if not isinstance(races, list):
        raise V4AvailabilityGuardError("snapshot races must be a list")

    by_race: dict[str, dict[str, str]] = {}
    for raw in races:
        if not isinstance(raw, dict):
            raise V4AvailabilityGuardError("availability race row must be an object")
        race_id = raw.get("race_id")
        venue_id = raw.get("venue_id")
        status = raw.get("status")
        scope = raw.get("scope")
        cancel_from_race_no = raw.get("cancel_from_race_no")
        evidence_id = raw.get("evidence_id")
        if not isinstance(race_id, str) or not race_id:
            raise V4AvailabilityGuardError(f"invalid availability race_id: {race_id!r}")
        if race_id in by_race:
            raise V4AvailabilityGuardError(f"duplicate availability race_id: {race_id}")
        if not isinstance(venue_id, str) or len(venue_id) != 2 or not venue_id.isdigit():
            raise V4AvailabilityGuardError(f"invalid availability venue_id: {venue_id!r}")
        if status not in ALLOWED_STATUSES:
            raise V4AvailabilityGuardError(f"unknown availability status: {status!r}")
        if scope not in ALLOWED_SCOPES:
            raise V4AvailabilityGuardError(f"unknown availability scope: {scope!r}")
        if not isinstance(evidence_id, str) or evidence_id not in evidence_sources:
            raise V4AvailabilityGuardError(
                f"availability evidence_id missing or unknown for race: {race_id}"
            )
        if status == ACTIVE and scope != RACE_SCOPE:
            raise V4AvailabilityGuardError(
                f"non-race active status is insufficient for core race: {race_id}"
            )
        if scope == VENUE_RANGE_SCOPE:
            if status != UNAVAILABLE:
                raise V4AvailabilityGuardError(
                    f"venue-range evidence must be unavailable: {race_id}"
                )
            if (
                not isinstance(cancel_from_race_no, int)
                or isinstance(cancel_from_race_no, bool)
                or not (1 <= cancel_from_race_no <= 12)
            ):
                raise V4AvailabilityGuardError(
                    f"invalid cancel_from_race_no for venue-range evidence: {race_id}"
                )
            race_no = int(race_id.split("_")[2])
            if race_no < cancel_from_race_no:
                raise V4AvailabilityGuardError(
                    f"venue-range unavailable evidence does not cover core race: {race_id}"
                )
        elif cancel_from_race_no is not None:
            raise V4AvailabilityGuardError(
                f"cancel_from_race_no only valid for venue-range evidence: {race_id}"
            )
        by_race[race_id] = {
            "venue_id": venue_id,
            "status": status,
            "scope": scope,
            "evidence_id": evidence_id,
            "cancel_from_race_no": cancel_from_race_no,
        }

    core_ids = {row["race_id"] for row in core}
    missing_races = sorted(core_ids - set(by_race))
    if missing_races:
        raise V4AvailabilityGuardError(
            "availability snapshot missing core race(s): " + ",".join(missing_races)
        )

    for row in core:
        observed = by_race[row["race_id"]]
        if observed["venue_id"] != row["venue_id"]:
            raise V4AvailabilityGuardError(
                f"availability venue mismatch for core race: {row['race_id']}"
            )

    # Venue-wide unavailability cannot coexist with an active selected race at
    # that same venue in one snapshot.
    for venue_id in {row["venue_id"] for row in core}:
        selected = [by_race[row["race_id"]] for row in core if row["venue_id"] == venue_id]
        if any(item["scope"] == VENUE_SCOPE and item["status"] == UNAVAILABLE for item in selected):
            if any(item["status"] != UNAVAILABLE for item in selected):
                raise V4AvailabilityGuardError(
                    f"inconsistent venue-level unavailable evidence: {venue_id}"
                )

    # A race-scoped positive source must not be reused to assert another core
    # race. Reuse is allowed only for venue-wide unavailable evidence at the
    # same venue.
    evidence_usage: dict[str, list[dict[str, str]]] = {}
    for row in core:
        observed = by_race[row["race_id"]]
        evidence_usage.setdefault(observed["evidence_id"], []).append(
            {
                "race_id": row["race_id"],
                "venue_id": row["venue_id"],
                "status": observed["status"],
                "scope": observed["scope"],
                "cancel_from_race_no": observed.get("cancel_from_race_no"),
            }
        )
    for evidence_id, used_by in evidence_usage.items():
        if len(used_by) <= 1:
            continue
        same_venue = len({item["venue_id"] for item in used_by}) == 1
        venue_unavailable_only = all(
            item["scope"] == VENUE_SCOPE and item["status"] == UNAVAILABLE
            for item in used_by
        )
        venue_range_unavailable_only = all(
            item["scope"] == VENUE_RANGE_SCOPE and item["status"] == UNAVAILABLE
            for item in used_by
        )
        same_range = len({item.get("cancel_from_race_no") for item in used_by}) == 1
        if not (
            same_venue
            and (
                venue_unavailable_only
                or (venue_range_unavailable_only and same_range)
            )
        ):
            raise V4AvailabilityGuardError(
                f"evidence source reused across incompatible core races: {evidence_id}"
            )

    blocked = [
        {
            "race_id": row["race_id"],
            "venue_id": row["venue_id"],
            "daily_rank": row["daily_rank"],
            "status": by_race[row["race_id"]]["status"],
            "scope": by_race[row["race_id"]]["scope"],
            "cancel_from_race_no": by_race[row["race_id"]].get("cancel_from_race_no"),
            "evidence_id": by_race[row["race_id"]]["evidence_id"],
        }
        for row in core
        if by_race[row["race_id"]]["status"] != ACTIVE
    ]

    core_evidence = []
    for row in core:
        observed = by_race[row["race_id"]]
        source = evidence_sources[observed["evidence_id"]]
        core_evidence.append(
            {
                "race_id": row["race_id"],
                "venue_id": row["venue_id"],
                "status": observed["status"],
                "scope": observed["scope"],
                **source,
            }
        )

    return {
        "contract": "candidate_discovery_v4_pre_freeze_availability_guard_v1",
        "target_date": target_date,
        "formal_core_races": len(core),
        "evidence_source_count": len(evidence_sources),
        "core_evidence": core_evidence,
        "eligible_under_guard": not blocked,
        "blocked_core_races": blocked,
        "replacement_candidates_generated": False,
        "ranking_changed": False,
        "purchase_action": False,
        "decision": "PASS_ACTIVE_CORE" if not blocked else "BLOCK_PRE_FREEZE_UNAVAILABLE_CORE",
    }
