# -*- coding: utf-8 -*-
"""V5 mainline source-receipt first-write storage CONTRACT; undeployed.

Pure plan + readback checker. SQL text is returned, NEVER executed here.
The first successful INSERT freezes one observed HTTP response per resource.
A duplicate MUST be compared with that frozen response, not overwritten.
No "first_observed_at" or authentic first-capture assertion is fabricated.
Receipt authenticity, collector timing, write permissions and external audits
are separate prerequisites for any Forward prediction.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit

from v5.official_http_receipt import (
    UnverifiedCapture, _aware_dt, _source_from_exact_url,
    MAX_REQUEST_SECONDS,
)

TABLE = "v5_official_source_first_capture"
DDL = """
CREATE TABLE IF NOT EXISTS v5_official_source_first_capture (
  resource_key text PRIMARY KEY,
  source_kind text NOT NULL
    CHECK (source_kind IN ('official_racelist','official_beforeinfo','official_k_file')),
  race_id text,
  source_url text NOT NULL,
  request_started_at timestamptz NOT NULL,
  response_completed_at timestamptz NOT NULL,
  raw_bytes bytea NOT NULL,
  raw_sha256 text NOT NULL CHECK (length(raw_sha256)=64),
  stored_at timestamptz NOT NULL DEFAULT now(),
  CHECK (octet_length(raw_bytes)>0 AND octet_length(raw_bytes)<=10485760),
  CHECK (response_completed_at >= request_started_at),
  UNIQUE (source_kind, source_url)
)
"""
INSERT_FIRST = """
INSERT INTO v5_official_source_first_capture
 (resource_key,source_kind,race_id,source_url,request_started_at,
  response_completed_at,raw_bytes,raw_sha256)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (resource_key) DO NOTHING
RETURNING resource_key
"""
READ_FIRST = """
SELECT resource_key,source_kind,race_id,source_url,request_started_at,
       response_completed_at,raw_bytes,raw_sha256,stored_at
FROM v5_official_source_first_capture WHERE resource_key=%s
"""


def _reject(reason: str) -> None:
    raise UnverifiedCapture(reason)


def _identity(source: str, url: str) -> tuple[str, str | None]:
    parts = urlsplit(url)
    if source == "official_k_file":
        # The K download is a daily bundle, NOT proof for any individual race.
        day = parts.path.rsplit("/", 1)[-1][1:7]
        return f"official_k_file:{day}", None
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    race_id = f"{q['hd']}_{q['jcd']}_{int(q['rno']):02d}"
    return f"{source}:{race_id}", race_id


def prepare_first_write_storage(
    proposal: Mapping[str, Any], *, expected_race_id: str | None = None,
) -> dict[str, Any]:
    """Validate proposed HTTP response and produce INSERT/SELECT parameters.

    Caller must use the real HTTP transport's original bytes and clocks.
    Neither this function nor a receipt hash proves what a remote site sent.
    """
    if not isinstance(proposal, Mapping) or proposal.get("contract") != "V5_OFFICIAL_HTTP_CAPTURE_PROPOSAL_V1":
        _reject("HTTP_PROPOSAL_CONTRACT_REQUIRED")
    url = proposal.get("source_url")
    kind, maximum = _source_from_exact_url(url)
    if proposal.get("source") != kind or proposal.get("http_status") != 200:
        _reject("SOURCE_IDENTITY_CONFLICT")
    if (proposal.get("first_observed_at") is not None
            or proposal.get("receipt_ref") is not None
            or proposal.get("first_write_confirmed") is not False
            or proposal.get("readback_confirmed") is not False
            or proposal.get("forward_eligible") is not False):
        _reject("PREMATURE_FIRST_OBSERVATION_CLAIM")
    raw = proposal.get("raw_base64")
    if not isinstance(raw, str) or not raw:
        _reject("RAW_RESPONSE_MISSING")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise UnverifiedCapture("RAW_RESPONSE_INVALID_ENCODING") from exc
    if not decoded or len(decoded) > maximum:
        _reject("RAW_RESPONSE_INVALID_SIZE")
    digest = hashlib.sha256(decoded).hexdigest()
    if proposal.get("raw_sha256") != digest or proposal.get("raw_size_bytes") != len(decoded):
        _reject("RAW_RESPONSE_DIGEST_CONFLICT")
    start = _aware_dt(proposal.get("request_started_at"))
    finished = _aware_dt(proposal.get("response_completed_at"))
    if not 0 <= (finished - start).total_seconds() <= MAX_REQUEST_SECONDS:
        _reject("RESPONSE_CLOCK_CONFLICT")
    if _aware_dt(proposal.get("observed_at")) != finished:
        _reject("OBSERVATION_CLOCK_CONFLICT")

    resource_key, race_id = _identity(kind, url)
    if expected_race_id != race_id:
        _reject("RACE_ID_OR_DAILY_K_MISMATCH")
    params = (resource_key, kind, race_id, url, start, finished, decoded, digest)
    return {
        "status": "PREPARED_ONLY_NO_DB_WRITE",
        "resource_key": resource_key,
        "race_id": race_id,
        "source_kind": kind,
        "raw_sha256": digest,
        "sql": INSERT_FIRST,
        "params": params,
        "read_sql": READ_FIRST,
        "read_params": (resource_key,),
        "first_observed_at": None,
        "first_write_confirmed": False,
        "forward_eligible": False,
        "limitations": (
            "Undeployed INSERT/SELECT; a matching readback checks consistency "
            "only. No proof of remote source authenticity, earliest observation, "
            "DB immutability policies or release time."
        ),
    }


def verify_first_write_readback(
    plan: Mapping[str, Any], frozen: Mapping[str, Any] | None,
    *, inserted_this_attempt: bool | None,
) -> dict[str, Any]:
    """Inspect FIRST stored row after an attempted INSERT; never overwrite.

    inserted_this_attempt is DB cursor evidence (True on RETURNING key,
    False if ON CONFLICT DID NOTHING). Even True is NOT an independent audit
    of prior first observation. This pure function never authorizes Forward.
    """
    def outcome(status: str, *, consistent: bool = False) -> dict[str, Any]:
        return {
            "status": status, "storage_consistent": consistent,
            "first_observed_at": None, "first_write_confirmed": False,
            "db_stored_at_readback_consistent": consistent,
            "forward_eligible": False,
        }

    if not isinstance(plan, Mapping) or not isinstance(plan.get("params"), tuple) or len(plan["params"]) != 8:
        return outcome("INVALID_STORAGE_PLAN")
    if type(inserted_this_attempt) is not bool:
        return outcome("INSERT_OUTCOME_UNVERIFIED")
    if not isinstance(frozen, Mapping):
        return outcome("FIRST_WRITE_READBACK_MISSING")
    key, kind, rid, url, start, completed, raw, digest = plan["params"]
    # PostgreSQL DEFAULT now() is transaction-start, never commit/first-sight.
    # This is only an untrusted same-transaction row value, not an audit.
    stored_at = frozen.get("stored_at")
    if type(stored_at) is not datetime:
        return outcome("DB_STORED_AT_MISSING_OR_INVALID")
    try:
        stored_at = _aware_dt(stored_at)
    except (UnverifiedCapture, ValueError, TypeError):
        return outcome("DB_STORED_AT_MISSING_OR_INVALID")
    if stored_at < completed:
        return outcome("DB_STORED_AT_BEFORE_RESPONSE_COMPLETION")
    try:
        stored_raw = frozen.get("raw_bytes")
        if not isinstance(stored_raw, (bytes, memoryview)):
            return outcome("FROZEN_RAW_BYTES_UNAVAILABLE")
        stored_raw = bytes(stored_raw)
        stored_start = _aware_dt(frozen.get("request_started_at"))
        stored_completed = _aware_dt(frozen.get("response_completed_at"))
        same = (
            frozen.get("resource_key") == key
            and frozen.get("source_kind") == kind
            and frozen.get("race_id") == rid
            and frozen.get("source_url") == url
            and stored_start == start and stored_completed == completed
            and frozen.get("raw_sha256") == digest
            and hashlib.sha256(stored_raw).hexdigest() == digest
            and stored_raw == raw
        )
    except (UnverifiedCapture, TypeError, ValueError):
        same = False
    if not same:
        return outcome("FIRST_WRITE_COLLISION_OR_TAMPERING")
    if inserted_this_attempt:
        return outcome("INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED", consistent=True)
    return outcome("EXISTING_IDENTICAL_FIRST_CAPTURE", consistent=True)
