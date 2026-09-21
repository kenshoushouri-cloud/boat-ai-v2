# -*- coding: utf-8 -*-
"""Pure parser contract for preserved BOAT RACE unavailability evidence.

Research-only. This parser never fetches official pages. It accepts an exact
preserved raw payload (base64), verifies its SHA-256, binds a human-readable
evidence excerpt back to those bytes, and emits only BLOCKING unavailable
evidence. Positive/active evidence is intentionally unsupported in v1.
"""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime
from typing import Any

CONTRACT = "candidate_discovery_v4_official_unavailability_parse_input_v1"
VENUE_SCOPE = "venue"
VENUE_RANGE_SCOPE = "venue_race_range"
RACE_SCOPE = "race"
UNAVAILABLE = "cancelled_postponed"
VENUE_INDEX = "venue_day_index"
RACE_PAGE = "race_page"
ALLOWED_SOURCE_KINDS = {VENUE_INDEX, RACE_PAGE}

VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RACE_ID_RE = re.compile(r"^(\d{8})_(\d{2})_(\d{2})$")
VENUE_INDEX_URL_RE = re.compile(
    r"^https://www\.boatrace\.jp/owpc/pc/race/index\?hd=(\d{8})$"
)
RACE_PAGE_URL_RE = re.compile(
    r"^https://www\.boatrace\.jp/owpc/pc/race/racelist"
    r"\?hd=(\d{8})&jcd=(\d{2})&rno=(\d{1,2})$"
)


class V4OfficialAvailabilityParserError(ValueError):
    pass


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise V4OfficialAvailabilityParserError(f"{field} must be an ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise V4OfficialAvailabilityParserError(f"{field} is not valid ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise V4OfficialAvailabilityParserError(f"{field} must be timezone-aware")
    return parsed


def _decode_raw(raw_b64: Any) -> bytes:
    if not isinstance(raw_b64, str) or not raw_b64:
        raise V4OfficialAvailabilityParserError("raw_content_base64 missing")
    try:
        return base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise V4OfficialAvailabilityParserError("raw_content_base64 is invalid") from exc


def parse_unavailability_evidence(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise V4OfficialAvailabilityParserError("parse input must be an object")
    if data.get("contract") != CONTRACT:
        raise V4OfficialAvailabilityParserError("unexpected parser input contract")

    source_kind = data.get("source_kind")
    if source_kind not in ALLOWED_SOURCE_KINDS:
        raise V4OfficialAvailabilityParserError(f"unsupported source_kind: {source_kind!r}")

    target_date = data.get("target_date")
    if not isinstance(target_date, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date) is None:
        raise V4OfficialAvailabilityParserError("target_date must be YYYY-MM-DD")
    target_compact = target_date.replace("-", "")

    race_id = data.get("race_id")
    if not isinstance(race_id, str):
        raise V4OfficialAvailabilityParserError("race_id missing")
    m = RACE_ID_RE.fullmatch(race_id)
    if m is None:
        raise V4OfficialAvailabilityParserError("malformed race_id")
    race_date, venue_id, race_no = m.groups()
    if race_date != target_compact:
        raise V4OfficialAvailabilityParserError("race_id target_date mismatch")
    if venue_id not in VENUE_NAMES:
        raise V4OfficialAvailabilityParserError("race_id venue_id out of range")
    if not (1 <= int(race_no) <= 12):
        raise V4OfficialAvailabilityParserError("race number out of range")

    observed_at = _aware_datetime(data.get("observed_at"), field="observed_at")
    source_updated_raw = data.get("source_updated_at")
    source_updated_at = None
    if source_updated_raw is not None:
        source_updated_at = _aware_datetime(source_updated_raw, field="source_updated_at")
        if source_updated_at > observed_at:
            raise V4OfficialAvailabilityParserError(
                "source_updated_at cannot be after observed_at"
            )

    source_url = data.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("https://www.boatrace.jp/"):
        raise V4OfficialAvailabilityParserError("source_url must be BOAT RACE official")

    if source_kind == VENUE_INDEX:
        source_match = VENUE_INDEX_URL_RE.fullmatch(source_url)
        if source_match is None:
            raise V4OfficialAvailabilityParserError(
                "venue_day_index source_url must use canonical official URL"
            )
        if source_match.group(1) != target_compact:
            raise V4OfficialAvailabilityParserError("source_url target date mismatch")
        scope = VENUE_SCOPE
    else:
        source_match = RACE_PAGE_URL_RE.fullmatch(source_url)
        if source_match is None:
            raise V4OfficialAvailabilityParserError(
                "race_page source_url must use canonical official URL"
            )
        url_date, url_venue, url_race_no = source_match.groups()
        if url_date != target_compact:
            raise V4OfficialAvailabilityParserError("source_url target date mismatch")
        if url_venue != venue_id:
            raise V4OfficialAvailabilityParserError("race_page venue mismatch")
        if int(url_race_no) != int(race_no):
            raise V4OfficialAvailabilityParserError("race_page race number mismatch")
        scope = RACE_SCOPE

    raw = _decode_raw(data.get("raw_content_base64"))
    digest = hashlib.sha256(raw).hexdigest()
    expected_digest = data.get("source_content_sha256")
    if not isinstance(expected_digest, str) or SHA256_RE.fullmatch(expected_digest) is None:
        raise V4OfficialAvailabilityParserError(
            "source_content_sha256 must be lowercase 64-hex"
        )
    if digest != expected_digest:
        raise V4OfficialAvailabilityParserError("source content SHA-256 mismatch")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise V4OfficialAvailabilityParserError("official raw payload must decode as UTF-8") from exc

    excerpt = data.get("evidence_excerpt_utf8")
    if not isinstance(excerpt, str) or not excerpt.strip():
        raise V4OfficialAvailabilityParserError("evidence_excerpt_utf8 missing")
    if text.count(excerpt) != 1:
        raise V4OfficialAvailabilityParserError(
            "evidence excerpt must occur exactly once in preserved raw payload"
        )

    compact_excerpt = re.sub(r"\s+", "", excerpt)
    venue_name = VENUE_NAMES[venue_id]

    cancel_from_race_no = None
    if source_kind == VENUE_INDEX:
        if venue_name not in compact_excerpt:
            raise V4OfficialAvailabilityParserError(
                "venue-day excerpt does not identify expected venue"
            )
        other_venues = sorted(
            name
            for other_id, name in VENUE_NAMES.items()
            if other_id != venue_id and name in compact_excerpt
        )
        if other_venues:
            raise V4OfficialAvailabilityParserError(
                "venue-day excerpt is not isolated to expected venue: "
                + ",".join(other_venues)
            )
        range_match = re.search(r"(1[0-2]|[1-9])R以降中止", compact_excerpt)
        if range_match is not None:
            cancel_from_race_no = int(range_match.group(1))
            if int(race_no) < cancel_from_race_no:
                raise V4OfficialAvailabilityParserError(
                    "venue race-range unavailable marker does not cover selected race"
                )
            scope = VENUE_RANGE_SCOPE
            marker = range_match.group(0)
        elif "中止順延" in compact_excerpt or "開催中止" in compact_excerpt:
            marker = "中止順延" if "中止順延" in compact_excerpt else "開催中止"
        else:
            raise V4OfficialAvailabilityParserError(
                "no supported venue unavailable marker"
            )
    else:
        if "レース中止" not in compact_excerpt:
            raise V4OfficialAvailabilityParserError(
                "no supported race-level unavailable marker"
            )
        marker = "レース中止"

    evidence_id = data.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise V4OfficialAvailabilityParserError("evidence_id missing")

    return {
        "contract": "candidate_discovery_v4_official_availability_evidence_v1",
        "target_date": target_date,
        "race_id": race_id,
        "venue_id": venue_id,
        "status": UNAVAILABLE,
        "scope": scope,
        "cancel_from_race_no": cancel_from_race_no,
        "evidence_id": evidence_id,
        "source_kind": source_kind,
        "observed_at": data["observed_at"],
        "source_updated_at": source_updated_raw,
        "source_url": source_url,
        "source_content_sha256": digest,
        "matched_unavailable_marker": marker,
        "positive_active_evidence_supported": False,
        "purchase_action": False,
    }
