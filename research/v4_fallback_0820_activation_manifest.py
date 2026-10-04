# -*- coding: utf-8 -*-
"""Pure activation/rollback manifest for a separately-approved 08:20 fallback change.

This module never calls Railway. It only freezes the exact intended one-field
configuration change and rollback target.
"""
from __future__ import annotations

MANIFEST = {
    "contract": "V4_FALLBACK_0820_ACTIVATION_MANIFEST_V1",
    "project_id": "268a5b17-0712-440a-884d-27f7fa887a2d",
    "environment_id": "5ffb02f6-5ec8-4268-9bda-8e30431ff625",
    "service_id": "84010f63-8e5a-4ad3-8718-bdad3dd9c436",
    "service_name": "candidate-discovery-v4-fallback-dispatcher",
    "current_cron": "25 23 * * *",
    "proposed_cron": "20 23 * * *",
    "current_jst": "08:25",
    "proposed_jst": "08:20",
    "allowed_changed_fields": ["cronSchedule"],
    "baseline_service_config": {
        "source_repo": "kenshoushouri-cloud/boat-ai-v2",
        "source_branch": "main",
        "builder": "RAILPACK",
        "build_environment": "V3",
        "start_command": "python -u research/candidate_discovery_v4_fallback_dispatcher.py",
        "restart_policy_type": "NEVER",
        "runtime": "V2",
        "region": "us-west2",
        "num_replicas": 1,
        "cron_schedule": "25 23 * * *",
    },
    "proposed_service_config_delta": {
        "cron_schedule": ["25 23 * * *", "20 23 * * *"],
    },
    "unchanged_requirements": [
        "project",
        "environment",
        "service",
        "source_cutoff_08_15_jst",
        "primary_schedule_08_16_jst",
        "dispatcher_code",
        "capture_arbiter",
        "formal_v4_model",
        "formal_selector",
        "formal_top6",
        "formal_top2",
        "stake",
        "purchase_action_false",
    ],
    "preconditions": [
        "explicit_user_approval_for_production_cron_change",
        "current_cron_reverified_as_25_23_star_star_star",
        "production_staged_changes_none",
        "production_pending_work_none",
        "latest_dispatcher_deployment_success",
    ],
    "post_change_verification": [
        "cron_is_20_23_star_star_star",
        "deployment_success",
        "production_staged_changes_none",
        "production_pending_work_none",
        "no_other_service_config_change",
    ],
    "rollback": {
        "trigger": "unexpected_dispatch_behavior_or_user_request",
        "cron": "25 23 * * *",
        "jst": "08:25",
    },
    "activation_performed": False,
}


def validate_manifest() -> dict:
    if MANIFEST["allowed_changed_fields"] != ["cronSchedule"]:
        raise ValueError("only cronSchedule may change")
    if MANIFEST["current_cron"] != "25 23 * * *":
        raise ValueError("unexpected current cron")
    if MANIFEST["proposed_cron"] != "20 23 * * *":
        raise ValueError("unexpected proposed cron")
    if MANIFEST["rollback"]["cron"] != MANIFEST["current_cron"]:
        raise ValueError("rollback must restore current cron")
    if set(MANIFEST["proposed_service_config_delta"]) != {"cron_schedule"}:
        raise ValueError("only cron schedule delta allowed")
    if MANIFEST["baseline_service_config"]["cron_schedule"] != MANIFEST["current_cron"]:
        raise ValueError("baseline/current cron mismatch")
    if MANIFEST["activation_performed"] is not False:
        raise ValueError("research manifest cannot claim activation")
    return MANIFEST


if __name__ == "__main__":
    import json
    print(json.dumps(validate_manifest(), ensure_ascii=False, indent=2, sort_keys=True))
