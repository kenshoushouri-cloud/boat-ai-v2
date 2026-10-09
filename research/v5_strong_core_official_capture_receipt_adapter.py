# -*- coding: utf-8 -*-
"""Undeployed research-only adapter from immutable SOURCE receipts to freeze plan.

Current realtime snapshot_at and official K result fetched_at are mutable and
MUST NOT be passed as first_observed_at. This adapter accepts ONLY separately
retained raw capture receipts, including first-write/readback evidence.
A digest proves internal byte consistency, NOT that a website was official,
a page parser correctly extracted its fields or a DB first-write really took
place. Those facts require independent collector/readback verification.

This module has no I/O or runtime integration and never authorizes Forward
eligibility, Production, LINE or purchase.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
from datetime import datetime
from typing import Any, Mapping

from research.v5_strong_core_entry_recent_form_predeadline_gate import _aware_time
from research.v5_strong_core_entry_form_freeze_plan import (
    EvidenceNotReady, prepare_entry_form_freeze,
)


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise EvidenceNotReady(reason)


def _raw_receipt(value: Any, *, source: str, at_field: str,
                 no_later_than: datetime) -> Mapping[str, Any]:
    """Validate a proposed immutable capture; not proof of external origin."""
    _need(isinstance(value, Mapping), "SOURCE_RECEIPT_MISSING")
    _need(value.get("source") == source, "SOURCE_RECEIPT_WRONG_SOURCE")
    _need(value.get("first_write_confirmed") is True
          and value.get("readback_confirmed") is True,
          "FIRST_WRITE_READBACK_UNPROVEN")
    ref = value.get("receipt_ref")
    _need(isinstance(ref, str) and bool(ref.strip()), "SOURCE_RECEIPT_REF_MISSING")
    observed = _aware_time(value.get(at_field))
    _need(observed is not None and observed <= no_later_than,
          "SOURCE_RECEIPT_MISSING_OR_LATE_TIME")
    raw = value.get("raw_base64")
    _need(isinstance(raw, str) and bool(raw), "SOURCE_RAW_BYTES_MISSING")
    try:
        payload = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EvidenceNotReady("SOURCE_RAW_BYTES_INVALID") from exc
    _need(bool(payload), "SOURCE_RAW_BYTES_EMPTY")
    digest = hashlib.sha256(payload).hexdigest()
    _need(value.get("raw_sha256") == digest
          and value.get("readback_sha256") == digest,
          "SOURCE_DIGEST_OR_READBACK_MISMATCH")
    return value


def prepare_from_official_capture_receipts(
    snapshot: Mapping[str, Any],
    *,
    beforeinfo_receipt: Mapping[str, Any],
    racelist_receipt: Mapping[str, Any],
    history_scan_receipts: list[Mapping[str, Any]],
    k_result_receipts: list[Mapping[str, Any]],
    official_deadline_at: Any,
    prediction_cutoff_at: Any,
) -> dict[str, Any]:
    """Build an OFFLINE plan from alleged first-observation source receipts.

    External caller MUST verify actual first-write SQL/readback, capture-source
    URLs and parser extraction. No existing mutable table is proof. The
    resulting plan always has forward_eligible=False.
    """
    _need(isinstance(snapshot, Mapping), "SNAPSHOT_MISSING")
    built = _aware_time(snapshot.get("feature_built_at"))
    captured = _aware_time(snapshot.get("captured_at"))
    cutoff = _aware_time(prediction_cutoff_at)
    _need(built is not None and captured is not None and cutoff is not None,
          "FREEZE_CLOCK_NOT_VERIFIED")
    _raw_receipt(beforeinfo_receipt, source="official_beforeinfo",
                 at_field="first_observed_at", no_later_than=captured)
    _need(_aware_time(beforeinfo_receipt["first_observed_at"]) == captured,
          "BEFOREINFO_OBSERVATION_NOT_CAPTURE_TIME")
    _raw_receipt(racelist_receipt, source="official_racelist",
                 at_field="first_observed_at", no_later_than=built)

    entries = snapshot.get("entries")
    _need(isinstance(entries, (list, tuple)) and len(entries) == 6,
          "NO_SIX_ENTRY_SNAPSHOT")
    # Caller independently verifies this parsed roster against the raw
    # immutable racelist receipt. The adapter can only compare its declaration.
    declared_roster = racelist_receipt.get("parsed_lane_racer_ids")
    _need(isinstance(declared_roster, (list, tuple))
          and all(isinstance(x, (list, tuple)) and len(x) == 2 for x in declared_roster),
          "OFFICIAL_RACELIST_ROSTER_NOT_ATTESTED")
    roster = [(e.get("lane"), e.get("racer_number")) for e in entries
              if isinstance(e, Mapping)]
    _need(len(roster) == 6 and sorted(roster) == sorted(map(tuple, declared_roster)),
          "OFFICIAL_RACELIST_ENTRY_MISMATCH")

    prepared = copy.deepcopy(dict(snapshot))
    racers = {e.get("racer_number") for e in prepared["entries"]}
    _need(all(type(x) is int and x > 0 for x in racers) and len(racers) == 6,
          "SIX_RACER_IDS_NOT_VERIFIED")
    _need(isinstance(history_scan_receipts, list)
          and len(history_scan_receipts) == 6, "NO_COMPLETE_SCAN_RECEIPTS")
    _need(isinstance(k_result_receipts, list), "K_RESULT_RECEIPTS_MISSING")

    scans = []
    for scan in history_scan_receipts:
        _raw_receipt(scan, source="official_k_file",
                     at_field="checked_at", no_later_than=built)
        _need(scan.get("complete_asof") is True
              and type(scan.get("racer_number")) is int
              and scan["racer_number"] in racers,
              "HISTORY_SCAN_COVERAGE_UNVERIFIED")
        scans.append({k: scan[k] for k in
                      ("source", "racer_number", "checked_at", "receipt_ref",
                       "complete_asof", "result_race_ids") if k in scan})

    observed_results = {}
    results = []
    for rec in k_result_receipts:
        _raw_receipt(rec, source="official_k_file",
                     at_field="first_observed_at", no_later_than=built)
        key = (rec.get("racer_number"), rec.get("race_id"))
        _need(type(key[0]) is int and key[0] in racers
              and isinstance(key[1], str) and bool(key[1])
              and key not in observed_results, "K_RESULT_IDENTITY_UNVERIFIED")
        observed_results[key] = rec["first_observed_at"]
        results.append({k: rec[k] for k in
                        ("source", "racer_number", "race_id",
                         "first_observed_at", "receipt_ref")})

    # No publication timestamp is inferred from target race date, prior race
    # date, fetched_at or updated_at. Only first OBSERVED capture time is used.
    for e in prepared["entries"]:
        hist = e.get("recent_form")
        _need(isinstance(hist, list), "HISTORY_NOT_MATERIALIZED")
        for item in hist:
            _need(isinstance(item, dict), "INVALID_HISTORY_ITEM")
            key = (e.get("racer_number"), item.get("race_id"))
            _need(key in observed_results, "K_OBSERVATION_NOT_AVAILABLE")
            observed_at = observed_results[key]
            existing = item.get("published_at")
            _need(existing is None or _aware_time(existing) == _aware_time(observed_at),
                  "CONFLICTING_K_PUBLICATION_ASSERTION")
            item["published_at"] = observed_at

    plan = prepare_entry_form_freeze(
        prepared,
        entry_receipt={k: beforeinfo_receipt[k] for k in
                       ("source", "first_observed_at", "receipt_ref")},
        history_scan_receipts=scans,
        official_result_receipts=results,
        official_deadline_at=official_deadline_at,
        prediction_cutoff_at=prediction_cutoff_at,
    )
    plan["limitations"] = (
        "PREPARED ONLY: raw hashes/flags are supplied assertions; independently "
        "audit official fetch, roster parser, first-write proof, scan completeness "
        "and stored DB readback before any Forward eligibility. "
        "published_at denotes first OBSERVED K receipt, NOT official release."
    )
    plan["forward_eligible"] = False
    return plan
