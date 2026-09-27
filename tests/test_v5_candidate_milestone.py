from datetime import date

from research.v5_candidate_milestone import (
    V5MilestoneInput,
    current_baseline,
    evaluate_v5_milestone,
    evaluate_v5_core_progress,
)


def test_current_baseline_is_collecting():
    x = current_baseline()
    assert x["status"] == "COLLECTING_CORE_EVIDENCE"
    assert x["remaining"]["v4_resolved_formal_days"] == 14
    assert x["remaining"]["s03_m2_evaluated"] == 47
    assert x["remaining"]["day_strength_future_resolved_days"] == 10
    assert x["production_activation_allowed"] is False
    assert x["purchase_action"] is False


def test_freeze_review_needs_all_preregistered_evidence_gates():
    x = evaluate_v5_milestone(
        V5MilestoneInput(
            as_of=date(2026, 10, 15),
            v4_resolved_formal_days=20,
            s03_m2_evaluated=100,
            day_strength_future_resolved_days=10,
            day_strength_keep_days=3,
            day_strength_skip_days=3,
            evidence_contract_clean=True,
        )
    )
    assert x["status"] == "V5_CORE_FREEZE_REVIEW_READY"
    assert x["core_evidence_ready"] is True
    assert x["optional_layers"]["day_strength"]["admission_ready"] is True
    assert x["automatic_model_change_allowed"] is False


def test_optional_day_strength_cannot_block_core_freeze():
    x = evaluate_v5_milestone(
        V5MilestoneInput(
            as_of=date(2026, 10, 15),
            v4_resolved_formal_days=25,
            s03_m2_evaluated=120,
            day_strength_future_resolved_days=10,
            day_strength_keep_days=10,
            day_strength_skip_days=0,
            evidence_contract_clean=True,
        )
    )
    assert x["core_evidence_ready"] is True
    assert x["status"] == "V5_CORE_FREEZE_REVIEW_READY"
    assert x["optional_layers"]["day_strength"]["admission_ready"] is False
    assert x["remaining"]["day_strength_skip_days"] == 3


def test_unclean_evidence_fails_closed():
    x = evaluate_v5_milestone(
        V5MilestoneInput(
            as_of=date(2026, 10, 15),
            v4_resolved_formal_days=20,
            s03_m2_evaluated=100,
            day_strength_future_resolved_days=10,
            day_strength_keep_days=3,
            day_strength_skip_days=3,
            evidence_contract_clean=False,
        )
    )
    assert x["core_evidence_ready"] is False


def test_core_progress_does_not_infer_optional_layers():
    x = evaluate_v5_core_progress(
        as_of=date(2026, 10, 10),
        v4_resolved_formal_days=20,
        s03_m2_evaluated=100,
        evidence_contract_clean=True,
    )
    assert x["status"] == "V5_CORE_FREEZE_REVIEW_READY"
    assert x["remaining"]["v4_resolved_formal_days"] == 0
    assert x["remaining"]["s03_m2_evaluated"] == 0
    assert x["optional_layers_not_evaluated_here"] == ["day_strength", "f_count"]
    assert x["production_activation_allowed"] is False
