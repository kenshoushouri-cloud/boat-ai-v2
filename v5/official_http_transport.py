# -*- coding: utf-8 -*-
"""V5 mainline HTTP-to-first-write-plan adapter; NOT wired into Production.

Caller passes an HTTP session compatible with requests.Session. This is a
real transport-capable function, but only runs if explicitly invoked by a
future V5-only collector. No import-time network calls, DB writes, DDL, LINE,
model activation, stake or purchase actions.

Capture clock = local response-body completion time; it is NOT official
publication time and not proven first-ever observation. Source/readback
attestation is a separate later integration step. Do not use an existing
mutable snapshot's updated_at/fetched_at as an original receipt time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from v5.official_http_receipt import (
    UnverifiedCapture,
    _aware_dt,
    _source_from_exact_url,
    prepare_official_http_receipt,
)
from v5.official_first_write_storage import prepare_first_write_storage

CHUNK_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0


def capture_v5_official_response(
    *,
    session: Any,
    requested_url: str,
    expected_source: str,
    expected_race_id: str | None,
    clock: Callable[[], datetime] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Capture one bounded official GET, generate ONLY a first-write proposal.

    No retry: another GET has a DIFFERENT observed time, so it must be a
    separate recorded request. Actual HTTP session MUST be provided by the
    future isolated V5 collector; caller owns/provides its network policy.

    Requests-compatible session.get(url, stream=True, allow_redirects=False,
    timeout=seconds) and response.iter_content(chunk_size=N) are used, never
    response.text. Returned plans are never executed here.
    """
    kind, maximum = _source_from_exact_url(requested_url)
    if kind != expected_source:
        raise UnverifiedCapture("SOURCE_KIND_MISMATCH")
    if type(timeout_seconds) not in (int, float) or not (0 < timeout_seconds <= MAX_TIMEOUT_SECONDS):
        raise UnverifiedCapture("INVALID_TRANSPORT_TIMEOUT")
    if session is None or not callable(getattr(session, "get", None)):
        raise UnverifiedCapture("HTTP_SESSION_REQUIRED")

    now = clock if clock is not None else lambda: datetime.now(timezone.utc)
    started = _aware_dt(now())
    response = None
    try:
        try:
            response = session.get(
                requested_url, allow_redirects=False,
                stream=True, timeout=timeout_seconds,
            )
        except Exception as exc:
            raise UnverifiedCapture("HTTP_TRANSPORT_FAILED") from exc

        if response is None:
            raise UnverifiedCapture("HTTP_RESPONSE_MISSING")
        status = getattr(response, "status_code", None)
        if type(status) is not int or status != 200:
            raise UnverifiedCapture("HTTP_RESPONSE_NOT_OK")
        if getattr(response, "url", None) != requested_url:
            raise UnverifiedCapture("REDIRECT_OR_URL_MISMATCH")
        if getattr(response, "history", None):
            raise UnverifiedCapture("REDIRECT_HISTORY_NOT_ALLOWED")

        headers = getattr(response, "headers", {}) or {}
        length_text = headers.get("Content-Length") if hasattr(headers, "get") else None
        if length_text is not None:
            try:
                announced = int(length_text)
            except (ValueError, TypeError) as exc:
                raise UnverifiedCapture("INVALID_CONTENT_LENGTH") from exc
            if announced < 0:
                raise UnverifiedCapture("INVALID_CONTENT_LENGTH")
            if announced > maximum:
                raise UnverifiedCapture("SOURCE_RESPONSE_TOO_LARGE")

        parts: list[bytes] = []
        total = 0
        try:
            for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
                if type(chunk) is not bytes:
                    raise UnverifiedCapture("INVALID_HTTP_BYTE_CHUNK")
                if not chunk:
                    continue
                total += len(chunk)
                if total > maximum:
                    raise UnverifiedCapture("SOURCE_RESPONSE_TOO_LARGE")
                parts.append(chunk)
        except UnverifiedCapture:
            raise
        except Exception as exc:
            raise UnverifiedCapture("HTTP_STREAM_FAILED") from exc
        # Stamp immediately after consuming bytes; no post-processing time
        # may be represented as the first available timestamp.
        completed = _aware_dt(now())
        if not total:
            raise UnverifiedCapture("MISSING_RAW_RESPONSE")
        # Verification in pure helpers also checks clock duration and
        # immutable-source proposal contract, never authorizes Forward.
        receipt = prepare_official_http_receipt(
            requested_url=requested_url,
            final_url=response.url,
            expected_source=expected_source,
            http_status=status,
            response_body=b"".join(parts),
            request_started_at=started,
            response_completed_at=completed,
        )
        plan = prepare_first_write_storage(
            receipt, expected_race_id=expected_race_id,
        )
        return {
            "status": "HTTP_OBSERVED_STORAGE_NOT_EXECUTED",
            "receipt_proposal": receipt,
            "storage_plan": plan,
            "first_observed_at": None,
            "forward_eligible": False,
            "limitations": "HTTP bytes/time observed once during this call; no verified first-write DB receipt or official release timing.",
        }
    finally:
        if response is not None:
            close = getattr(response, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
