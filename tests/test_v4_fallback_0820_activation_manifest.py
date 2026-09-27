from research.v4_fallback_0820_activation_manifest import validate_manifest


def test_activation_manifest_is_one_field_only_and_not_active():
    m = validate_manifest()
    assert m["allowed_changed_fields"] == ["cronSchedule"]
    assert m["current_cron"] == "25 23 * * *"
    assert m["proposed_cron"] == "20 23 * * *"
    assert m["rollback"]["cron"] == m["current_cron"]
    assert m["activation_performed"] is False
    assert "explicit_user_approval_for_production_cron_change" in m["preconditions"]
