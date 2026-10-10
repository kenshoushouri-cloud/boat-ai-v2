# -*- coding: utf-8 -*-
"""Pure V5 offline summary of a positive-start diagnostic preflight.

No network/session/GET/DB/filesystem/production calls. This is NOT a live
execution plan, status attestation, first-observation receipt or BUY signal.
Even a synthetically passing preflight produces a permanently blocked report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from v5.positive_start_diagnostic_preflight import (
    COMPLETED_PROBES, MAX_GETS, PreflightResult, RACE_PATTERN,
)

_KNOWN_DENIALS = frozenset({
    "ONE_RACE_REQUIRED", "INVALID_RACE_ID", "INVALID_RACE_DATE",
    "PREVIOUSLY_PROBED_RACE_FORBIDDEN", "NO_AUTHORITATIVE_SCHEMA",
    "OFFICIAL_DEADLINE_UNVERIFIED", "OUTSIDE_PREDEADLINE_WINDOW",
    "INVALID_GET_SCOPE", "SOURCE_URL_NOT_EXACTLY_ALLOWLISTED",
    "RACE_SPECIFIC_MANUAL_REVIEW_MISSING",
})
_SYNTHETIC_PREVIEW = "PREFLIGHT_ONLY_NOT_LIVE_AUTHORIZATION"
_INVALID = "UNTRUSTED_PREFLIGHT_RESULT"


@dataclass(frozen=True, slots=True)
class OfflineDiagnosticReport:
    """Safe, anonymous race-scope summary. Every capability flag is DENY."""

    reason_code: str
    race_id: str | None = None
    preflight_conditions_met: bool = False
    proposed_get_count: int = 0
    contract: str = field(default="V5_POSITIVE_START_OFFLINE_REPORT_V1", init=False)
    status: str = field(default="HARD_HOLD_NO_LIVE_DIAGNOSTIC", init=False)
    attempted_gets: int = field(default=0, init=False)
    diagnostic_live_get_authorized: bool = field(default=False, init=False)
    source_bytes_independently_authenticated: bool = field(default=False, init=False)
    original_first_observation_proven: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    persistence_performed: bool = field(default=False, init=False)

    def anonymous_summary(self) -> dict[str, str | int | bool | None]:
        """Only fixed, nonidentity fields; no URL, racer ID, raw body or text."""
        return {
            "contract": self.contract, "status": self.status,
            "reason_code": self.reason_code, "race_id": self.race_id,
            "preflight_conditions_met": self.preflight_conditions_met,
            "proposed_get_count": self.proposed_get_count,
            "attempted_gets": self.attempted_gets,
            "diagnostic_live_get_authorized": self.diagnostic_live_get_authorized,
            "source_bytes_independently_authenticated":
                self.source_bytes_independently_authenticated,
            "original_first_observation_proven":
                self.original_first_observation_proven,
            "six_active_starts_confirmed": self.six_active_starts_confirmed,
            "beforeinfo_first_write_eligible": self.beforeinfo_first_write_eligible,
            "forward_eligible": self.forward_eligible,
            "persistence_performed": self.persistence_performed,
        }


def _safe_race_id(value: object) -> str | None:
    if not isinstance(value, str) or not RACE_PATTERN.fullmatch(value):
        return None
    try:
        datetime.strptime(value[:8], "%Y%m%d")
    except ValueError:
        return None
    return value


def prepare_offline_diagnostic_report(preflight: object) -> OfflineDiagnosticReport:
    """Consume an exact frozen preflight result; ALWAYS deny live operations.

    Values from any caller (including manually fabricated dataclass instances)
    are never permission to fetch, persist, mark active, forward or purchase.
    A valid synthetic preview is only a count of possible future GETs.
    """
    if type(preflight) is not PreflightResult:
        return OfflineDiagnosticReport(_INVALID)
    if (preflight.diagnostic_live_get_authorized is not False
            or preflight.six_active_starts_confirmed is not False
            or preflight.beforeinfo_first_write_eligible is not False
            or preflight.forward_eligible is not False
            or preflight.persistence_performed is not False):
        return OfflineDiagnosticReport(_INVALID)
    race_id = _safe_race_id(preflight.race_id)
    reason = preflight.reason_code
    if reason == _SYNTHETIC_PREVIEW:
        if (race_id is not None and race_id not in COMPLETED_PROBES
                and preflight.preflight_conditions_met is True
                and type(preflight.planned_gets) is int
                and 1 <= preflight.planned_gets <= MAX_GETS):
            return OfflineDiagnosticReport(
                reason, race_id, preflight_conditions_met=True,
                proposed_get_count=preflight.planned_gets,
            )
        return OfflineDiagnosticReport(_INVALID)
    if (reason in _KNOWN_DENIALS and preflight.preflight_conditions_met is False
            and type(preflight.planned_gets) is int
            and preflight.planned_gets == 0):
        return OfflineDiagnosticReport(reason, race_id)
    return OfflineDiagnosticReport(_INVALID)
