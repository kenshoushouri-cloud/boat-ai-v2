from research.v4_fallback_0820_activation_manifest import validate_manifest


def test_activation_manifest_is_one_field_only_and_not_active():
    m = validate_manifest()
    assert m["allowed_changed_fields"] == ["cronSchedule"]
    assert m["current_cron"] == "25 23 * * *"
    assert m["proposed_cron"] == "20 23 * * *"
    assert m["rollback"]["cron"] == m["current_cron"]
    assert m["activation_performed"] is False
    assert "explicit_user_approval_for_production_cron_change" in m["preconditions"]


def test_non_cron_service_config_is_frozen():
    m = validate_manifest()
    b = m["baseline_service_config"]
    assert b["source_repo"] == "kenshoushouri-cloud/boat-ai-v2"
    assert b["source_branch"] == "main"
    assert b["builder"] == "RAILPACK"
    assert b["build_environment"] == "V3"
    assert b["start_command"] == "python -u research/candidate_discovery_v4_fallback_dispatcher.py"
    assert b["restart_policy_type"] == "NEVER"
    assert b["runtime"] == "V2"
    assert b["region"] == "us-west2"
    assert b["num_replicas"] == 1
    assert m["proposed_service_config_delta"] == {
        "cron_schedule": ["25 23 * * *", "20 23 * * *"]
    }
