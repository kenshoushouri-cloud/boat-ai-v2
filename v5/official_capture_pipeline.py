# -*- coding: utf-8 -*-
"""V5 mainline official HTTP capture -> first-write persistence; NOT deployed.

This callable uses ONLY explicitly injected HTTP and DB objects. It has no
import-time I/O, database URL lookup, migrations, retries, or V4/BUY actions.
It is opt-in and fail closed. A byte-for-byte matching first stored source
response alone does NOT independently prove earliest capture, official
publication timing, complete entry/feature provenance or Forward eligibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from collections.abc import Mapping

from v5.beforeinfo_prewrite_gate import check_beforeinfo_prewrite

from v5.official_first_write_executor import (
    FirstWriteRejected,
    persist_first_http_capture,
)
from v5.official_http_receipt import UnverifiedCapture
from v5.official_http_transport import capture_v5_official_response


class CapturePipelineNotReady(RuntimeError):
    """The end-to-end V5 source is unavailable or unverified for Forward."""


def capture_and_store_v5_official_source(
    *,
    session: Any,
    connection: Any,
    requested_url: str,
    expected_source: str,
    expected_race_id: str | None,
    storage_enabled: bool = False,
    clock: Callable[[], datetime] | None = None,
    timeout_seconds: float = 15.0,
    official_deadline_at: Any = None,
    prediction_cutoff_at: Any = None,
    racelist_evidence: Mapping | None = None,
) -> dict[str, Any]:
    """Perform ONE response capture and ONE transactional insert/readback.

    storage_enabled must be explicitly True. The caller MUST independently
    ensure the connection is an ISOLATED V5 INSERT+SELECT-only account before
    invoking this function. This code cannot infer the DB's role or origin.
    Actual Railway/Production invocation is not configured or approved.
    """
    if storage_enabled is not True:
        raise CapturePipelineNotReady("V5_STORAGE_NOT_ENABLED")
    if connection is None or not callable(getattr(connection, "transaction", None)) or not callable(getattr(connection, "cursor", None)):
        raise CapturePipelineNotReady("EXPLICIT_ISOLATED_DB_CONNECTION_REQUIRED")
    if session is None or not callable(getattr(session, "get", None)):
        raise CapturePipelineNotReady("EXPLICIT_HTTP_SESSION_REQUIRED")

    try:
        observed = capture_v5_official_response(
            session=session,
            requested_url=requested_url,
            expected_source=expected_source,
            expected_race_id=expected_race_id,
            clock=clock,
            timeout_seconds=timeout_seconds,
        )
        if (observed.get("status") != "HTTP_OBSERVED_STORAGE_NOT_EXECUTED"
                or observed.get("forward_eligible") is not False
                or observed.get("first_observed_at") is not None):
            raise CapturePipelineNotReady("UNVERIFIED_HTTP_CAPTURE_PROPOSAL")
        receipt = observed["receipt_proposal"]
        storage_plan = observed["storage_plan"]
        if expected_source == "official_beforeinfo":
            prewrite = check_beforeinfo_prewrite(
                receipt,
                expected_race_id=expected_race_id,
                official_deadline_at=official_deadline_at,
                prediction_cutoff_at=prediction_cutoff_at,
                racelist_evidence=racelist_evidence,
            )
            if prewrite.get("prewrite_eligible") is not True:
                raise CapturePipelineNotReady(
                    "BEFOREINFO_PREWRITE_DENIED:" + prewrite["reason"]
                )
        result = persist_first_http_capture(connection, storage_plan)
        if (result.get("storage_consistent") is not True
                or result.get("forward_eligible") is not False
                or result.get("first_observed_at") is not None
                or result.get("first_write_confirmed") is not False):
            raise CapturePipelineNotReady("UNVERIFIED_FIRST_WRITE_READBACK")
    except (FirstWriteRejected, UnverifiedCapture) as exc:
        # Do not log raw payloads, credentials, or underlying database errors.
        raise CapturePipelineNotReady("V5_CAPTURE_OR_STORAGE_NOT_VERIFIED") from exc

    return {
        "status": "STORED_SOURCE_CONSISTENT_FORWARD_UNVERIFIED",
        "storage_status": result["status"],
        "resource_key": result["resource_key"],
        "source": receipt["source"],
        "response_completed_at": receipt["response_completed_at"],
        "raw_sha256": receipt["raw_sha256"],
        "inserted_this_attempt": result["inserted_this_attempt"],
        "storage_consistent": True,
        "beforeinfo_prewrite_checked": expected_source == "official_beforeinfo",
        "first_observed_at": None,
        "first_write_confirmed": False,
        "forward_eligible": False,
        "limitations": (
            "One request + same-transaction byte/digest readback only. "
            "Independent verified fetch record, restrictive DB grants, "
            "reliable first-observed provenance, six-entry form/exhibition "
            "cutoff checks and economic Forward proof are still pending."
        ),
    }
