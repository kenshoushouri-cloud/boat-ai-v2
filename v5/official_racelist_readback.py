# -*- coding: utf-8 -*-
"""V5 mainline racelist binder: verified-byte READBACK -> six entrant candidates.

The only input to this binder is an explicit DB read-connection and independently
supplied race/cutoff clocks. It SELECTs the original frozen bytes from the
V5 first-write table, checks URL identity, byte digest and acquisition time,
and parses strict structured HTML. No caller-provided "verified racers" flags
are trusted. This NEVER proves the official site's authenticity, true earliest
observation, append-only owner privileges, or all-six ACTIVE at decision time.
No network, insert, SQL update, V4 or BUY actions.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from v5.official_first_write_storage import READ_FIRST, _identity
from v5.official_http_receipt import (
    MAX_PAGE_BYTES, MAX_REQUEST_SECONDS, _aware_dt, _source_from_exact_url,
    UnverifiedCapture,
)

READ_COLUMNS = (
    "resource_key", "source_kind", "race_id", "source_url",
    "request_started_at", "response_completed_at", "raw_bytes", "raw_sha256",
)
CLASS = re.compile(r"(?<!\d)([1-9]\d{3})\s*/\s*(A1|A2|B1|B2)(?!\w)")
LANE = re.compile(r"[1-6]")
CANCEL_MARKERS = ("欠場", "出走取消", "出場取消", "取消", "帰郷", "不参加")
MAX_ROSTER_AGE_SECONDS = 24 * 60 * 60


class RacelistNotVerified(ValueError):
    """Strict source/readback/roster verification failed."""


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(v or ""))).strip()


def _extract_six_entrant_candidates(original_html: bytes) -> list[dict[str, Any]]:
    try:
        soup = BeautifulSoup(original_html.decode("utf-8", errors="strict"), "html.parser")
    except (UnicodeError, TypeError) as exc:
        raise RacelistNotVerified("RACELIST_ENCODING_UNVERIFIED") from exc
    # Only an identifiable official-style entry table is usable. Never scan
    # generic text and mistake a secondary odds/results table for the roster.
    tables = []
    for table in soup.find_all("table"):
        labels = [_norm(x.get_text(" ", strip=True)) for x in table.find_all("th")]
        if any("登録番号/級別" in label for label in labels):
            tables.append(table)
    if len(tables) != 1:
        raise RacelistNotVerified("RACELIST_STRUCTURED_TABLE_MISSING_OR_AMBIGUOUS")

    found: list[dict[str, Any]] = []
    candidate_lanes = []
    for tr in tables[0].find_all("tr"):
        cells = [
            _norm(x.get_text(" ", strip=True))
            for x in tr.find_all(["td", "th"], recursive=False)
        ]
        lane_text = next((c for c in cells[:3] if LANE.fullmatch(c)), None)
        if lane_text is None:
            continue
        lane = int(lane_text)
        candidate_lanes.append(lane)
        full_text = _norm(" ".join(cells))
        if any(marker in full_text for marker in CANCEL_MARKERS):
            raise RacelistNotVerified("RACELIST_CANCEL_MARKER_PRESENT")
        matches = CLASS.findall(full_text)
        if len(matches) != 1:
            raise RacelistNotVerified("RACELIST_REGISTRATION_UNVERIFIED")
        racer_text, racer_class = matches[0]
        found.append({
            "lane": lane,
            "racer_number": int(racer_text),
            "racer_class": racer_class,
            "no_cancellation_marker": True,
            # Textual absence of a cancellation mark is NOT an independent
            # official confirmation of the athlete's actual start status.
            "active_verified": False,
        })
    if len(candidate_lanes) != 6 or sorted(candidate_lanes) != list(range(1, 7)):
        raise RacelistNotVerified("RACELIST_NOT_SIX_UNIQUE_LANES")
    if len(found) != 6 or len({x["racer_number"] for x in found}) != 6:
        raise RacelistNotVerified("RACELIST_DUPLICATE_OR_MISSING_RACERS")
    return sorted(found, key=lambda row: row["lane"])


def bind_first_write_racelist(
    connection: Any,
    *,
    expected_race_id: str,
    beforeinfo_captured_at: Any,
    prediction_cutoff_at: Any,
) -> dict[str, Any]:
    """Read ONLY original bytea row and extract an independently checked roster.

    Explicit DB connection can be read-only; the binder issues precisely the
    constant SELECT in READ_FIRST, not DDL, UPDATE, or inserted assertions.
    This result is *not* a substitute for proving the DB row was the actual
    first official HTTP observation. A later operational pilot must supply
    externally verified collector log/source, read-only role and timing.
    """
    if not isinstance(expected_race_id, str) or not re.fullmatch(
        r"20\d{6}_(?:0[1-9]|1[0-9]|2[0-4])_(?:0[1-9]|1[0-2])",
        expected_race_id,
    ):
        raise RacelistNotVerified("INVALID_RACE_ID")
    if connection is None or not callable(getattr(connection, "cursor", None)):
        raise RacelistNotVerified("EXPLICIT_READ_CONNECTION_REQUIRED")
    try:
        cutoff = _aware_dt(prediction_cutoff_at)
        beforeinfo_at = _aware_dt(beforeinfo_captured_at)
    except (UnverifiedCapture, TypeError, ValueError) as exc:
        raise RacelistNotVerified("UNVERIFIED_DECISION_CLOCK") from exc
    if beforeinfo_at >= cutoff:
        raise RacelistNotVerified("BEFOREINFO_NOT_BEFORE_CUTOFF")
    key = "official_racelist:" + expected_race_id
    try:
        with connection.cursor() as cursor:
            cursor.execute(READ_FIRST, (key,))
            raw_row = cursor.fetchone()
    except Exception as exc:
        raise RacelistNotVerified("RACELIST_DB_READ_FAILED") from exc
    if raw_row is None:
        raise RacelistNotVerified("RACELIST_FIRST_WRITE_NOT_FOUND")
    if isinstance(raw_row, Mapping):
        row = raw_row
    elif isinstance(raw_row, (tuple, list)) and len(raw_row) == len(READ_COLUMNS):
        row = dict(zip(READ_COLUMNS, raw_row))
    else:
        raise RacelistNotVerified("RACELIST_READBACK_SHAPE_UNVERIFIED")
    url = row.get("source_url")
    try:
        kind, max_bytes = _source_from_exact_url(url)
        expected_key, url_race = _identity(kind, url)
        start = _aware_dt(row.get("request_started_at"))
        captured = _aware_dt(row.get("response_completed_at"))
    except (UnverifiedCapture, ValueError, TypeError) as exc:
        raise RacelistNotVerified("RACELIST_SOURCE_OR_TIME_UNVERIFIED") from exc
    if (kind != "official_racelist" or expected_key != key or url_race != expected_race_id
            or row.get("resource_key") != key
            or row.get("source_kind") != kind
            or row.get("race_id") != expected_race_id):
        raise RacelistNotVerified("RACELIST_SOURCE_IDENTITY_MISMATCH")
    if not (start <= captured <= beforeinfo_at < cutoff):
        raise RacelistNotVerified("RACELIST_OBSERVATION_AFTER_CUTOFF")
    duration = (captured - start).total_seconds()
    age = (beforeinfo_at - captured).total_seconds()
    if not (0 <= duration <= MAX_REQUEST_SECONDS and 0 <= age <= MAX_ROSTER_AGE_SECONDS):
        raise RacelistNotVerified("RACELIST_CAPTURE_TIME_OUT_OF_BOUNDS")

    raw_bytes = row.get("raw_bytes")
    if not isinstance(raw_bytes, (bytes, memoryview, bytearray)):
        raise RacelistNotVerified("RACELIST_ORIGINAL_BYTES_MISSING")
    raw = bytes(raw_bytes)
    if not (0 < len(raw) <= min(MAX_PAGE_BYTES, max_bytes)):
        raise RacelistNotVerified("RACELIST_ORIGINAL_BYTES_SIZE_INVALID")
    digest = hashlib.sha256(raw).hexdigest()
    if row.get("raw_sha256") != digest:
        raise RacelistNotVerified("RACELIST_ORIGINAL_SHA256_MISMATCH")
    entries = _extract_six_entrant_candidates(raw)
    return {
        "contract": "V5_RACELIST_ORIGINAL_READBACK_V1",
        "source": "official_racelist",
        "race_id": expected_race_id,
        "source_url": url,
        "captured_at": captured.isoformat(),
        "raw_sha256": digest,
        "entries": entries,
        "readback_consistent": True,
        "first_write_confirmed": False,
        "all_active_verified": False,
        "forward_eligible": False,
        "limitations": (
            "Original stored bytes and digest matched a restricted SELECT; "
            "real source authenticity, first-on-the-internet observation and "
            "all six active start confirmations remain unproven."
        ),
    }
