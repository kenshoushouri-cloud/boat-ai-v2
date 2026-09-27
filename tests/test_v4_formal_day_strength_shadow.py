from datetime import date

import pytest

from research.v4_formal_day_strength_shadow import (
    FormalDay,
    classify_future_day,
    extract_formal_day,
)


def payload(day: str, scores: list[float]):
    return {
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": day,
            "outcome_read": False,
            "payout_read": False,
        },
        "summary": {"date": day, "core_races": 6, "core_tickets": 12},
        "feed": [
            {"daily_rank": i + 1, "race_score": s}
            for i, s in enumerate(scores)
        ],
    }


def test_extract_exact_six_strength():
    x = extract_formal_day(payload("2026-09-28", [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]))
    assert x.target_date == date(2026, 9, 28)
    assert x.day_strength == pytest.approx(0.65)


def test_future_shadow_uses_prior_seven_median_only():
    prior = [
        FormalDay(date(2026, 9, 21 + i), v, 6)
        for i, v in enumerate([0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96])
    ]
    keep = classify_future_day(FormalDay(date(2026, 9, 28), 0.94, 6), prior)
    skip = classify_future_day(FormalDay(date(2026, 9, 28), 0.92, 6), prior)
    assert keep["reference_strength"] == pytest.approx(0.93)
    assert keep["classification"] == "KEEP_SHADOW"
    assert skip["classification"] == "SKIP_SHADOW"
    assert keep["formal_action_changed"] is False
    assert keep["promotion_allowed"] is False


def test_not_ready_before_seven_prior_formal_days():
    prior = [FormalDay(date(2026, 9, 27), 0.9, 6)]
    result = classify_future_day(FormalDay(date(2026, 9, 28), 0.95, 6), prior)
    assert result["classification"] == "NOT_READY"


def test_rejects_pre_result_contract_violation():
    x = payload("2026-09-28", [0.9] * 6)
    x["freeze_provenance"]["outcome_read"] = True
    with pytest.raises(ValueError):
        extract_formal_day(x)


def test_rejects_wrong_core_count():
    x = payload("2026-09-28", [0.9] * 6)
    x["summary"]["core_races"] = 5
    with pytest.raises(ValueError):
        extract_formal_day(x)
