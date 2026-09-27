from research.v4_fcount_prospective_activation_manifest import validate_manifest


def test_manifest_remains_noop_and_future_only():
    m = validate_manifest()
    assert m["activation_performed"] is False
    assert m["approval_required"] is True
    assert m["scope"] == "future_target_days_only"
    assert m["historical_backfill_allowed"] is False
    assert m["historical_coefficient_search_allowed"] is False


def test_manifest_allows_only_exact_read_shape():
    m = validate_manifest()
    assert m["db_transaction"] == "read_only"
    assert m["db_write_allowed"] is False
    assert m["required_rows"] == 36
    assert m["required_races"] == 6
    assert m["required_lanes_per_race"] == [1, 2, 3, 4, 5, 6]
    assert m["allowed_db_read_sql"] == (
        "select race_id,lane,f_count "
        "from v2_race_entries "
        "where race_id=any(%s) "
        "order by race_id,lane"
    )


def test_companion_failure_cannot_rewrite_formal_v4():
    m = validate_manifest()
    assert m["formal_v4_mutation_allowed"] is False
    assert m["formal_v4_failure_on_companion_failure"] is False
    assert m["on_failure"]["write_companion"] is False
    assert m["on_failure"]["rewrite_formal_v4"] is False
    assert m["on_failure"]["change_formal_selection"] is False
    assert m["on_failure"]["purchase"] is False
