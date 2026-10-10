# -*- coding: utf-8 -*-
"""V5 mainline BEFOREINFO pre-first-write fail-closed eligibility gate.

Independently validated race deadline/cutoff and six active racer roster
attestation MUST come from the caller's verified source. The official page
alone shows exhibition and may not prove racers' start status. An attestation
is not cryptographic proof of genuine source acquisition. This gate permits
ONLY a bounded, complete per-race FIRST-WRITE candidate, NEVER Forward/BUY.

No HTTP/DB I/O or Production V4 changes.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import math
from collections.abc import Mapping
from datetime import datetime

from bs4 import BeautifulSoup

from historical_beforeinfo_parser_v3 import (
    EXHIBITION_STATUS_COMPLETE,
    inspect_exhibition_time_page,
    _direct_cells,
    _lane_from_cells,
)
from v5.official_http_receipt import _aware_dt, _source_from_exact_url, UnverifiedCapture
from v5.official_first_write_storage import _identity

MIN_MINUTES_BEFORE = 8.0
MAX_MINUTES_BEFORE = 15.0


def check_beforeinfo_prewrite(
    receipt: Mapping | None,
    *,
    expected_race_id: str,
    official_deadline_at,
    prediction_cutoff_at,
    racelist_evidence: Mapping | None,
) -> dict:
    """Return a reason on failure; allow only prewrite, never prediction.

    racelist_evidence is a separate, caller-attested first-readback entry
    snapshot. This function checks consistency but cannot authenticate the
    issuer, official source page or DB privilege history by itself.
    """
    def reject(reason):
        return {"prewrite_eligible": False, "reason": reason,
                "forward_eligible": False}

    if not isinstance(receipt, Mapping) or receipt.get("contract") != "V5_OFFICIAL_HTTP_CAPTURE_PROPOSAL_V1":
        return reject("NO_VERIFIED_HTTP_PROPOSAL")
    if receipt.get("source") != "official_beforeinfo" or receipt.get("forward_eligible") is not False:
        return reject("WRONG_SOURCE_OR_PREMATURE_FORWARD")
    if (receipt.get("first_write_confirmed") is not False
            or receipt.get("first_observed_at") is not None
            or receipt.get("receipt_ref") is not None):
        return reject("PREMATURE_FIRST_CAPTURE_ASSERTION")
    try:
        url = receipt["source_url"]
        kind, maximum = _source_from_exact_url(url)
        key, linked_race_id = _identity(kind, url)
    except (KeyError, ValueError, TypeError, UnverifiedCapture):
        return reject("UNVERIFIED_BEFOREINFO_URL")
    if kind != "official_beforeinfo" or linked_race_id != expected_race_id or not expected_race_id:
        return reject("BEFOREINFO_RACE_ID_MISMATCH")
    try:
        captured = _aware_dt(receipt.get("response_completed_at"))
        started = _aware_dt(receipt.get("request_started_at"))
        deadline = _aware_dt(official_deadline_at)
        cutoff = _aware_dt(prediction_cutoff_at)
    except (UnverifiedCapture, ValueError, TypeError):
        return reject("MISSING_OR_UNZONED_CLOCK")
    if not (started <= captured < cutoff <= deadline):
        return reject("NOT_BEFORE_DECISION_CUTOFF")
    if not 0 <= (captured - started).total_seconds() <= 180:
        return reject("INVALID_RESPONSE_DURATION")
    minutes = (deadline - captured).total_seconds() / 60
    if not MIN_MINUTES_BEFORE <= minutes <= MAX_MINUTES_BEFORE:
        return reject("OUTSIDE_EXHIBITION_CAPTURE_WINDOW")

    # Only parse the exact bytes whose digest will be stored. No fallback to
    # mutable race history or unbound parsed-row assertions.
    encoded = receipt.get("raw_base64")
    if not isinstance(encoded, str) or not encoded:
        return reject("MISSING_BEFOREINFO_BYTES")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return reject("INVALID_BEFOREINFO_ENCODING")
    if (not raw or len(raw) > maximum
            or receipt.get("raw_size_bytes") != len(raw)
            or receipt.get("raw_sha256") != hashlib.sha256(raw).hexdigest()):
        return reject("UNVERIFIED_BEFOREINFO_BYTES")
    html = raw.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    # No generic-text fallback. The six distinct structured boat rows
    # must be present; duplicate lane rows MUST NOT silently collapse.
    structured_lanes = []
    for tbody in soup.select("tbody.is-fs12"):
        trs = tbody.find_all("tr", recursive=False)
        if trs:
            lane = _lane_from_cells(_direct_cells(trs[0]))
            if lane is not None:
                structured_lanes.append(lane)
    if len(structured_lanes) != 6 or sorted(structured_lanes) != [1, 2, 3, 4, 5, 6]:
        return reject("NOT_EXACTLY_SIX_STRUCTURED_LANES")
    parsed = inspect_exhibition_time_page(html)
    if (parsed.get("status") != EXHIBITION_STATUS_COMPLETE
            or parsed.get("source") != "primary_structured_rows"
            or parsed.get("valid_time_count") != 6
            or parsed.get("lanes") != [1, 2, 3, 4, 5, 6]):
        return reject("INCOMPLETE_OR_FALLBACK_EXHIBITION")
    rows = parsed.get("rows")
    if not isinstance(rows, list) or len(rows) != 6:
        return reject("INCOMPLETE_OR_FALLBACK_EXHIBITION")
    if sorted(r.get("lane") for r in rows) != [1, 2, 3, 4, 5, 6]:
        return reject("EXHIBITION_LANE_MISMATCH")
    times = [r.get("exhibition_time") for r in rows]
    ranks = [r.get("exhibition_time_rank") for r in rows]
    if (any(type(v) not in (float, int) or not math.isfinite(v) or not 6.0 <= v < 8.0 for v in times)
            or any(type(v) is not int for v in ranks)
            or sorted(ranks) != [1, 2, 3, 4, 5, 6]):
        return reject("INVALID_SIX_EXHIBITION_VALUES")

    # BEFOREINFO alone does not establish racers are all active: six-racer
    # verification must originate in a separately observed official racelist.
    if not isinstance(racelist_evidence, Mapping) or not racelist_evidence:
        return reject("ACTIVE_RACELIST_EVIDENCE_MISSING")
    if (racelist_evidence.get("source") != "official_racelist"
            or racelist_evidence.get("race_id") != expected_race_id
            or racelist_evidence.get("first_write_confirmed") is not True
            or racelist_evidence.get("readback_confirmed") is not True):
        return reject("UNVERIFIED_ACTIVE_RACELIST")
    try:
        roster_url = racelist_evidence.get("source_url")
        r_kind, _ = _source_from_exact_url(roster_url)
        _, roster_race = _identity(r_kind, roster_url)
        roster_at = _aware_dt(racelist_evidence.get("captured_at"))
    except (TypeError, ValueError, UnverifiedCapture):
        return reject("UNVERIFIED_ACTIVE_RACELIST")
    if (r_kind != "official_racelist" or roster_race != expected_race_id
            or roster_at > captured or roster_at >= cutoff
            or not isinstance(racelist_evidence.get("raw_sha256"), str)
            or len(racelist_evidence["raw_sha256"]) != 64
            or not all(c in "0123456789abcdef" for c in racelist_evidence["raw_sha256"])):
        return reject("UNVERIFIED_ACTIVE_RACELIST")
    entries = racelist_evidence.get("entries")
    if not isinstance(entries, (list, tuple)) or len(entries) != 6:
        return reject("NOT_SIX_ACTIVE_RACERS")
    lanes, racers = [], []
    for e in entries:
        if not isinstance(e, Mapping) or e.get("active") is not True:
            return reject("NOT_SIX_ACTIVE_RACERS")
        lane, racer = e.get("lane"), e.get("racer_number")
        if (type(lane) is not int or type(racer) is not int
                or not 1 <= lane <= 6 or racer <= 0):
            return reject("INVALID_RACER_IDENTITY")
        lanes.append(lane)
        racers.append(racer)
    if sorted(lanes) != [1, 2, 3, 4, 5, 6] or len(set(racers)) != 6:
        return reject("DUPLICATE_OR_MISSING_RACERS")
    return {"prewrite_eligible": True, "reason": "COMPLETE_BEFOREINFO_PREWRITE_ONLY",
            "forward_eligible": False, "race_id": linked_race_id,
            "source_sha256": hashlib.sha256(raw).hexdigest()}
