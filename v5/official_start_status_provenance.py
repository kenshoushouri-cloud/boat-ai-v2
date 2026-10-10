# -*- coding: utf-8 -*-
"""V5 mainline: conservative predeadline official start-status EVIDENCE classifier.

Independent immutable-source READBACK of the racelist must happen upstream via
bind_first_write_racelist(). This pure function checks original beforeinfo
response bytes/hash/time against that readback and looks for EXPLICIT
withdrawal/cancellation in each structured boat row. It does NOT invent a
positive "all six active" source when the official page lacks one.

Observed exhibition participation != confirmed race start. Caller booleans,
post-race K/results, mutable historical snapshots and absence of cancellation
markers never approve BEFOREINFO first-write, Forward, LINE or BUY.
No HTTP/DB writes or production integration.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import unicodedata
from collections.abc import Mapping

from bs4 import BeautifulSoup

from historical_beforeinfo_parser_v3 import (
    EXHIBITION_STATUS_COMPLETE,
    inspect_exhibition_time_page,
    _direct_cells,
    _lane_from_cells,
)
from v5.official_http_receipt import (
    MAX_REQUEST_SECONDS, _aware_dt, _source_from_exact_url, UnverifiedCapture,
)
from v5.official_first_write_storage import _identity

WITHDRAWAL_MARKERS = ("欠場", "出走取消", "出場取消", "取消", "帰郷", "不参加")
WINDOW_MIN, WINDOW_MAX = 8.0, 15.0


def _normalized(text: str) -> str:
    """Normalize full-width and intermittent Japanese whitespace."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def classify_predeadline_start_status(
    *,
    beforeinfo_receipt: Mapping | None,
    racelist_readback: Mapping | None,
    expected_race_id: str,
    official_deadline_at,
    prediction_cutoff_at,
) -> dict:
    """Return evidence classification only; NEVER a confirmed-start approval.

    No independent official positive start-state field was established from
    current repository source evidence. A future reviewed source contract
    will be needed before changing this all-active hold.
    """
    def denied(reason: str):
        return {
            "status": "UNVERIFIED_SOURCE",
            "reason": reason,
            "all_six_active_confirmed": False,
            "beforeinfo_prewrite_eligible": False,
            "forward_eligible": False,
        }

    receipt = beforeinfo_receipt
    roster = racelist_readback
    if (not isinstance(receipt, Mapping)
            or receipt.get("contract") != "V5_OFFICIAL_HTTP_CAPTURE_PROPOSAL_V1"
            or receipt.get("source") != "official_beforeinfo"
            or receipt.get("first_observed_at") is not None
            or receipt.get("first_write_confirmed") is not False
            or receipt.get("forward_eligible") is not False):
        return denied("BEFOREINFO_CAPTURE_PROPOSAL_UNVERIFIED")
    if (not isinstance(roster, Mapping)
            or roster.get("contract") != "V5_RACELIST_ORIGINAL_READBACK_V1"
            or roster.get("source") != "official_racelist"
            or roster.get("readback_consistent") is not True
            or roster.get("race_id") != expected_race_id
            or roster.get("all_active_verified") is not False
            or roster.get("first_write_confirmed") is not False
            or roster.get("forward_eligible") is not False):
        return denied("RACELIST_ORIGINAL_READBACK_UNVERIFIED")
    try:
        before_kind, max_bytes = _source_from_exact_url(receipt["source_url"])
        _, before_race = _identity(before_kind, receipt["source_url"])
        roster_kind, _ = _source_from_exact_url(roster["source_url"])
        _, roster_race = _identity(roster_kind, roster["source_url"])
        begin = _aware_dt(receipt["request_started_at"])
        observed = _aware_dt(receipt["response_completed_at"])
        roster_observed = _aware_dt(roster["captured_at"])
        cutoff = _aware_dt(prediction_cutoff_at)
        deadline = _aware_dt(official_deadline_at)
    except (UnverifiedCapture, TypeError, ValueError, KeyError):
        return denied("SOURCE_URL_OR_CLOCK_UNVERIFIED")
    if (before_kind != "official_beforeinfo"
            or roster_kind != "official_racelist"
            or not expected_race_id
            or before_race != expected_race_id
            or roster_race != expected_race_id):
        return denied("SOURCE_RACE_ID_MISMATCH")
    if (not roster_observed <= begin <= observed < cutoff <= deadline
            or not 0 <= (observed - begin).total_seconds() <= MAX_REQUEST_SECONDS
            or not 0 <= (observed - roster_observed).total_seconds() <= 86400
            or not WINDOW_MIN <= (deadline - observed).total_seconds() / 60 <= WINDOW_MAX):
        return denied("NOT_FRESH_PREDEADLINE_EVIDENCE")
    raw_b64 = receipt.get("raw_base64")
    if not isinstance(raw_b64, str) or not raw_b64:
        return denied("ORIGINAL_BEFOREINFO_BYTES_MISSING")
    try:
        raw = base64.b64decode(raw_b64, validate=True)
    except (ValueError, binascii.Error):
        return denied("ORIGINAL_BEFOREINFO_ENCODING_INVALID")
    if (not raw or len(raw) > max_bytes
            or receipt.get("raw_size_bytes") != len(raw)
            or receipt.get("raw_sha256") != hashlib.sha256(raw).hexdigest()):
        return denied("ORIGINAL_BEFOREINFO_SHA256_MISMATCH")
    try:
        html = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return denied("ORIGINAL_BEFOREINFO_CHARSET_UNKNOWN")
    entries = roster.get("entries")
    if (not isinstance(entries, (list, tuple)) or len(entries) != 6
            or len({e.get("racer_number") for e in entries if isinstance(e, Mapping)}) != 6
            or sorted(e.get("lane") for e in entries if isinstance(e, Mapping)) != list(range(1, 7))
            or any(not isinstance(e, Mapping)
                   or type(e.get("racer_number")) is not int
                   or e.get("racer_number") <= 0
                   or e.get("active_verified") is not False
                   for e in entries)):
        return denied("RACELIST_CANDIDATE_ROSTER_INVALID")
    # Build cancellation evidence only from boat-specific structured rows.
    # Never search generic page text or post-race results as positive proof.
    rows = []
    for tbody in BeautifulSoup(html, "html.parser").select("tbody.is-fs12"):
        trs = tbody.find_all("tr", recursive=False)
        if not trs:
            continue
        first_cells = _direct_cells(trs[0])
        lane = _lane_from_cells(first_cells)
        if lane is None:
            continue
        combined = _normalized(tbody.get_text(" ", strip=True))
        negative = [m for m in WITHDRAWAL_MARKERS if m in combined]
        rows.append({"lane": lane, "withdrawal_markers": negative})
    observed_lanes = [r["lane"] for r in rows]
    if (len(rows) != 6 or sorted(observed_lanes) != list(range(1, 7))):
        return denied("BEFOREINFO_NOT_SIX_STRUCTURED_LANES")
    withdrawals = [
        {"lane": r["lane"], "markers": r["withdrawal_markers"]}
        for r in rows if r["withdrawal_markers"]
    ]
    parsed = inspect_exhibition_time_page(html)
    complete_exhibition = (
        parsed.get("status") == EXHIBITION_STATUS_COMPLETE
        and parsed.get("source") == "primary_structured_rows"
        and parsed.get("valid_time_count") == 6
        and parsed.get("lanes") == list(range(1, 7))
    )
    classification = (
        "EXPLICIT_WITHDRAWAL_DISPLAYED" if withdrawals else
        "SIX_EXHIBITION_CANDIDATES_START_UNKNOWN" if complete_exhibition else
        "INCOMPLETE_EXHIBITION_START_UNKNOWN"
    )
    return {
        "status": classification,
        "reason": (
            "EXPLICIT_PREDEADLINE_WITHDRAWAL" if withdrawals
            else "OFFICIAL_POSITIVE_START_STATUS_NOT_ESTABLISHED"
        ),
        "race_id": expected_race_id,
        "response_completed_at": observed.isoformat(),
        "racelist_captured_at": roster_observed.isoformat(),
        "original_beforeinfo_sha256": hashlib.sha256(raw).hexdigest(),
        "exhibition_six_complete": complete_exhibition,
        "explicit_withdrawals": withdrawals,
        "all_six_active_confirmed": False,
        "beforeinfo_prewrite_eligible": False,
        "forward_eligible": False,
        "limitations": (
            "Official source authenticity and earliest capture still need "
            "independent audit. Six exhibition boats or missing withdrawal "
            "markers do NOT establish six confirmed starters."
        ),
    }
