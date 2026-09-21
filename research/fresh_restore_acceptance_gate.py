# -*- coding: utf-8 -*-
"""Pure post-rehearsal acceptance gate for a future Hobby capacity decision.

Consumes only measured rehearsal evidence. It performs no database, filesystem,
network, Railway, archive, or Production mutation.
"""
from __future__ import annotations

from typing import Any

CONTRACT = "v4_fresh_restore_acceptance_evidence_v1"
HOBBY_LIMIT_BYTES = 5_000_000_000


class FreshRestoreAcceptanceError(ValueError):
    pass


def _nonnegative_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise FreshRestoreAcceptanceError(f"{field} must be a non-negative integer")
    return value


def evaluate_acceptance(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FreshRestoreAcceptanceError("evidence must be an object")
    if data.get("contract") != CONTRACT:
        raise FreshRestoreAcceptanceError("unexpected acceptance contract")
    if data.get("target_production") is not False:
        raise FreshRestoreAcceptanceError("measured rehearsal target must be non-Production")
    if data.get("restore_completed") is not True:
        raise FreshRestoreAcceptanceError("fresh restore must be completed")

    observed_db = _nonnegative_int(
        data.get("observed_database_bytes"),
        field="observed_database_bytes",
    )
    observed_fs = _nonnegative_int(
        data.get("observed_target_filesystem_bytes"),
        field="observed_target_filesystem_bytes",
    )
    if observed_fs <= 0:
        raise FreshRestoreAcceptanceError(
            "observed_target_filesystem_bytes must be physically measured"
        )
    if observed_fs < observed_db:
        raise FreshRestoreAcceptanceError(
            "target filesystem bytes cannot be below database bytes"
        )

    headroom = data.get("headroom_policy")
    if not isinstance(headroom, dict) or headroom.get("frozen") is not True:
        raise FreshRestoreAcceptanceError("headroom policy must be frozen")
    limit = _nonnegative_int(headroom.get("volume_limit_bytes"), field="volume_limit_bytes")
    reserve = _nonnegative_int(
        headroom.get("required_reserve_bytes"),
        field="required_reserve_bytes",
    )
    daily_growth = _nonnegative_int(
        headroom.get("measured_daily_growth_bytes"),
        field="measured_daily_growth_bytes",
    )
    horizon = _nonnegative_int(
        headroom.get("growth_horizon_days"),
        field="growth_horizon_days",
    )
    if limit != HOBBY_LIMIT_BYTES:
        raise FreshRestoreAcceptanceError(
            "Hobby volume limit must use conservative 5,000,000,000-byte cap"
        )
    if reserve <= 0 or horizon <= 0:
        raise FreshRestoreAcceptanceError("reserve and growth horizon must be positive")
    growth_horizon_bytes = daily_growth * horizon
    if reserve < growth_horizon_bytes:
        raise FreshRestoreAcceptanceError(
            "required reserve is below measured growth horizon"
        )

    checks = data.get("equivalence_checks")
    if not isinstance(checks, dict):
        raise FreshRestoreAcceptanceError("equivalence_checks missing")
    required_true = (
        "schema_equivalent",
        "indexes_constraints_extensions_equivalent",
        "retained_row_counts_equivalent",
        "representative_digests_equivalent",
        "application_readonly_smoke_pass",
        "archive_consumer_smoke_pass",
    )
    for field in required_true:
        if checks.get(field) is not True:
            raise FreshRestoreAcceptanceError(f"{field} must be true")

    approvals = data.get("approvals")
    if not isinstance(approvals, dict):
        raise FreshRestoreAcceptanceError("approvals missing")
    if approvals.get("production_migration_authorized") is not False:
        raise FreshRestoreAcceptanceError(
            "rehearsal evidence must not authorize Production migration"
        )

    projected_required_bytes = observed_fs + reserve
    capacity_fit = projected_required_bytes <= limit

    return {
        "contract": "v4_fresh_restore_acceptance_result_v1",
        "observed_database_bytes": observed_db,
        "observed_target_filesystem_bytes": observed_fs,
        "required_reserve_bytes": reserve,
        "growth_horizon_bytes": growth_horizon_bytes,
        "projected_required_bytes": projected_required_bytes,
        "volume_limit_bytes": limit,
        "hobby_capacity_fit": capacity_fit,
        "decision": (
            "PASS_FRESH_RESTORE_CAPACITY_AND_EQUIVALENCE"
            if capacity_fit
            else "FAIL_FRESH_RESTORE_CAPACITY_HEADROOM"
        ),
        "automatic_plan_change_allowed": False,
        "production_migration_authorized": False,
        "purchase_action": False,
    }
