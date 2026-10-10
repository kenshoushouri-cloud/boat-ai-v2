# -*- coding: utf-8 -*-
"""V5 only: offline preflight for a future positive-start source diagnostic.

NO HTTP, storage, CI dispatch, Railway or Production entry point. Even a
passing synthetic policy check NEVER grants live GET, first-write or Forward.
The production reviewed-schema and race-specific approval registries are
intentionally EMPTY until separate, independent official-source review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
RACE_PATTERN = re.compile(r"^(20\d{6})_(0[1-9]|1[0-9]|2[0-4])_(0[1-9]|1[0-2])$")
COMPLETED_PROBES = frozenset({"20261010_03_01"})
OFFICIAL_BASE = "https://www.boatrace.jp/owpc/pc/race/"
ALLOWED_ENDPOINTS = frozenset({"racelist", "beforeinfo"})
MAX_RACES = 1
MAX_GETS = 2


@dataclass(frozen=True, slots=True)
class ReviewedSourceSchema:
    """Fixture/review record: declarations do not independently prove facts."""

    schema_id: str
    official_documentation_url: str
    independent_review_ref: str
    affirmative_status_field: str
    lane_field: str
    racer_registration_field: str
    candidate_endpoint: str


@dataclass(frozen=True, slots=True)
class ApprovedRaceScope:
    """An exact, independently reviewed race+source+deadline approval entry."""

    race_id: str
    schema_id: str
    independent_review_ref: str
    manual_approval_ref: str
    official_deadline_at: datetime
    decision_cutoff_at: datetime
    exact_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreflightResult:
    reason_code: str
    race_id: str | None = None
    preflight_conditions_met: bool = False
    planned_gets: int = 0
    # Immutable DENY flags, including for synthetic passing-policy fixtures.
    diagnostic_live_get_authorized: bool = field(default=False, init=False)
    six_active_starts_confirmed: bool = field(default=False, init=False)
    beforeinfo_first_write_eligible: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    persistence_performed: bool = field(default=False, init=False)


# Deliberately NOT a caller-supplied approval/active Boolean. Both registries
# must remain empty until a separately reviewed, race-specific promotion.
_PRODUCTION_REVIEWED_SCHEMAS: Mapping[str, ReviewedSourceSchema] = MappingProxyType({})
_PRODUCTION_APPROVED_SCOPES: frozenset[ApprovedRaceScope] = frozenset()


def _time(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value


def _expected_urls(race_id: str, candidate: str) -> tuple[str, ...]:
    date, venue, number = race_id.split("_")
    def url(endpoint: str) -> str:
        return f"{OFFICIAL_BASE}{endpoint}?rno={int(number)}&jcd={venue}&hd={date}"
    return (url(candidate),) if candidate == "racelist" else (
        url("beforeinfo"), url("racelist")
    )


def _review_preflight(
    *,
    race_ids: object,
    schema_id: object,
    official_deadline_at: object,
    decision_cutoff_at: object,
    observation_start_at: object,
    requested_urls: object,
    reviewed_schemas: Mapping[str, ReviewedSourceSchema],
    approved_scopes: frozenset[ApprovedRaceScope],
) -> PreflightResult:
    """Pure review engine; fixture registries are permitted for OFFLINE tests."""
    if (not isinstance(race_ids, (tuple, list)) or len(race_ids) != MAX_RACES
            or not isinstance(race_ids[0], str)):
        return PreflightResult("ONE_RACE_REQUIRED")
    race_id = race_ids[0]
    match = RACE_PATTERN.fullmatch(race_id)
    if match is None:
        return PreflightResult("INVALID_RACE_ID")
    try:
        date = datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return PreflightResult("INVALID_RACE_DATE")
    if race_id in COMPLETED_PROBES:
        return PreflightResult("PREVIOUSLY_PROBED_RACE_FORBIDDEN", race_id)
    if not isinstance(schema_id, str) or not schema_id:
        return PreflightResult("NO_AUTHORITATIVE_SCHEMA", race_id)
    schema = reviewed_schemas.get(schema_id)
    if (not isinstance(schema, ReviewedSourceSchema)
            or schema.schema_id != schema_id
            or schema.candidate_endpoint not in ALLOWED_ENDPOINTS
            or not schema.official_documentation_url.startswith("https://www.boatrace.jp/")
            or not all(isinstance(v, str) and v.strip() for v in (
                schema.independent_review_ref, schema.affirmative_status_field,
                schema.lane_field, schema.racer_registration_field
            ))):
        return PreflightResult("NO_AUTHORITATIVE_SCHEMA", race_id)
    deadline = _time(official_deadline_at)
    cutoff = _time(decision_cutoff_at)
    start = _time(observation_start_at)
    if any(t is None for t in (deadline, cutoff, start)):
        return PreflightResult("OFFICIAL_DEADLINE_UNVERIFIED", race_id)
    if (deadline.astimezone(JST).date() != date
            or cutoff.astimezone(JST).date() != date
            or start.astimezone(JST).date() != date
            or not start < cutoff < deadline):
        return PreflightResult("OFFICIAL_DEADLINE_UNVERIFIED", race_id)
    if not deadline - timedelta(minutes=15) <= start <= deadline - timedelta(minutes=8):
        return PreflightResult("OUTSIDE_PREDEADLINE_WINDOW", race_id)
    if (not isinstance(requested_urls, (tuple, list))
            or not 1 <= len(requested_urls) <= MAX_GETS
            or not all(isinstance(url, str) for url in requested_urls)):
        return PreflightResult("INVALID_GET_SCOPE", race_id)
    required_urls = _expected_urls(race_id, schema.candidate_endpoint)
    if tuple(requested_urls) != required_urls:
        return PreflightResult("SOURCE_URL_NOT_EXACTLY_ALLOWLISTED", race_id)
    scope_match = any(
        isinstance(scope, ApprovedRaceScope)
        and scope.race_id == race_id
        and scope.schema_id == schema_id
        and scope.independent_review_ref == schema.independent_review_ref
        and isinstance(scope.manual_approval_ref, str)
        and bool(scope.manual_approval_ref.strip())
        and _time(scope.official_deadline_at) == deadline
        and _time(scope.decision_cutoff_at) == cutoff
        and scope.exact_urls == required_urls
        for scope in approved_scopes
    )
    if not scope_match:
        return PreflightResult("RACE_SPECIFIC_MANUAL_REVIEW_MISSING", race_id)
    # An offline test can reach this result only with injected synthetic policy.
    # It is NEVER a network execution token nor an official status attestation.
    return PreflightResult("PREFLIGHT_ONLY_NOT_LIVE_AUTHORIZATION", race_id,
                           preflight_conditions_met=True,
                           planned_gets=len(required_urls))


def review_positive_start_diagnostic_preflight(
    *, race_ids: object, schema_id: object, official_deadline_at: object,
    decision_cutoff_at: object, observation_start_at: object,
    requested_urls: object,
) -> PreflightResult:
    """Production entry point: OFF by default; no approved source/race today."""
    return _review_preflight(
        race_ids=race_ids, schema_id=schema_id,
        official_deadline_at=official_deadline_at,
        decision_cutoff_at=decision_cutoff_at,
        observation_start_at=observation_start_at,
        requested_urls=requested_urls,
        reviewed_schemas=_PRODUCTION_REVIEWED_SCHEMAS,
        approved_scopes=_PRODUCTION_APPROVED_SCOPES,
    )
