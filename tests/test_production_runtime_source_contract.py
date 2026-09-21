# -*- coding: utf-8 -*-
from research.production_runtime_source_contract import audit_runtime_inventory


REQUIRED = (
    "cron-final-check",
    "cron-opponent-pressure-v2-live",
    "cron-nightly-results",
    "candidate-discovery-v4-prospective-freeze",
    "test-beforeinfo-extra",
    "storage-maintenance-once",
    "storage-index-drop-once",
)


def current_like_snapshot():
    return [
        {
            "name": "cron-final-check",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u run_final_pg.py",
            "cron_schedule": "*/15 23,0-14 * * *",
            "capabilities": ["legacy_final_chain"],
        },
        {
            "name": "cron-opponent-pressure-v2-live",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "runtime/opponent-pressure-railway-cron",
            "start_command": "python -u .github/scripts/opponent_pressure_shadow_v2_compact.py",
            "cron_schedule": "0 22 * * *",
            "capabilities": ["v4_input_writer"],
        },
        {
            "name": "cron-nightly-results",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u run_nightly_results_pg.py",
            "cron_schedule": "30 14 * * *",
            "capabilities": ["candidate_shadow_reader"],
        },
        {
            "name": "candidate-discovery-v4-prospective-freeze",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u research/candidate_discovery_v4_prospective_freeze_pg.py",
            "cron_schedule": "16 23 * * *",
            "capabilities": ["candidate_shadow_reader"],
        },
        {
            "name": "test-beforeinfo-extra",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u collect_candidate_filter_shadow_pg.py",
            "capabilities": ["candidate_shadow_writer", "reads_base_odds"],
            "observed_effects": ["candidate_rows=11", "saved_rows=11"],
        },
        {
            "name": "storage-maintenance-once",
            "source_image": "python:3.12-slim",
            "start_command": "python -c \"... DROP INDEX CONCURRENTLY public.idx_v2_odds_race_date ...\"",
        },
        {
            "name": "storage-index-drop-once",
            "source_image": "python:3.12-slim",
            "start_command": "",
        },
    ]


def test_current_like_snapshot_blocks_and_surfaces_non_main_branch():
    report = audit_runtime_inventory(current_like_snapshot(), required_services=REQUIRED)
    assert report.runtime_inventory_gate == "BLOCK"
    assert report.candidate_shadow_zero_consumer_gate == "BLOCK"
    assert report.non_main_repo_sources == ("cron-opponent-pressure-v2-live",)
    assert report.candidate_shadow_writer_surfaces == ("test-beforeinfo-extra",)
    assert report.candidate_shadow_reader_surfaces == (
        "candidate-discovery-v4-prospective-freeze",
        "cron-nightly-results",
    )
    assert report.destructive_inline_surfaces == ("storage-maintenance-once",)
    assert report.unresolved_services == ("storage-index-drop-once",)
    assert "test-beforeinfo-extra" in report.no_cron_executable_surfaces
    assert "storage-maintenance-once" in report.no_cron_executable_surfaces


def test_missing_required_service_fails_closed():
    rows = [row for row in current_like_snapshot() if row["name"] != "cron-final-check"]
    report = audit_runtime_inventory(rows, required_services=REQUIRED)
    assert report.runtime_inventory_gate == "BLOCK"
    assert report.missing_required_services == ("cron-final-check",)


def test_duplicate_service_fails_closed():
    rows = current_like_snapshot()
    rows.append(dict(rows[0]))
    report = audit_runtime_inventory(rows, required_services=REQUIRED)
    assert report.runtime_inventory_gate == "BLOCK"
    assert report.duplicate_services == ("cron-final-check",)


def test_repo_surface_without_branch_is_unresolved():
    rows = [
        {
            "name": "repo-surface",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "start_command": "python -u task.py",
        }
    ]
    report = audit_runtime_inventory(rows, required_services=("repo-surface",))
    assert report.runtime_inventory_gate == "BLOCK"
    assert report.unresolved_services == ("repo-surface",)


def test_safe_hypothetical_inventory_can_pass_structural_gate():
    rows = [
        {
            "name": "scheduled-safe",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u safe_reader.py",
            "cron_schedule": "0 0 * * *",
            "capabilities": ["read_only_current_data"],
        },
        {
            "name": "manual-safe",
            "source_image": "python:3.12-slim",
            "start_command": "python -c \"print('read-only audit')\"",
        },
    ]
    report = audit_runtime_inventory(
        rows,
        required_services=("scheduled-safe", "manual-safe"),
    )
    assert report.runtime_inventory_gate == "PASS"
    assert report.candidate_shadow_zero_consumer_gate == "PASS"
    assert report.no_cron_executable_surfaces == ("manual-safe",)


def test_reader_only_inventory_blocks_candidate_shadow_zero_consumer() -> None:
    rows = [
        {
            "name": "reader-only",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "main",
            "start_command": "python -u report_candidate_filter_shadow_performance_pg.py",
            "cron_schedule": "0 0 * * *",
            "capabilities": ["candidate_shadow_reader"],
        }
    ]
    report = audit_runtime_inventory(rows, required_services=("reader-only",))
    assert report.runtime_inventory_gate == "PASS"
    assert report.candidate_shadow_zero_consumer_gate == "BLOCK"
    assert report.candidate_shadow_writer_surfaces == ()
    assert report.candidate_shadow_reader_surfaces == ("reader-only",)


def test_non_main_branch_is_accounted_not_automatically_blocked():
    rows = [
        {
            "name": "runtime-branch-reader",
            "source_repo": "kenshoushouri-cloud/boat-ai-v2",
            "source_branch": "runtime/example",
            "start_command": "python -u reader.py",
            "cron_schedule": "0 1 * * *",
        }
    ]
    report = audit_runtime_inventory(rows, required_services=("runtime-branch-reader",))
    assert report.runtime_inventory_gate == "PASS"
    assert report.non_main_repo_sources == ("runtime-branch-reader",)
