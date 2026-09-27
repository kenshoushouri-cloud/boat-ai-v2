import copy

from research.v4_fcount_current_artifact_compat import synthetic_rows


def test_synthetic_rows_are_exact_36_and_do_not_mutate_formal():
    formal = {
        "feed": [
            {
                "race_id": f"r{i}",
                "daily_rank": i,
                "legacy_carryover": False,
            }
            for i in range(1, 7)
        ]
    }
    before = copy.deepcopy(formal)
    rows = synthetic_rows(formal)
    assert len(rows) == 36
    assert {(x["race_id"], x["lane"]) for x in rows} == {
        (f"r{i}", lane) for i in range(1, 7) for lane in range(1, 7)
    }
    assert all(type(x["f_count"]) is int and x["f_count"] >= 0 for x in rows)
    assert formal == before
