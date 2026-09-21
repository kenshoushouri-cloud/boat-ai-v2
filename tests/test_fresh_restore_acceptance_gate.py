# -*- coding: utf-8 -*-
import hashlib

import pytest

from research.fresh_restore_acceptance_gate import (
    FreshRestoreAcceptanceError,
    evaluate_acceptance,
)


def rehearsal_manifest():
    boundary = "race_date >= frozen_cutoff"
    return {
        "contract": "v4_fresh_restore_rehearsal_manifest_v1",
        "source": {
            "main_sha": "1" * 40,
            "production_read_only": True,
            "destructive_operations": False,
        },
        "target": {
            "production": False,
            "ephemeral": True,
            "postgres_major": 17,
        },
        "online_retention": {
            "frozen": True,
            "tables": [
                {"table": "v2_races", "mode": "keep_all"},
                {"table": "v2_result_entries", "mode": "keep_all"},
                {
                    "table": "v2_odds_trifecta",
                    "mode": "bounded",
                    "boundary": boundary,
                    "boundary_sha256": hashlib.sha256(
                        boundary.encode("utf-8")
                    ).hexdigest(),
                },
            ],
            "protected_evidence_tables": ["v2_races", "v2_result_entries"],
        },
        "archive_recovery": {
            "primary_archive_verified": True,
            "second_recovery_layer_verified": True,
            "excluded_partitions": [
                {"partition_id": "v2_odds_trifecta:cold", "manifest_sha256": "3" * 64}
            ],
        },
        "schema": {
            "schema_sha256": "4" * 64,
            "migration_script_sha256": "5" * 64,
            "indexes_constraints_extensions_frozen": True,
        },
        "headroom_policy": {
            "frozen": True,
            "volume_limit_bytes": 5_000_000_000,
            "required_reserve_bytes": 1024**3,
            "measured_daily_growth_bytes": 32 * 1024**2,
            "growth_horizon_days": 14,
        },
        "approvals": {
            "non_production_rehearsal_allowed": True,
            "production_migration_authorized": False,
        },
    }


def evidence():
    return {
        "contract": "v4_fresh_restore_acceptance_evidence_v1",
        "target_production": False,
        "restore_completed": True,
        "observed_database_bytes": 3 * 1024**3,
        "observed_target_filesystem_bytes": 3 * 1024**3 + 200 * 1024**2,
        "headroom_policy": {
            "frozen": True,
            "volume_limit_bytes": 5_000_000_000,
            "required_reserve_bytes": 1024**3,
            "measured_daily_growth_bytes": 32 * 1024**2,
            "growth_horizon_days": 14,
        },
        "equivalence_checks": {
            "schema_equivalent": True,
            "indexes_constraints_extensions_equivalent": True,
            "retained_row_counts_equivalent": True,
            "representative_digests_equivalent": True,
            "application_readonly_smoke_pass": True,
            "archive_consumer_smoke_pass": True,
        },
        "approvals": {
            "production_migration_authorized": False,
        },
    }


def test_measured_restore_can_pass_capacity_without_authorizing_migration():
    result = evaluate_acceptance(evidence(), rehearsal_manifest())
    assert result["hobby_capacity_fit"] is True
    assert result["decision"] == "PASS_FRESH_RESTORE_CAPACITY_AND_EQUIVALENCE"
    assert result["automatic_plan_change_allowed"] is False
    assert result["production_migration_authorized"] is False
    assert result["purchase_action"] is False


def test_capacity_failure_returns_fail_not_a_smaller_required_dataset():
    data = evidence()
    data["observed_target_filesystem_bytes"] = 4 * 1024**3 + 500 * 1024**2
    result = evaluate_acceptance(data, rehearsal_manifest())
    assert result["hobby_capacity_fit"] is False
    assert result["decision"] == "FAIL_FRESH_RESTORE_CAPACITY_HEADROOM"
    assert result["automatic_plan_change_allowed"] is False


@pytest.mark.parametrize(
    "field",
    [
        "schema_equivalent",
        "indexes_constraints_extensions_equivalent",
        "retained_row_counts_equivalent",
        "representative_digests_equivalent",
        "application_readonly_smoke_pass",
        "archive_consumer_smoke_pass",
    ],
)
def test_any_equivalence_failure_blocks_acceptance(field):
    data = evidence()
    data["equivalence_checks"][field] = False
    with pytest.raises(FreshRestoreAcceptanceError, match=field):
        evaluate_acceptance(data, rehearsal_manifest())


def test_physical_filesystem_measurement_is_required():
    data = evidence()
    data["observed_target_filesystem_bytes"] = 0
    with pytest.raises(FreshRestoreAcceptanceError, match="physically measured"):
        evaluate_acceptance(data, rehearsal_manifest())


def test_database_bytes_cannot_exceed_measured_filesystem_bytes():
    data = evidence()
    data["observed_database_bytes"] = data["observed_target_filesystem_bytes"] + 1
    with pytest.raises(FreshRestoreAcceptanceError, match="cannot be below"):
        evaluate_acceptance(data, rehearsal_manifest())


def test_headroom_must_cover_measured_growth_horizon():
    data = evidence()
    manifest = rehearsal_manifest()
    data["headroom_policy"]["required_reserve_bytes"] = 100
    manifest["headroom_policy"]["required_reserve_bytes"] = 100
    with pytest.raises(FreshRestoreAcceptanceError, match="measured growth horizon"):
        evaluate_acceptance(data, manifest)


def test_post_hoc_headroom_policy_change_is_rejected():
    data = evidence()
    data["headroom_policy"]["required_reserve_bytes"] += 1
    with pytest.raises(
        FreshRestoreAcceptanceError,
        match="differs from preregistered rehearsal manifest",
    ):
        evaluate_acceptance(data, rehearsal_manifest())


def test_rehearsal_evidence_cannot_authorize_production_migration():
    data = evidence()
    data["approvals"]["production_migration_authorized"] = True
    with pytest.raises(FreshRestoreAcceptanceError, match="must not authorize"):
        evaluate_acceptance(data, rehearsal_manifest())


def test_module_has_no_io_or_production_mutation_surface():
    import ast
    import inspect
    import research.fresh_restore_acceptance_gate as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported <= {"__future__", "research", "typing"}
    low = source.lower()
    for forbidden in (
        "psycopg",
        "database_url",
        "requests.",
        "urllib.",
        "line_notify(",
        "subprocess.",
        "os.environ",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
    ):
        assert forbidden not in low
