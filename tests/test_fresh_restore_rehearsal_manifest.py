# -*- coding: utf-8 -*-
import hashlib

import pytest

from research.fresh_restore_rehearsal_manifest import (
    FreshRestoreRehearsalManifestError,
    evaluate_manifest,
)


def manifest():
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
                    "boundary": "race_date >= frozen_cutoff",
                    "boundary_sha256": hashlib.sha256(
                        b"race_date >= frozen_cutoff"
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


def test_valid_manifest_allows_only_non_production_rehearsal():
    result = evaluate_manifest(manifest())
    assert result["rehearsal_allowed"] is True
    assert result["target_production"] is False
    assert result["source_production_read_only"] is True
    assert result["production_migration_authorized"] is False
    assert result["purchase_action"] is False
    assert result["bounded_retention_table_count"] == 1


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda x: x["source"].update(production_read_only=False), "read-only"),
        (lambda x: x["source"].update(destructive_operations=True), "destructive"),
        (lambda x: x["target"].update(production=True), "non-Production"),
        (lambda x: x["target"].update(ephemeral=False), "ephemeral"),
        (lambda x: x["online_retention"].update(frozen=False), "retention policy"),
        (
            lambda x: x["archive_recovery"].update(primary_archive_verified=False),
            "primary archive",
        ),
        (
            lambda x: x["archive_recovery"].update(second_recovery_layer_verified=False),
            "second recovery",
        ),
        (
            lambda x: x["schema"].update(indexes_constraints_extensions_frozen=False),
            "indexes/constraints/extensions",
        ),
        (lambda x: x["headroom_policy"].update(frozen=False), "headroom policy"),
        (
            lambda x: x["approvals"].update(production_migration_authorized=True),
            "must not authorize Production",
        ),
    ],
)
def test_prerequisite_failure_is_fail_closed(mutator, message):
    bad = manifest()
    mutator(bad)
    with pytest.raises(FreshRestoreRehearsalManifestError, match=message):
        evaluate_manifest(bad)


def test_bounded_retention_requires_frozen_boundary_digest():
    bad = manifest()
    del bad["online_retention"]["tables"][2]["boundary_sha256"]
    with pytest.raises(FreshRestoreRehearsalManifestError, match="boundary_sha256"):
        evaluate_manifest(bad)


def test_bounded_retention_boundary_digest_binds_exact_text():
    bad = manifest()
    bad["online_retention"]["tables"][2]["boundary"] = "race_date >= changed_cutoff"
    with pytest.raises(FreshRestoreRehearsalManifestError, match="boundary_sha256 mismatch"):
        evaluate_manifest(bad)


def test_protected_evidence_table_must_remain_in_retained_manifest():
    bad = manifest()
    bad["online_retention"]["protected_evidence_tables"].append("v4_formal_evidence")
    with pytest.raises(FreshRestoreRehearsalManifestError, match="absent from retention"):
        evaluate_manifest(bad)


def test_archive_exclusion_requires_manifest_digest():
    bad = manifest()
    bad["archive_recovery"]["excluded_partitions"][0]["manifest_sha256"] = "bad"
    with pytest.raises(FreshRestoreRehearsalManifestError, match="manifest_sha256"):
        evaluate_manifest(bad)


def test_headroom_must_cover_measured_growth_horizon():
    bad = manifest()
    bad["headroom_policy"]["required_reserve_bytes"] = 100
    with pytest.raises(FreshRestoreRehearsalManifestError, match="measured growth horizon"):
        evaluate_manifest(bad)


def test_manifest_is_pure_and_has_no_production_io_surface():
    import ast
    import inspect
    import research.fresh_restore_rehearsal_manifest as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported <= {"__future__", "hashlib", "re", "typing"}

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
