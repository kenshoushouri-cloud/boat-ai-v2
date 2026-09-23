# -*- coding: utf-8 -*-
from pathlib import Path

from research import candidate_discovery_v4_contract as v4
from research import v4_alpha025_prospective_shadow as shadow


def synthetic_entries():
    return [
        {
            "lane": lane,
            "national_win_rate": 7.5 - lane * 0.3,
            "national_place2_rate": 50.0 - lane * 3.0,
            "local_place2_rate": 48.0 - lane * 2.5,
            "avg_st": 0.12 + lane * 0.01,
            "motor_place2_rate": 40.0 - lane,
        }
        for lane in v4.LANES
    ]


def test_frozen_alpha_and_historical_identity():
    assert shadow.ALPHA == 0.25
    assert shadow.TRAINING_END_DATE == "2026-09-22"
    assert shadow.HISTORICAL_RUN_ID == 35850876154
    assert shadow.HISTORICAL_ARTIFACT_ID == 10745995595
    assert shadow.HISTORICAL_ARTIFACT_SHA256 == (
        "6aae27dbaa9ed7a13a937904765b61124d4507ec52880d007e9998e1286debbe"
    )
    assert len(shadow.SECOND_WEIGHTS) == shadow.SECOND_DIM == 14
    assert len(shadow.THIRD_WEIGHTS) == shadow.THIRD_DIM == 16


def test_shadow_preserves_current_first_place_marginal():
    raw = {lane: 7.0 - lane * 0.5 for lane in v4.LANES}
    current = v4.ticket_probabilities(raw)
    features = shadow.lane_feature_map(
        synthetic_entries(),
        base_raw=raw,
    )
    out = shadow.shadow_distribution(current, features)
    before = shadow.first_marginals(current)
    after = shadow.first_marginals(out)
    assert len(out) == 120
    assert abs(sum(out.values()) - 1.0) < 1e-12
    for lane in v4.LANES:
        assert abs(before[lane] - after[lane]) < 1e-12


def test_frozen_model_metadata_is_deterministic():
    assert shadow.model_metadata() == shadow.model_metadata()
    assert len(shadow.model_metadata()["frozen_model_sha256"]) == 64


def test_pg_generator_has_no_result_payout_odds_or_write_surface():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_alpha025_prospective_shadow_pg.py"
    ).read_text(encoding="utf-8").lower()
    assert "set transaction read only" in source
    assert "v4_alpha025_forward_date is required" in source
    assert "prospective same-day freeze required" in source
    assert "freeze before 08:15 jst is not allowed" in source
    assert "selected race deadline not prospective" in source
    for forbidden in (
        "v2_results",
        "trifecta_payout",
        "select odds",
        " from v2_odds",
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "line_notify",
        "purchase_action=true",
    ):
        assert forbidden not in source


def test_workflow_is_disabled_pending_374_gate_and_non_enumerating():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-alpha025-forward-shadow.yml"
    ).read_text(encoding="utf-8").lower()
    assert "v4_alpha025_forward_enabled: '0'" in workflow
    assert "pending_374_real_fixture_gate" in workflow
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
