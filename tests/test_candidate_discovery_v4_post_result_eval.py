from copy import deepcopy

import pytest

from research.candidate_discovery_v4_post_result_eval import (
    V4PostResultEvaluationError,
    evaluate,
)


def artifact():
    feed = []
    for rank in range(1, 7):
        head = 1 if rank < 6 else 3
        if rank == 1:
            tickets = ["1-2-4", "1-3-4"]
        elif rank == 2:
            tickets = ["1-5-2", "1-2-5"]
        elif rank == 3:
            tickets = ["1-5-2", "1-2-5"]
        elif rank == 4:
            tickets = ["1-3-4", "1-4-3"]
        elif rank == 5:
            tickets = ["2-1-3", "2-1-6"]
            head = 2
        else:
            tickets = ["3-1-4", "3-4-1"]
        feed.append({
            "race_id": f"20260918_{rank:02d}_01",
            "daily_rank": rank,
            "tier": "A" if rank < 3 else "B",
            "head_lane": head,
            "tickets": [
                {"core_order": 1, "ticket": tickets[0], "source": ["DISCOVERY_CORE"], "legacy_rules": []},
                {"core_order": 2, "ticket": tickets[1], "source": ["DISCOVERY_CORE"], "legacy_rules": []},
            ],
        })
    feed.append({
        "race_id": "20260918_20_01",
        "daily_rank": None,
        "tier": "L",
        "head_lane": None,
        "tickets": [
            {"core_order": None, "ticket": "1-2-3", "source": ["LEGACY"], "legacy_rules": ["S03"]}
        ],
    })
    return {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "all_frozen_rows_pre_deadline": True,
            "target_date": "2026-09-18",
        },
        "feed": feed,
    }


def outcomes():
    return {
        "races": [
            {"race_id": "20260918_01_01", "trifecta": "1-2-4", "trifecta_payout_yen": 2200},
            {"race_id": "20260918_02_01", "trifecta": "1-5-3", "trifecta_payout_yen": 3100},
            {"race_id": "20260918_03_01", "trifecta": "4-1-2", "trifecta_payout_yen": 5000},
            {"race_id": "20260918_04_01", "trifecta": "1-4-3", "trifecta_payout_yen": 1800},
            {"race_id": "20260918_05_01", "trifecta": "2-1-5", "trifecta_payout_yen": 4100},
            {"race_id": "20260918_06_01", "trifecta": "3-4-1", "trifecta_payout_yen": 1200},
        ]
    }


def test_evaluator_keeps_formal_core_separate_from_legacy() -> None:
    result = evaluate(artifact(), outcomes())
    summary = result["summary"]
    assert result["formal_core_only"] is True
    assert result["legacy_excluded_from_formal_metrics"] is True
    assert summary["core_races"] == 6
    assert summary["core_tickets"] == 12
    assert summary["exact_hit_races"] == 3
    assert summary["head_hit_races"] == 5
    assert summary["first_second_prefix_hit_races"] == 5
    assert summary["third_only_miss_races"] == 2
    assert summary["investment_yen"] == 1200
    assert summary["gross_return_yen"] == 5200
    assert summary["profit_yen"] == 4000
    assert summary["roi_percent"] == 433.333


def test_third_only_miss_requires_correct_first_second_prefix() -> None:
    result = evaluate(artifact(), outcomes())
    by_id = {row["race_id"]: row for row in result["races"]}
    assert by_id["20260918_02_01"]["third_only_miss"] is True
    assert by_id["20260918_05_01"]["third_only_miss"] is True
    assert by_id["20260918_03_01"]["third_only_miss"] is False


def test_ineligible_or_late_artifact_is_rejected() -> None:
    bad = artifact()
    bad["prospective_evidence_eligible"] = False
    with pytest.raises(V4PostResultEvaluationError, match="not eligible"):
        evaluate(bad, outcomes())

    bad = artifact()
    bad["freeze_provenance"]["all_frozen_rows_pre_deadline"] = False
    with pytest.raises(V4PostResultEvaluationError, match="pre-deadline"):
        evaluate(bad, outcomes())


def test_missing_outcome_fails_closed() -> None:
    bad = outcomes()
    bad["races"] = bad["races"][:-1]
    with pytest.raises(V4PostResultEvaluationError, match="missing outcome"):
        evaluate(artifact(), bad)


def test_duplicate_or_malformed_outcomes_fail_closed() -> None:
    bad = outcomes()
    bad["races"].append(deepcopy(bad["races"][0]))
    with pytest.raises(V4PostResultEvaluationError, match="duplicate outcome"):
        evaluate(artifact(), bad)

    bad = outcomes()
    bad["races"][0]["trifecta"] = "1-1-2"
    with pytest.raises(V4PostResultEvaluationError, match="duplicate lane"):
        evaluate(artifact(), bad)


def test_core_shape_and_purchase_safety_are_frozen() -> None:
    bad = artifact()
    bad["purchase_action"] = True
    with pytest.raises(V4PostResultEvaluationError, match="purchase_action"):
        evaluate(bad, outcomes())

    bad = artifact()
    bad["feed"] = bad["feed"][:-2] + bad["feed"][-1:]
    with pytest.raises(V4PostResultEvaluationError, match="exactly 6 races"):
        evaluate(bad, outcomes())


def test_evaluator_module_is_offline_and_has_no_production_io_surface() -> None:
    import inspect
    import research.candidate_discovery_v4_post_result_eval as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "psycopg",
        "requests",
        "database_url",
        "railway",
        "line_notify",
        "insert into",
        "update ",
        "delete from",
        "vacuum",
    ):
        assert forbidden not in source
