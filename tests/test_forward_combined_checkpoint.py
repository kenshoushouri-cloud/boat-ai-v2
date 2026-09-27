import json
from research.forward_combined_checkpoint import build_scorecard


def test_combined_scorecard_uses_frozen_review_gates():
    v4 = {
        "complete_day_count": 7,
        "complete_day_dates": [f"2026-09-{d:02d}" for d in range(21, 28)],
        "complete_day_only": {"top2": {"roi_pct": 150.0}},
        "robustness": {},
        "void_races": [],
        "pending_or_invalid_races": [],
    }
    s03 = "\n".join([
        'S03_M2_COMMON_COVERAGE={"evaluated": 58, "invalid_result": 1, "pending": 4, "rows": 63}',
        'S03_M2_COMMON_OVERALL={"evaluated": 58, "hits": 5, "roi_pct": 180.0}',
        'S03_M2_COMMON_RISK={"max_drawdown_yen": 1700, "max_losing_streak": 16}',
        'S03_M2_COMMON_HALVES={"first": {"roi_pct": 250.0}, "second": {"roi_pct": 110.0}}',
        'S03_M2_COMMON_BOOTSTRAP={"p_roi_gt_100_pct": 88.0}',
    ])
    out = build_scorecard(v4, s03, end_date="2026-09-27")
    assert out["v4_formal"]["review_gate"]["next_gate"] == 10
    assert out["v4_formal"]["review_gate"]["remaining"] == 3
    assert out["s03_m2"]["review_gate"]["next_gate"] == 100
    assert out["s03_m2"]["review_gate"]["remaining"] == 42
    assert out["safety"]["promotion_allowed"] is False
    assert out["safety"]["production_change"] is False
