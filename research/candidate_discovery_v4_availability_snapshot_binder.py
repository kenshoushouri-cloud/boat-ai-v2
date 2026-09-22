# -*- coding: utf-8 -*-
"""Pure binder from preserved pre-freeze raw availability to V4 snapshot.

No network, DB, Railway, LINE, result/payout, candidate generation, or purchase
surface exists here. The binder verifies the raw-capture manifest and exact
payload SHA-256 values, extracts one official venue/race row, delegates
normalization to the preregistered parsers, and emits the exact-six snapshot
consumed by the availability guard.
"""
from __future__ import annotations

import base64
import hashlib
import html
import re
from datetime import datetime
from typing import Any, Mapping

from research.candidate_discovery_v4_official_active_parser import (
    V4OfficialActiveAvailabilityParserError,
    parse_active_evidence,
)
from research.candidate_discovery_v4_official_availability_parser import (
    VENUE_NAMES,
    V4OfficialAvailabilityParserError,
    parse_unavailability_evidence,
)
from research.candidate_discovery_v4_pre_freeze_availability_capture import (
    MANIFEST_CONTRACT,
)

SNAPSHOT_CONTRACT = "candidate_discovery_v4_official_availability_snapshot_v1"
ARTIFACT_CONTRACT = "candidate_discovery_v4_main_feed_v1"
TR_RE = re.compile(r"(?is)<tr\b[^>]*>.*?</tr>")
TAG_RE = re.compile(r"(?is)<[^>]+>")
RANGE_CANCEL_RE = re.compile(r"(1[0-2]|[1-9])R以降中止")
VENUE_CANCEL_MARKERS = ("中止順延", "開催中止")


class V4AvailabilitySnapshotBinderError(ValueError):
    pass


def _aware(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4AvailabilitySnapshotBinderError(
            f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4AvailabilitySnapshotBinderError(
            f"{field} is not valid ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4AvailabilitySnapshotBinderError(
            f"{field} must be timezone-aware"
        )
    return parsed


def _visible(fragment: str) -> str:
    return re.sub(r"\s+", "", html.unescape(TAG_RE.sub(" ", fragment)))


def _formal_core(artifact: Any) -> tuple[str, datetime, list[dict[str, Any]]]:
    if not isinstance(artifact, dict) or artifact.get("contract") != ARTIFACT_CONTRACT:
        raise V4AvailabilitySnapshotBinderError("unexpected artifact contract")
    if artifact.get("prospective_evidence_eligible") is not True:
        raise V4AvailabilitySnapshotBinderError(
            "artifact is not eligible prospective evidence"
        )
    if artifact.get("purchase_action") is not False:
        raise V4AvailabilitySnapshotBinderError("artifact purchase_action must be false")
    provenance = artifact.get("freeze_provenance")
    if not isinstance(provenance, dict):
        raise V4AvailabilitySnapshotBinderError("freeze_provenance missing")
    target_date = provenance.get("target_date")
    if not isinstance(target_date, str):
        raise V4AvailabilitySnapshotBinderError("target_date missing")
    generated_at = _aware(artifact.get("generated_at"), field="artifact generated_at")

    rows = []
    for row in artifact.get("feed", []):
        if not isinstance(row, dict) or row.get("daily_rank") is None:
            continue
        tickets = [
            item
            for item in row.get("tickets", [])
            if isinstance(item, dict) and item.get("core_order") in (1, 2)
        ]
        if sorted(item["core_order"] for item in tickets) != [1, 2]:
            raise V4AvailabilitySnapshotBinderError(
                f"malformed formal core ticket orders: {row.get('race_id')}"
            )
        race_id = row.get("race_id")
        venue_id = row.get("venue_id")
        deadline = _aware(
            row.get("deadline_at"),
            field=f"core deadline_at {race_id}",
        )
        if not isinstance(race_id, str) or not isinstance(venue_id, str):
            raise V4AvailabilitySnapshotBinderError("core race identity missing")
        parts = race_id.split("_")
        if (
            len(parts) != 3
            or parts[0] != target_date.replace("-", "")
            or parts[1] != venue_id
            or not parts[2].isdigit()
            or not (1 <= int(parts[2]) <= 12)
        ):
            raise V4AvailabilitySnapshotBinderError(
                f"core race identity mismatch: {race_id}"
            )
        rows.append(
            {
                "race_id": race_id,
                "venue_id": venue_id,
                "race_no": int(parts[2]),
                "daily_rank": row["daily_rank"],
                "deadline_at": deadline,
                "deadline_hhmm": deadline.strftime("%H:%M"),
            }
        )
    if len(rows) != 6 or sorted(row["daily_rank"] for row in rows) != [1, 2, 3, 4, 5, 6]:
        raise V4AvailabilitySnapshotBinderError(
            "artifact formal core must be exactly six ranks 1..6"
        )
    return target_date, generated_at, sorted(rows, key=lambda row: row["daily_rank"])


def _load_manifest(
    manifest: Any,
    payloads: Mapping[str, bytes],
    *,
    target_date: str,
    generated_at: datetime,
) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("contract") != MANIFEST_CONTRACT:
        raise V4AvailabilitySnapshotBinderError("unexpected raw manifest contract")
    if manifest.get("target_date") != target_date:
        raise V4AvailabilitySnapshotBinderError("raw manifest target_date mismatch")
    completed = _aware(
        manifest.get("capture_completed_at_jst"),
        field="capture_completed_at_jst",
    )
    if completed > generated_at:
        raise V4AvailabilitySnapshotBinderError(
            "raw availability capture completed after artifact freeze"
        )
    if manifest.get("all_sources_pre_hard_stop") is not True:
        raise V4AvailabilitySnapshotBinderError(
            "raw manifest lacks pre-hard-stop provenance"
        )
    if manifest.get("result_endpoint_reads") != 0 or manifest.get("payout_endpoint_reads") != 0:
        raise V4AvailabilitySnapshotBinderError(
            "raw manifest result/payout read invariant violated"
        )
    if manifest.get("purchase_action") is not False:
        raise V4AvailabilitySnapshotBinderError(
            "raw manifest purchase_action must be false"
        )

    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise V4AvailabilitySnapshotBinderError("raw manifest sources missing")
    by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            raise V4AvailabilitySnapshotBinderError("raw source must be an object")
        source_id = source.get("source_id")
        filename = source.get("raw_filename")
        if not isinstance(source_id, str) or not source_id or source_id in by_id:
            raise V4AvailabilitySnapshotBinderError(
                f"invalid/duplicate raw source_id: {source_id}"
            )
        if not isinstance(filename, str) or filename not in payloads:
            raise V4AvailabilitySnapshotBinderError(
                f"raw payload missing: {source_id}"
            )
        raw = payloads[filename]
        if not isinstance(raw, bytes) or not raw:
            raise V4AvailabilitySnapshotBinderError(
                f"raw payload empty: {source_id}"
            )
        digest = hashlib.sha256(raw).hexdigest()
        if digest != source.get("source_content_sha256"):
            raise V4AvailabilitySnapshotBinderError(
                f"raw payload SHA-256 mismatch: {source_id}"
            )
        observed = _aware(
            source.get("observed_at"),
            field=f"source observed_at {source_id}",
        )
        if observed > generated_at:
            raise V4AvailabilitySnapshotBinderError(
                f"raw source observed after artifact freeze: {source_id}"
            )
        by_id[source_id] = {**source, "_raw": raw}
    return by_id


def _decode(raw: bytes, *, source_id: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise V4AvailabilitySnapshotBinderError(
            f"raw source is not UTF-8: {source_id}"
        ) from exc


def _venue_unavailable_excerpt(text: str, venue_id: str) -> str | None:
    venue_name = VENUE_NAMES[venue_id]
    candidates = []
    for fragment in TR_RE.findall(text):
        visible = _visible(fragment)
        if venue_name not in visible:
            continue
        if (
            any(marker in visible for marker in VENUE_CANCEL_MARKERS)
            or RANGE_CANCEL_RE.search(visible) is not None
        ):
            candidates.append(fragment)
    if not candidates:
        return None
    if len(candidates) != 1:
        raise V4AvailabilitySnapshotBinderError(
            f"ambiguous venue unavailable row: {venue_id}"
        )
    return candidates[0]


def _race_active_excerpt(
    text: str,
    *,
    race_no: int,
    deadline_hhmm: str,
) -> str:
    marker = f"{race_no}R"
    candidates = []
    for fragment in TR_RE.findall(text):
        visible = _visible(fragment)
        row_races = {
            int(value)
            for value in re.findall(r"(1[0-2]|[1-9])R", visible)
        }
        if row_races == {race_no} and marker in visible and deadline_hhmm in visible:
            candidates.append(fragment)
    if len(candidates) != 1:
        raise V4AvailabilitySnapshotBinderError(
            f"expected exactly one active race-row candidate: R{race_no} {deadline_hhmm}"
        )
    return candidates[0]


def bind_availability_snapshot(
    artifact: Any,
    manifest: Any,
    payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    target_date, generated_at, core = _formal_core(artifact)
    sources = _load_manifest(
        manifest,
        payloads,
        target_date=target_date,
        generated_at=generated_at,
    )

    day_source = sources.get("day-index")
    if day_source is None:
        raise V4AvailabilitySnapshotBinderError("day-index raw source missing")
    day_text = _decode(day_source["_raw"], source_id="day-index")

    used_sources: dict[str, dict[str, Any]] = {}
    races = []
    for row in core:
        race_id = row["race_id"]
        venue_id = row["venue_id"]

        unavailable_excerpt = _venue_unavailable_excerpt(day_text, venue_id)
        if unavailable_excerpt is not None:
            try:
                parsed = parse_unavailability_evidence(
                    {
                        "contract": "candidate_discovery_v4_official_unavailability_parse_input_v1",
                        "source_kind": "venue_day_index",
                        "target_date": target_date,
                        "race_id": race_id,
                        "observed_at": day_source["observed_at"],
                        "source_updated_at": None,
                        "source_url": day_source["source_url"],
                        "raw_content_base64": base64.b64encode(
                            day_source["_raw"]
                        ).decode("ascii"),
                        "source_content_sha256": day_source[
                            "source_content_sha256"
                        ],
                        "evidence_excerpt_utf8": unavailable_excerpt,
                        "evidence_id": "day-index",
                    }
                )
            except V4OfficialAvailabilityParserError as exc:
                raise V4AvailabilitySnapshotBinderError(
                    f"venue unavailable parser rejected {race_id}: {exc}"
                ) from exc
            used_sources["day-index"] = day_source
            races.append(
                {
                    "race_id": race_id,
                    "venue_id": venue_id,
                    "status": parsed["status"],
                    "scope": parsed["scope"],
                    "cancel_from_race_no": parsed["cancel_from_race_no"],
                    "evidence_id": "day-index",
                }
            )
            continue

        source_id = f"venue-{venue_id}-raceindex"
        venue_source = sources.get(source_id)
        if venue_source is None:
            raise V4AvailabilitySnapshotBinderError(
                f"venue raceindex raw source missing: {venue_id}"
            )
        venue_text = _decode(venue_source["_raw"], source_id=source_id)
        excerpt = _race_active_excerpt(
            venue_text,
            race_no=row["race_no"],
            deadline_hhmm=row["deadline_hhmm"],
        )
        try:
            parsed = parse_active_evidence(
                {
                    "contract": "candidate_discovery_v4_official_active_parse_input_v1",
                    "source_kind": "venue_race_index",
                    "target_date": target_date,
                    "race_id": race_id,
                    "deadline_hhmm": row["deadline_hhmm"],
                    "observed_at": venue_source["observed_at"],
                    "source_updated_at": None,
                    "source_url": venue_source["source_url"],
                    "raw_content_base64": base64.b64encode(
                        venue_source["_raw"]
                    ).decode("ascii"),
                    "source_content_sha256": venue_source[
                        "source_content_sha256"
                    ],
                    "race_row_excerpt_utf8": excerpt,
                    "evidence_id": source_id,
                }
            )
        except V4OfficialActiveAvailabilityParserError as exc:
            raise V4AvailabilitySnapshotBinderError(
                f"active parser rejected {race_id}: {exc}"
            ) from exc
        used_sources[source_id] = venue_source
        races.append(
            {
                "race_id": race_id,
                "venue_id": venue_id,
                "status": parsed["status"],
                "scope": parsed["scope"],
                "evidence_id": source_id,
                "evidence_binding_sha256": parsed[
                    "evidence_binding_sha256"
                ],
            }
        )

    evidence_sources = []
    for evidence_id in sorted(used_sources):
        source = used_sources[evidence_id]
        evidence_sources.append(
            {
                "evidence_id": evidence_id,
                "observed_at": source["observed_at"],
                "source_updated_at": None,
                "source_url": source["source_url"],
                "source_content_sha256": source["source_content_sha256"],
            }
        )

    return {
        "contract": SNAPSHOT_CONTRACT,
        "target_date": target_date,
        "evidence_sources": evidence_sources,
        "races": races,
        "race_universe_sha256": manifest.get("race_universe_sha256"),
        "purchase_action": False,
    }
