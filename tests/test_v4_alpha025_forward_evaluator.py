# -*- coding: utf-8 -*-
from research.v4_alpha025_forward_evaluator import evaluate


def freeze():
    races = []
    for idx in range(1, 7):
        races.append({
            "race_id": f"r{idx}",
            "control_top2": ["1-2-3", "1-3-2"],
            "shadow_top2": ["1-2-3", "1-2-4"],
        })
    return {
        "contract": "v4_alpha025_prospective_shadow_v1",
        "freeze": {
            "target_date": "2026-09-24",
            "freeze_at_jst": "2026-09-24T08:45:00+09:00",
        },
        "model": {"frozen_model_sha256": "a" * 64},
        "policy": {
            "alpha": 0.25,
            "result_read": False,
            "payout_read": False,
            "odds_read": False,
            "db_write": False,
            "line_sent": False,
            "purchase_action": False,
            "promotion_allowed": False,
            "production_behavior_changed": False,
        },
        "races": races,
    }


def results():
    tickets = [
        "1-2-3",
        "1-3-2",
        "1-2-4",
        "2-1-3",
        "3-2-1",
        "4-5-6",
    ]
    return [
        {
            "race_id": f"r{idx}",
            "trifecta_ticket": ticket,
            "trifecta_payout_yen": 1000 + idx * 100,
            "result_status": "official",
            "race_status": "official",
        }
        for idx, ticket in enumerate(tickets, 1)
    ]


def test_evaluator_uses_only_frozen_ticket_sets():
    out = evaluate(freeze(), results())
    assert out["races"] == 6
    assert out["control"]["hits"] == 2
    assert out["shadow"]["hits"] == 2
    assert out["paired"]["control_only"] == 1
    assert out["paired"]["shadow_only"] == 1
    assert out["candidate_reconstruction"] is False
    assert out["rerank_performed"] is False
    assert out["purchase_action"] is False


def test_evaluator_requires_exact_same_race_set():
    bad = results()[:-1]
    try:
        evaluate(freeze(), bad)
    except ValueError as exc:
        assert "exactly match" in str(exc)
    else:
        raise AssertionError("expected fail closed on incomplete results")


def test_evaluator_rejects_nonofficial_result():
    bad = results()
    bad[0]["result_status"] = "provisional"
    try:
        evaluate(freeze(), bad)
    except ValueError as exc:
        assert "non-exact official" in str(exc)
    else:
        raise AssertionError("expected fail closed on provisional result")
