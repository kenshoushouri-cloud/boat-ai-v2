# -*- coding: utf-8 -*-
"""UNDEPLOYED research-only first-write-wins capture/storage contract.

This module does NOT read a DB, fetch official webpages, write data, or certify
that independently supplied evidence receipts are genuine. The external
collector must capture actual official entry and K-result observations and
retain immutable source receipts. The historical recent_form backfill and
upserted realtime entry tables alone are NOT eligible inputs.

`published_at` in the existing pure gate is treated here as *first verified
observation time* of an official K result, NOT an invented official publish
timestamp. Never synthesize it from a race date or DB updated_at.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Mapping

from research.v5_strong_core_entry_recent_form_predeadline_gate import (
    FREEZE_CONTRACT, check_frozen_entries_recent_form, _aware_time,
)

TABLE = "research_v5_entry_form_first_write"
# DDL and SQL are PLAN STRINGS. Nothing runs them in this module.
DDL = """
CREATE TABLE IF NOT EXISTS research_v5_entry_form_first_write (
    race_id text PRIMARY KEY,
    race_date date NOT NULL,
    captured_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    payload_sha256 text NOT NULL CHECK (length(payload_sha256) = 64),
    entry_receipt_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
)
"""
INSERT_IF_ABSENT = """
INSERT INTO research_v5_entry_form_first_write
    (race_id,race_date,captured_at,payload,payload_sha256,entry_receipt_ref)
VALUES (%s,%s,%s,%s::jsonb,%s,%s)
ON CONFLICT (race_id) DO NOTHING
RETURNING race_id,payload_sha256
"""
READ_FROZEN = """
SELECT race_id,payload,payload_sha256,entry_receipt_ref
FROM research_v5_entry_form_first_write WHERE race_id=%s
"""


class EvidenceNotReady(ValueError):
    """An unverified source/time/coverage claim must never become a packet."""


def _require(cond: bool, reason: str) -> None:
    if not cond:
        raise EvidenceNotReady(reason)


def _valid_receipt(receipt: Any, source: str, at_field: str, before: datetime) -> bool:
    if not isinstance(receipt, Mapping) or receipt.get("source") != source:
        return False
    if not isinstance(receipt.get("receipt_ref"), str) or not receipt["receipt_ref"].strip():
        return False
    at = _aware_time(receipt.get(at_field))
    return at is not None and at <= before


def _json_normalize(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError("Only JSON and ISO timestamps are accepted")


def prepare_entry_form_freeze(
    snapshot: Mapping[str, Any],
    *,
    entry_receipt: Mapping[str, Any],
    history_scan_receipts: list[Mapping[str, Any]],
    official_result_receipts: list[Mapping[str, Any]],
    official_deadline_at: Any,
    prediction_cutoff_at: Any,
) -> dict[str, Any]:
    """Prepare a proposed insert, never execute or assert operational coverage.

    Receipt fields are caller assertions requiring independent verification:
      entry: source=official_beforeinfo, first_observed_at, receipt_ref
      scans: source=official_k_file, racer_number, checked_at, receipt_ref,
             complete_asof=True, result_race_ids matching the 0..5 history IDs
      results: source=official_k_file, racer_number, race_id,
               first_observed_at, receipt_ref

    Even a valid proposal must be persisted by ON CONFLICT DO NOTHING and
    checked against the actual stored first-write row before forward use.
    """
    _require(isinstance(snapshot, Mapping), "MISSING_SNAPSHOT")
    built = _aware_time(snapshot.get("feature_built_at"))
    captured = _aware_time(snapshot.get("captured_at"))
    _require(built is not None and captured is not None, "MISSING_CAPTURE_TIME")
    _require(
        _valid_receipt(entry_receipt, "official_beforeinfo", "first_observed_at", captured)
        and _aware_time(entry_receipt["first_observed_at"]) == captured,
        "MISSING_FIRST_OFFICIAL_ENTRY_OBSERVATION",
    )

    entries = snapshot.get("entries")
    _require(isinstance(entries, (tuple, list)) and len(entries) == 6, "INCOMPLETE_ENTRY_SET")
    _require(isinstance(history_scan_receipts, list), "MISSING_HISTORY_SCAN_RECEIPTS")
    _require(isinstance(official_result_receipts, list), "MISSING_K_RESULT_RECEIPTS")

    scans: dict[int, Mapping[str, Any]] = {}
    for receipt in history_scan_receipts:
        _require(
            _valid_receipt(receipt, "official_k_file", "checked_at", built)
            and receipt.get("complete_asof") is True
            and type(receipt.get("racer_number")) is int
            and receipt["racer_number"] not in scans
            and isinstance(receipt.get("result_race_ids"), list),
            "UNVERIFIED_PRIOR_HISTORY_SCAN",
        )
        scans[receipt["racer_number"]] = receipt

    results: dict[tuple[int, str], Mapping[str, Any]] = {}
    for receipt in official_result_receipts:
        key = (receipt.get("racer_number"), receipt.get("race_id"))
        _require(
            _valid_receipt(receipt, "official_k_file", "first_observed_at", built)
            and type(key[0]) is int and isinstance(key[1], str) and bool(key[1])
            and key not in results,
            "UNVERIFIED_K_RESULT_OBSERVATION",
        )
        results[key] = receipt

    referenced: set[tuple[int, str]] = set()
    racers: set[int] = set()
    for entry in entries:
        _require(isinstance(entry, Mapping), "INVALID_ENTRY")
        racer = entry.get("racer_number")
        _require(type(racer) is int and racer not in racers, "DUPLICATE_OR_BAD_RACER")
        racers.add(racer)
        hist = entry.get("recent_form")
        _require(isinstance(hist, (list, tuple)), "MISSING_RECENT_FORM")
        _require(racer in scans, "MISSING_PRIOR_HISTORY_SCAN")
        ids = [item.get("race_id") for item in hist if isinstance(item, Mapping)]
        _require(len(ids) == len(hist) and scans[racer]["result_race_ids"] == ids,
                 "HISTORY_SCAN_SET_MISMATCH")
        for item in hist:
            key = (racer, item.get("race_id"))
            _require(key in results, "PRIOR_RESULT_OBSERVATION_MISSING")
            observed = _aware_time(results[key]["first_observed_at"])
            supplied = _aware_time(item.get("published_at"))
            _require(supplied is not None and supplied == observed,
                     "UNSUPPORTED_PRIOR_PUBLICATION_TIME")
            _require(_aware_time(scans[racer]["checked_at"]) >= observed,
                     "SCAN_PRECEDES_OFFICIAL_RESULT_OBSERVATION")
            referenced.add(key)

    _require(set(scans) == racers, "EXTRA_OR_MISSING_HISTORY_SCAN")
    _require(set(results) == referenced, "EXTRA_OR_MISSING_K_RECEIPT")

    # This can only validate the *proposed* evidence claims; actual immutable
    # capture must be established via external evidence and a DB readback.
    gate = check_frozen_entries_recent_form(
        str(snapshot.get("race_id") or ""), snapshot.get("race_date"), snapshot,
        official_deadline_at=official_deadline_at,
        prediction_cutoff_at=prediction_cutoff_at,
        immutable_provenance_verified=True,
    )
    _require(gate["eligible"], "ENTRY_GATE:" + gate["reason"])

    try:
        payload = json.loads(json.dumps(snapshot, default=_json_normalize,
                                        allow_nan=False, ensure_ascii=False))
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EvidenceNotReady("NONCANONICAL_PAYLOAD") from exc
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return {
        "status": "PREPARED_ONLY_NO_DB_WRITE",
        "race_id": payload["race_id"],
        "digest": digest,
        "sql": INSERT_IF_ABSENT,
        "params": (payload["race_id"], payload["race_date"], payload["captured_at"],
                   encoded, digest, entry_receipt["receipt_ref"]),
        "read_sql": READ_FROZEN,
        "read_params": (payload["race_id"],),
        "forward_eligible": False,
        "limitations": "External first-observation receipt authenticity and DB first-write readback unverified",
    }


def verify_frozen_readback(proposal: Mapping[str, Any], persisted: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a row read from the dedicated frozen table; never mutate it.

    Matching digest supports storage consistency only. It DOES NOT independently
    prove that a source receipt was real or authorize strong-core forward BUY.
    """
    if not isinstance(persisted, Mapping):
        return {"match": False, "reason": "FROZEN_ROW_MISSING"}
    payload = persisted.get("payload")
    try:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":"), allow_nan=False)
        actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        return {"match": False, "reason": "INVALID_STORED_JSON"}
    ok = (
        persisted.get("race_id") == proposal.get("race_id")
        and actual == persisted.get("payload_sha256") == proposal.get("digest")
        and persisted.get("entry_receipt_ref") == proposal.get("params", (None,) * 6)[5]
    )
    return {"match": bool(ok),
            "reason": "STORAGE_DIGEST_MATCH_SOURCE_STILL_UNVERIFIED" if ok else "FIRST_WRITE_CONFLICT_OR_TAMPERING"}
