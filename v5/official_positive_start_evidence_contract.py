# -*- coding: utf-8 -*-
"""V5 mainline: real-observation summary -> independently auditable start-proof need.

The 2026-10-10 GitHub-only Edogawa-1R pilot retained only anonymized th/dt
header-keyword counts and source hashes/timestamps. Those summaries are NOT
proof of six racers actually starting; they do not contain original source
bytes, authoritative lane-level status fields or first-observation evidence.

This pure review contract NEVER authorizes beforeinfo INSERT, Forward or BUY.
A future separately vetted positive official source schema and original-body
immutable acquisition audit are required. No network, DB, Railway or V4 I/O.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

from v5.official_http_receipt import _aware_dt, UnverifiedCapture

JST = ZoneInfo("Asia/Tokyo")
RACE_ID_RE = re.compile(r"^(20\d{6})_(0[1-9]|1[0-9]|2[0-4])_(0[1-9]|1[0-2])$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_ORDER = ("official_racelist", "official_beforeinfo")
SCANNED_HEADER_KEYWORDS = ("出走確定", "出走状況", "出走予定", "欠場")
# Deliberately no positive source schema is certified. Header keywords,
# textual '出走' and all-6 exhibition participation are never an allowlist.
APPROVED_POSITIVE_SOURCE_SCHEMAS: frozenset[str] = frozenset()


def review_positive_start_evidence(
    report: Mapping | None,
    *,
    expected_race_id: str,
    official_deadline_at,
    decision_cutoff_at,
) -> dict:
    """Describe whether this metadata merits deeper evidence discovery.

    Confirmation is ALWAYS false until a separately reviewed actual official
    positive-status schema can bind all six active lane/racer pairs to frozen
    original bytes and verified predeadline acquisition. This function does
    NOT accept a caller-supplied 'active' or 'confirmed' boolean.
    """
    def verdict(reason: str, consistent: bool = False) -> dict:
        return {
            "status": "POSITIVE_START_PROOF_NOT_ESTABLISHED",
            "reason": reason,
            "reviewed_summary_consistent": consistent,
            "source_bytes_independently_authenticated": False,
            "original_first_observation_proven": False,
            "six_active_starts_confirmed": False,
            "beforeinfo_first_write_eligible": False,
            "forward_eligible": False,
            "positive_schema_approved": False,
            "required_next_evidence": (
                "A vetted official source-specific affirmative six-lane status "
                "field, bound racer IDs and explicit cutoff, original raw bytes "
                "plus immutable first-fetch provenance and restricted DB audit"
            ),
        }

    if not isinstance(report, Mapping):
        return verdict("MISSING_OBSERVATION_REPORT")
    if (report.get("status") != "READ_ONLY_DISCOVERY_COMPLETE_NOT_VERIFIED"
            or report.get("attempted_gets") != 2
            or report.get("persistence_performed") is not False
            or report.get("forward_eligible") is not False
            or report.get("all_six_active_confirmed") is not False):
        return verdict("REPORT_SCOPE_OR_SAFETY_INVALID")
    if not isinstance(expected_race_id, str) or RACE_ID_RE.fullmatch(expected_race_id) is None:
        return verdict("INVALID_RACE_ID")
    try:
        datetime.strptime(expected_race_id[:8], "%Y%m%d")
        deadline = _aware_dt(official_deadline_at)
        cutoff = _aware_dt(decision_cutoff_at)
    except (ValueError, TypeError, UnverifiedCapture):
        return verdict("INVALID_OFFICIAL_DEADLINE_OR_CUTOFF")
    if not cutoff < deadline:
        return verdict("INVALID_OFFICIAL_DEADLINE_OR_CUTOFF")
    items = report.get("observations")
    if not isinstance(items, (list, tuple)) or len(items) != 2:
        return verdict("TWO_SOURCE_RECORDS_REQUIRED")
    times = []
    before_exhibition_complete = False
    observed_labels: dict[str, int] = {}
    for i, item in enumerate(items):
        if (not isinstance(item, Mapping)
                or item.get("source") != SOURCE_ORDER[i]
                or item.get("race_id") != expected_race_id
                or item.get("status") != "OBSERVED_CONTENT_NOT_AUTHENTICATED"
                or item.get("all_six_active_confirmed") is not False
                or item.get("first_observed_at") is not None
                or item.get("forward_eligible") is not False):
            return verdict("UNVERIFIED_OR_REORDERED_SOURCE_RECORD")
        digest = item.get("raw_sha256")
        raw_size = item.get("raw_size_bytes")
        if (not isinstance(digest, str) or HEX64_RE.fullmatch(digest) is None
                or type(raw_size) is not int or not 0 < raw_size <= 10_485_760):
            return verdict("ORIGINAL_HASH_OR_SIZE_INVALID")
        try:
            observed_at = _aware_dt(item.get("response_completed_at"))
        except (ValueError, TypeError, UnverifiedCapture):
            return verdict("RESPONSE_COMPLETION_TIME_UNVERIFIED")
        if observed_at.astimezone(JST).strftime("%Y%m%d") != expected_race_id[:8]:
            return verdict("OBSERVATION_ON_DIFFERENT_RACE_DAY")
        times.append(observed_at)
        hints = item.get("hints")
        if not isinstance(hints, Mapping) or hints.get("html_parse") != "LABEL_COUNTS_ONLY":
            return verdict("HEADER_SCAN_NOT_VERIFIABLE")
        counts = hints.get("potential_status_labels")
        if (not isinstance(counts, Mapping) or set(counts) != set(SCANNED_HEADER_KEYWORDS)
                or any(type(counts[label]) is not int or counts[label] < 0
                       for label in SCANNED_HEADER_KEYWORDS)):
            return verdict("HEADER_KEYWORD_AGGREGATES_INVALID")
        for label in SCANNED_HEADER_KEYWORDS:
            observed_labels[label] = observed_labels.get(label, 0) + counts[label]
        if i == 1:
            value = hints.get("structured_exhibition_complete")
            if type(value) is not bool:
                return verdict("SIX_EXHIBITION_FIELD_MISSING")
            before_exhibition_complete = value
    if not times[0] <= times[1] < cutoff:
        return verdict("SOURCE_CAPTURE_NOT_AS_OF_CUTOFF")
    # A valid report can only establish that the known keywords were or were
    # not in scanned <th>/<dt> headings. It cannot attest to every page field.
    if any(observed_labels[label] > 0 for label in SCANNED_HEADER_KEYWORDS):
        return verdict("HEADER_KEYWORD_CANDIDATE_ONLY_NOT_OFFICIAL_PROOF", True)
    if not before_exhibition_complete:
        return verdict("EXHIBITION_NOT_COMPLETE_AND_NO_POSITIVE_HEADER", True)
    return verdict("NO_POSITIVE_HEADER_IN_SCANNED_TH_DT_ONLY", True)
