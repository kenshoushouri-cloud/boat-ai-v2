# -*- coding: utf-8 -*-
"""Opt-in, offline-only odds capture PLAN. Never performs GET/SQL/BUY.

The caller-supplied receipt and raw HTML are untrusted mock evidence. A
successful binder comparison is byte/price parity, NOT an official capture,
first-write, published-before-cutoff proof or permission to place a wager.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from collections.abc import Mapping

from v5.offline_odds_raw_ticket_binder import (
    MockRawOddsCapture, bind_offline_odds_raw_tickets,
)

PROPOSAL_CONTRACT = 'V5_ODDS_CAPTURE_SHADOW_PROPOSAL_V1'
BINDER_PASS = 'MOCK_RAW_120_TICKET_PARITY_ONLY_HARD_HOLD'


@dataclass(frozen=True, slots=True)
class ProvisionalOddsReceipt:
    contract: str
    race_id: str
    source_url: str
    response_completed_at: datetime
    raw_sha256: str
    first_observed_at: None = None
    first_write_confirmed: bool = False
    readback_confirmed: bool = False
    forward_eligible: bool = False
    buy_eligible: bool = False
    storage_executed: bool = False
    http_executed: bool = False


@dataclass(frozen=True, slots=True)
class OfflineOddsCapturePlan:
    reason: str
    race_id: str = ''
    source_url: str = ''
    raw_sha256: str = ''
    parsed_tickets_sha256: str = ''
    parsed_ticket_count: int = 0
    mock_raw_parity: bool = False
    no_get: bool = field(default=True, init=False)
    no_sql: bool = field(default=True, init=False)
    no_write: bool = field(default=True, init=False)
    source_authenticated: bool = field(default=False, init=False)
    independently_verified_first_write: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    selection_eligible: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def prepare_offline_odds_capture_plan(
    *, expected_race_id: object, capture: object, claimed_ticket_odds: object,
    provisional_receipt: object, enabled: bool = False,
) -> OfflineOddsCapturePlan:
    """Return a frozen, non-executable shadow plan only after mock parity.

    No integration with real official transport, its URL allowlist, or DB.
    Never infer real observed-before-cutoff status from supplied timestamps.
    """
    def hold(reason: str) -> OfflineOddsCapturePlan:
        return OfflineOddsCapturePlan(reason)

    if enabled is not True:
        return hold('OFFLINE_ODDS_CAPTURE_DISABLED')
    if type(capture) is not MockRawOddsCapture or type(provisional_receipt) is not ProvisionalOddsReceipt:
        return hold('PROVISIONAL_ODDS_RECEIPT_REQUIRED')
    p = provisional_receipt
    if (p.first_observed_at is not None or p.first_write_confirmed is not False
            or p.readback_confirmed is not False or p.forward_eligible is not False
            or p.buy_eligible is not False or p.storage_executed is not False
            or p.http_executed is not False):
        return hold('PREMATURE_ODDS_CAPTURE_AUTHORITY_CLAIM')
    if (p.contract != PROPOSAL_CONTRACT
            or type(p.race_id) is not str or p.race_id != expected_race_id
            or type(p.source_url) is not str or p.source_url != capture.requested_url
            or type(p.raw_sha256) is not str or p.raw_sha256 != capture.raw_sha256
            or type(p.response_completed_at) is not datetime
            or p.response_completed_at != capture.response_completed_at):
        return hold('PROVISIONAL_RECEIPT_IDENTITY_OR_DIGEST_MISMATCH')
    # Existing unchanged parser + binder reparse the exact source bytes.
    proof = bind_offline_odds_raw_tickets(expected_race_id, capture, claimed_ticket_odds)
    if (proof.reason != BINDER_PASS or proof.mock_raw_ticket_parity is not True
            or proof.checked_ticket_count != 120 or proof.race_id != expected_race_id
            or any(getattr(proof, key, None) is not False for key in (
                'original_official_http_verified', 'independently_authenticated_receipt',
                'real_first_observed_verified', 'six_active_starts_confirmed',
                'selection_eligible', 'beforeinfo_first_write_eligible',
                'forward_eligible', 'buy_eligible'))):
        return hold('ODDS_RAW_BINDER_' + proof.reason if type(proof.reason) is str
                    and proof.reason != BINDER_PASS and proof.reason.isupper()
                    and len(proof.reason) < 100
                    else 'UNVERIFIED_ODDS_RAW_BINDER')
    if (not isinstance(claimed_ticket_odds, Mapping)
            or len(claimed_ticket_odds) != 120
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   or value <= 0 for value in claimed_ticket_odds.values())):
        return hold('INVALID_CLAIMED_ODDS_DIGEST_INPUT')
    # SHA covers exact canonical ticket + float representation; the binder
    # verified these values match the original bytes, not any fallback table.
    material = json.dumps(
        [(ticket, format(float(value), '.17g'))
         for ticket, value in sorted(claimed_ticket_odds.items())],
        ensure_ascii=True, separators=(',', ':'), allow_nan=False,
    ).encode('ascii')
    digest = hashlib.sha256(material).hexdigest()
    return OfflineOddsCapturePlan(
        'ODDS_CAPTURE_PLAN_SHADOW_ONLY', expected_race_id,
        capture.requested_url, capture.raw_sha256, digest, 120, True,
    )
