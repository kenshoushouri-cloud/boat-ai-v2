# -*- coding: utf-8 -*-
"""V5 mainline first-write persistence executor; NOT deployed or scheduled.

Accepts only a caller-provided transaction-capable DB connection and a plan
from v5.official_first_write_storage.prepare_first_write_storage. Never opens
a connection, creates tables, modifies Production V4 or sends LINE/BUY.

The FIRST row is stored via INSERT ON CONFLICT DO NOTHING, read back in the
SAME transaction and compared byte-for-byte. A collision or missing/invalid
readback raises, so the transaction rolls back. Even a successful commit does
NOT prove that source bytes are authentic, that this was the first observation
of the official page, or that the input is safe for Forward/BUY.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from v5.official_first_write_storage import (
    INSERT_FIRST,
    READ_FIRST,
    _identity,
    verify_first_write_readback,
)
from v5.official_http_receipt import _aware_dt, _source_from_exact_url, UnverifiedCapture


class FirstWriteRejected(RuntimeError):
    """Fail closed without exposing original DB errors or response bytes."""


READ_COLUMNS = (
    "resource_key", "source_kind", "race_id", "source_url",
    "request_started_at", "response_completed_at", "raw_bytes", "raw_sha256",
)


def _validate_prepared_plan(plan: Any) -> tuple[Any, ...]:
    if (not isinstance(plan, Mapping)
            or plan.get("status") != "PREPARED_ONLY_NO_DB_WRITE"
            or plan.get("sql") != INSERT_FIRST
            or plan.get("read_sql") != READ_FIRST
            or plan.get("forward_eligible") is not False
            or plan.get("first_write_confirmed") is not False
            or plan.get("first_observed_at") is not None):
        raise FirstWriteRejected("UNVERIFIED_OR_TAMPERED_STORAGE_PLAN")
    params = plan.get("params")
    if not isinstance(params, tuple) or len(params) != 8:
        raise FirstWriteRejected("INVALID_STORAGE_PARAMETERS")
    key, kind, rid, url, started, finished, raw, digest = params
    if (not isinstance(key, str) or not key
            or not isinstance(url, str)
            or not isinstance(raw, bytes) or not raw
            or not isinstance(digest, str)
            or hashlib.sha256(raw).hexdigest() != digest
            or plan.get("resource_key") != key
            or plan.get("race_id") != rid
            or plan.get("source_kind") != kind
            or plan.get("raw_sha256") != digest
            or plan.get("read_params") != (key,)):
        raise FirstWriteRejected("STORAGE_PARAMETER_INTEGRITY_FAILED")
    try:
        verified_kind, maximum = _source_from_exact_url(url)
        expected_key, expected_race = _identity(verified_kind, url)
        if (verified_kind != kind or len(raw) > maximum
                or expected_key != key or expected_race != rid
                or not 0 <= (_aware_dt(finished)-_aware_dt(started)).total_seconds() <= 180):
            raise FirstWriteRejected("STORAGE_IDENTITY_OR_CLOCK_FAILED")
    except UnverifiedCapture as exc:
        raise FirstWriteRejected("STORAGE_IDENTITY_OR_CLOCK_FAILED") from exc
    return params


def _returning_key(row: Any) -> str | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        key = row.get("resource_key")
    elif isinstance(row, (tuple, list)) and len(row) == 1:
        key = row[0]
    else:
        raise FirstWriteRejected("INSERT_RETURNING_INVALID")
    if not isinstance(key, str):
        raise FirstWriteRejected("INSERT_RETURNING_INVALID")
    return key


def _frozen_dict(row: Any) -> Mapping[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row
    if isinstance(row, (tuple, list)) and len(row) == len(READ_COLUMNS):
        return dict(zip(READ_COLUMNS, row))
    raise FirstWriteRejected("READBACK_SHAPE_INVALID")


def persist_first_http_capture(connection: Any, plan: Mapping[str, Any]) -> dict[str, Any]:
    """Perform exactly one first-write INSERT and frozen SELECT in one tx.

    This function ONLY executes against an explicitly injected connection;
    there is no environment-variable lookup, DSN or connection creation.
    No UPDATE, UPSERT, DDL or retry is ever issued.

    Success still yields forward_eligible=False and first_observed_at=None.
    A caller cannot treat its own DB readback as independent official capture
    provenance. Use a separate external audit before Forward promotion.
    """
    params = _validate_prepared_plan(plan)
    if (connection is None or not callable(getattr(connection, "transaction", None))
            or not callable(getattr(connection, "cursor", None))):
        raise FirstWriteRejected("EXPLICIT_TRANSACTION_CONNECTION_REQUIRED")

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(INSERT_FIRST, params)
                inserted_key = _returning_key(cursor.fetchone())
                if inserted_key is not None and inserted_key != params[0]:
                    raise FirstWriteRejected("INSERT_RETURNING_WRONG_RESOURCE")
                cursor.execute(READ_FIRST, (params[0],))
                frozen = _frozen_dict(cursor.fetchone())
                verified = verify_first_write_readback(
                    plan, frozen, inserted_this_attempt=(inserted_key is not None),
                )
                if verified.get("storage_consistent") is not True:
                    raise FirstWriteRejected(verified.get("status", "READBACK_VERIFICATION_FAILED"))
                # Returning from within context commits if no exception.
                return {
                    "status": verified["status"],
                    "storage_consistent": True,
                    "resource_key": params[0],
                    "inserted_this_attempt": inserted_key is not None,
                    "first_observed_at": None,
                    "first_write_confirmed": False,
                    "forward_eligible": False,
                    "limitations": (
                        "Transaction readback consistent only; authentic earliest "
                        "source observation, append-only DB permissions, verified "
                        "collector logs and Forward eligibility still unproven."
                    ),
                }
    except FirstWriteRejected:
        raise
    except Exception as exc:
        # No DB query strings, URLs, credentials or captured bytes in errors.
        raise FirstWriteRejected("DATABASE_TRANSACTION_FAILED") from exc
