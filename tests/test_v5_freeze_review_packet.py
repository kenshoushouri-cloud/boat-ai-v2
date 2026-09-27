from research.v5_freeze_review_packet import build_v5_review_packet


def combined(v4_days=20, s03_eval=100, core_ready=True):
    return {
        "contract": "forward_combined_manual_checkpoint_v1",
        "end_date": "2026-10-15",
        "v4_formal": {
            "resolved_formal_days": v4_days,
            "top2": {
                "evaluated": 100,
                "investment_yen": 20000,
                "return_yen": 23000,
                "profit_yen": 3000,
                "roi_pct": 115.0,
            },
            "robustness": {"leave_one_day_min_roi_pct": 101.0},
            "review_gate": {"current": v4_days, "next_gate": 30},
        },
        "s03_m2": {
            "coverage": {
                "evaluated": s03_eval,
                "invalid_result": 2,
                "pending": 0,
            },
            "overall": {
                "evaluated": s03_eval,
                "investment_yen": s03_eval * 100,
                "return_yen": 12000,
                "profit_yen": 2000,
                "roi_pct": 120.0,
            },
            "risk": {"max_drawdown_yen": 3000, "max_losing_streak": 20},
            "chronological_halves": {
                "first": {"roi_pct": 125.0},
                "second": {"roi_pct": 115.0},
            },
            "day_bootstrap": {"p_roi_gt_100_pct": 80.0},
            "review_gate": {"current": s03_eval, "next_gate": 100},
        },
        "v5_core_milestone": {
            "target_freeze_date": "2026-10-15",
            "core_evidence_ready": core_ready,
            "status": (
                "V5_CORE_FREEZE_REVIEW_READY"
                if core_ready
                else "COLLECTING_CORE_EVIDENCE"
            ),
        },
        "safety": {
            "production_change": False,
            "buy": False,
            "purchase_action": False,
        },
    }


def test_ready_packet_requires_human_review():
    x = build_v5_review_packet(combined())
    assert x["core_review_status"] == "CORE_EVIDENCE_READY_FOR_HUMAN_FREEZE_REVIEW"
    assert x["v4_formal"]["roi_gt_100_descriptive"] is True
    assert x["s03_m2"]["roi_gt_100_descriptive"] is True
    assert x["decision_boundary"]["human_review_required"] is True
    assert x["decision_boundary"]["automatic_production_activation_allowed"] is False
    assert x["decision_boundary"]["purchase_action"] is False


def test_optional_day_strength_is_nonblocking():
    x = build_v5_review_packet(
        combined(),
        day_strength_summary={
            "future_resolved_days": 10,
            "keep_days": 8,
            "skip_days": 2,
        },
    )
    d = x["optional_layers"]["day_strength"]
    assert d["admission_ready"] is False
    assert d["required_for_core_freeze"] is False
    assert x["core_evidence_ready"] is True


def test_collecting_core_stays_collecting():
    x = build_v5_review_packet(combined(v4_days=15, s03_eval=80, core_ready=False))
    assert x["core_review_status"] == "COLLECTING_CORE_EVIDENCE"
    assert x["core_evidence_ready"] is False


def test_rejects_non_neutral_combined_input():
    x = combined()
    x["safety"]["production_change"] = True
    try:
        build_v5_review_packet(x)
    except ValueError as e:
        assert "production-neutral" in str(e)
    else:
        raise AssertionError("expected ValueError")
