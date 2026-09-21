# -*- coding: utf-8 -*-
"""Pure parser contract for preserved BOAT RACE race-level active evidence.

Research-only. The parser never fetches official pages. It validates an exact
preserved raw venue race-index payload, binds one isolated race-row excerpt to
those bytes, and emits race-scoped ACTIVE evidence only when the selected race
row explicitly exposes a pre-deadline betting action.

This is a preregistration against synthetic contract fixtures. Real preserved
official raw fixtures remain required before any Production use.
"""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

CONTRACT = "candidate_discovery_v4_official_active_parse_input_v1"
ACTIVE = "active"
RACE_SCOPE = "race"
SOURCE_KIND = "venue_race_index"
JST = timezone(timedelta(hours=9))

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RACE_ID_RE = re.compile(r"^(\d{8})_(\d{2})_(\d{2})$")
DEADLINE_RE = re.compile(r"^(\d{2}):(\d{2})$")
SOURCE_URL_RE = re.compile(
    r"^https://www\.boatrace\.jp/owpc/pc/race/raceindex"
    r"\?hd=(\d{8})&jcd=(\d{2})$"
)

VENUE_IDS = {f"{idx:02d}" for idx in range(1, 25)}
BLOCKING_MARKERS = ("発売終了", "中止", "順延")


class V4OfficialActiveAvailabilityParserError(ValueError):
    pass


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4OfficialActiveAvailabilityParserError(
            f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4OfficialActiveAvailabilityParserError(
            f"{field} is not valid ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4OfficialActiveAvailabilityParserError(
            f"{field} must be timezone-aware"
        )
    return parsed


def _decode_raw(raw_b64: Any) -> bytes:
    if not isinstance(raw_b64, str) or not raw_b64:
        raise V4OfficialActiveAvailabilityParserError("raw_content_base64 missing")
    try:
        return base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise V4OfficialActiveAvailabilityParserError(
            "raw_content_base64 is invalid"
        ) from exc


def parse_active_evidence(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise V4OfficialActiveAvailabilityParserError("parse input must be an object")
    if data.get("contract") != CONTRACT:
        raise V4OfficialActiveAvailabilityParserError(
            "unexpected active parser input contract"
        )
    if data.get("source_kind") != SOURCE_KIND:
        raise V4OfficialActiveAvailabilityParserError("unsupported source_kind")

    target_date = data.get("target_date")
    if not isinstance(target_date, str):
        raise V4OfficialActiveAvailabilityParserError("target_date missing")
    try:
        target_day = date.fromisoformat(target_date)
    except ValueError as exc:
        raise V4OfficialActiveAvailabilityParserError(
            "target_date must be a valid ISO date"
        ) from exc
    target_compact = target_day.strftime("%Y%m%d")

    race_id = data.get("race_id")
    if not isinstance(race_id, str):
        raise V4OfficialActiveAvailabilityParserError("race_id missing")
    match = RACE_ID_RE.fullmatch(race_id)
    if match is None:
        raise V4OfficialActiveAvailabilityParserError("malformed race_id")
    race_date, venue_id, race_no_text = match.groups()
    if race_date != target_compact:
        raise V4OfficialActiveAvailabilityParserError("race_id target_date mismatch")
    if venue_id not in VENUE_IDS:
        raise V4OfficialActiveAvailabilityParserError("race_id venue_id out of range")
    race_no = int(race_no_text)
    if not (1 <= race_no <= 12):
        raise V4OfficialActiveAvailabilityParserError("race number out of range")

    deadline_hhmm = data.get("deadline_hhmm")
    if not isinstance(deadline_hhmm, str):
        raise V4OfficialActiveAvailabilityParserError("deadline_hhmm missing")
    deadline_match = DEADLINE_RE.fullmatch(deadline_hhmm)
    if deadline_match is None:
        raise V4OfficialActiveAvailabilityParserError("deadline_hhmm must be HH:MM")
    hour, minute = map(int, deadline_match.groups())
    if hour > 23 or minute > 59:
        raise V4OfficialActiveAvailabilityParserError("deadline_hhmm out of range")
    deadline_at = datetime.combine(
        target_day,
        time(hour=hour, minute=minute),
        tzinfo=JST,
    )

    observed_at = _aware_datetime(data.get("observed_at"), field="observed_at")
    observed_jst = observed_at.astimezone(JST)
    if observed_jst.date() != target_day:
        raise V4OfficialActiveAvailabilityParserError(
            "observed_at must fall on target_date in JST"
        )
    if observed_jst >= deadline_at:
        raise V4OfficialActiveAvailabilityParserError(
            "active evidence must be observed before selected race deadline"
        )

    source_updated_raw = data.get("source_updated_at")
    if source_updated_raw is not None:
        source_updated_at = _aware_datetime(
            source_updated_raw,
            field="source_updated_at",
        )
        if source_updated_at > observed_at:
            raise V4OfficialActiveAvailabilityParserError(
                "source_updated_at cannot be after observed_at"
            )

    source_url = data.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith(
        "https://www.boatrace.jp/"
    ):
        raise V4OfficialActiveAvailabilityParserError(
            "source_url must be BOAT RACE official"
        )
    url_match = SOURCE_URL_RE.fullmatch(source_url)
    if url_match is None:
        raise V4OfficialActiveAvailabilityParserError(
            "source_url must use canonical venue race-index URL"
        )
    url_date, url_venue = url_match.groups()
    if url_date != target_compact:
        raise V4OfficialActiveAvailabilityParserError("source_url target date mismatch")
    if url_venue != venue_id:
        raise V4OfficialActiveAvailabilityParserError("source_url venue mismatch")

    raw = _decode_raw(data.get("raw_content_base64"))
    digest = hashlib.sha256(raw).hexdigest()
    expected_digest = data.get("source_content_sha256")
    if (
        not isinstance(expected_digest, str)
        or SHA256_RE.fullmatch(expected_digest) is None
    ):
        raise V4OfficialActiveAvailabilityParserError(
            "source_content_sha256 must be lowercase 64-hex"
        )
    if digest != expected_digest:
        raise V4OfficialActiveAvailabilityParserError(
            "source content SHA-256 mismatch"
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise V4OfficialActiveAvailabilityParserError(
            "official raw payload must decode as UTF-8"
        ) from exc

    excerpt = data.get("race_row_excerpt_utf8")
    if not isinstance(excerpt, str) or not excerpt.strip():
        raise V4OfficialActiveAvailabilityParserError(
            "race_row_excerpt_utf8 missing"
        )
    if text.count(excerpt) != 1:
        raise V4OfficialActiveAvailabilityParserError(
            "race-row excerpt must occur exactly once in preserved raw payload"
        )

    visible = re.sub(r"<[^>]+>", " ", excerpt)
    visible = re.sub(r"\s+", "", visible)
    race_marker = f"{race_no}R"
    if race_marker not in visible:
        raise V4OfficialActiveAvailabilityParserError(
            "race-row excerpt does not identify selected race"
        )
    if deadline_hhmm not in visible:
        raise V4OfficialActiveAvailabilityParserError(
            "race-row excerpt deadline does not match frozen race deadline"
        )

    row_races = {int(value) for value in re.findall(r"(1[0-2]|[1-9])R", visible)}
    if row_races != {race_no}:
        raise V4OfficialActiveAvailabilityParserError(
            "race-row excerpt is not isolated to selected race"
        )

    for marker in BLOCKING_MARKERS:
        if marker in visible:
            raise V4OfficialActiveAvailabilityParserError(
                f"race-row excerpt contains blocking marker: {marker}"
            )
    if "投票" not in visible:
        raise V4OfficialActiveAvailabilityParserError(
            "race-row excerpt lacks explicit betting action"
        )

    evidence_id = data.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise V4OfficialActiveAvailabilityParserError("evidence_id missing")

    return {
        "contract": "candidate_discovery_v4_official_availability_evidence_v1",
        "target_date": target_date,
        "race_id": race_id,
        "venue_id": venue_id,
        "status": ACTIVE,
        "scope": RACE_SCOPE,
        "evidence_id": evidence_id,
        "source_kind": SOURCE_KIND,
        "deadline_hhmm": deadline_hhmm,
        "observed_at": data["observed_at"],
        "source_updated_at": source_updated_raw,
        "source_url": source_url,
        "source_content_sha256": digest,
        "matched_active_marker": "投票",
        "real_raw_fixture_required_before_production": True,
        "purchase_action": False,
    }
