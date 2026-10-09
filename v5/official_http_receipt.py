# -*- coding: utf-8 -*-
"""V5 mainline (not yet Production): official HTTP response receipt proposal.

A PURE converter of already-fetched raw response bytes; it does not fetch
anything or make database writes. It records the completion timestamp of this
HTTP request, NOT an invented official publication time or proven first sight.
Only a later independently audited first-write+readback process may turn the
provisional key into a durable first-observation receipt.

V4 Production/LINE/stake/BUY are deliberately outside this module.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlsplit


class UnverifiedCapture(ValueError):
    """Missing/untrusted/late evidence: never silently allow Forward."""


MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_K_BYTES = 10 * 1024 * 1024
MAX_REQUEST_SECONDS = 180.0

_OFFICIAL_PAGE_HOST = "www.boatrace.jp"
_OFFICIAL_K_HOST = "www1.mbrace.or.jp"


def _aware_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise UnverifiedCapture("INVALID_CAPTURE_CLOCK") from exc
    else:
        raise UnverifiedCapture("INVALID_CAPTURE_CLOCK")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise UnverifiedCapture("UNZONED_CAPTURE_CLOCK")
    return dt


def _source_from_exact_url(url: str) -> tuple[str, int]:
    """Reject nonofficial hosts, extra query keys, credentials, and bad paths."""
    if not isinstance(url, str) or not url:
        raise UnverifiedCapture("SOURCE_URL_MISSING")
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError as exc:
        raise UnverifiedCapture("SOURCE_URL_INVALID") from exc
    if (u.scheme != "https" or u.username is not None or
            u.password is not None or port is not None or u.fragment):
        raise UnverifiedCapture("UNTRUSTED_SOURCE_URL")
    if u.hostname == _OFFICIAL_PAGE_HOST and u.path in (
        "/owpc/pc/race/racelist", "/owpc/pc/race/beforeinfo"
    ):
        pairs = parse_qsl(u.query, keep_blank_values=True)
        values = dict(pairs)
        if (len(pairs) != 3 or len(values) != 3 or
                set(values) != {"rno", "jcd", "hd"} or
                not re.fullmatch(r"(?:[1-9]|1[0-2])", values["rno"]) or
                not re.fullmatch(r"(?:0[1-9]|1[0-9]|2[0-4])", values["jcd"]) or
                not re.fullmatch(r"20\d{6}", values["hd"])):
            raise UnverifiedCapture("INVALID_OFFICIAL_RACE_QUERY")
        try:
            parsed = datetime.strptime(values["hd"], "%Y%m%d")
            if parsed.strftime("%Y%m%d") != values["hd"]:
                raise ValueError("noncanonical date")
        except ValueError as exc:
            raise UnverifiedCapture("INVALID_OFFICIAL_RACE_DATE") from exc
        return (
            "official_racelist" if u.path.endswith("/racelist")
            else "official_beforeinfo", MAX_PAGE_BYTES
        )
    if u.hostname == _OFFICIAL_K_HOST:
        m = re.fullmatch(r"/od2/K/(20\d{4})/k(\d{6})\.lzh", u.path)
        if m is None or u.query:
            raise UnverifiedCapture("INVALID_OFFICIAL_K_PATH")
        try:
            d = datetime.strptime("20" + m.group(2), "%Y%m%d")
            if d.strftime("%Y%m") != m.group(1):
                raise ValueError("K folder doesn't match file date")
        except ValueError as exc:
            raise UnverifiedCapture("INVALID_OFFICIAL_K_DATE") from exc
        return "official_k_file", MAX_K_BYTES
    raise UnverifiedCapture("UNTRUSTED_SOURCE_URL")


def prepare_official_http_receipt(
    *,
    requested_url: str,
    final_url: str,
    expected_source: str,
    http_status: int,
    response_body: bytes,
    request_started_at: Any,
    response_completed_at: Any,
) -> dict[str, Any]:
    """Prepare bytes/digest with no false 'first observed' attestation.

    The caller must capture these inputs DIRECTLY from its HTTP transport;
    this function cannot verify an arbitrary caller's claims or the page
    content's official authenticity. It is not connected to V5 decisions.
    """
    source, max_bytes = _source_from_exact_url(requested_url)
    if final_url != requested_url:
        raise UnverifiedCapture("REDIRECT_OR_URL_MISMATCH")
    if expected_source != source:
        raise UnverifiedCapture("SOURCE_KIND_MISMATCH")
    if type(http_status) is not int or http_status != 200:
        raise UnverifiedCapture("HTTP_RESPONSE_NOT_OK")
    if type(response_body) is not bytes or not response_body:
        raise UnverifiedCapture("MISSING_RAW_RESPONSE")
    if len(response_body) > max_bytes:
        raise UnverifiedCapture("SOURCE_RESPONSE_TOO_LARGE")
    start = _aware_dt(request_started_at)
    completed = _aware_dt(response_completed_at)
    duration = (completed - start).total_seconds()
    if duration < 0 or duration > MAX_REQUEST_SECONDS:
        raise UnverifiedCapture("INVALID_OR_STALE_RESPONSE_CLOCK")

    digest = hashlib.sha256(response_body).hexdigest()
    # This key uniquely describes the proposed original response, but it is
    # NOT a DB receipt ID and does not prove first-write or real capture.
    key_material = json.dumps(
        {"source": source, "url": requested_url,
         "completed_at": completed.isoformat(), "raw_sha256": digest},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    proposal_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    return {
        "contract": "V5_OFFICIAL_HTTP_CAPTURE_PROPOSAL_V1",
        "source": source,
        "source_url": requested_url,
        "response_completed_at": completed.isoformat(),
        "request_started_at": start.isoformat(),
        "observed_at": completed.isoformat(),
        "first_observed_at": None,
        "receipt_ref": None,
        "provisional_receipt_key": proposal_key,
        "raw_sha256": digest,
        "raw_base64": base64.b64encode(response_body).decode("ascii"),
        "raw_size_bytes": len(response_body),
        "http_status": http_status,
        "first_write_confirmed": False,
        "readback_confirmed": False,
        "readback_sha256": None,
        "forward_eligible": False,
        "limitations": (
            "No first-write/readback proof. Response completion != official "
            "publication time. The direct HTTP source, original bytes, "
            "content parser and authentic receipt storage require external "
            "verification before any V5 Forward eligibility."
        ),
    }
