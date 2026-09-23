# -*- coding: utf-8 -*-
import math

from research import candidate_discovery_v4_contract as v4
from research.v4_market_residual_lane_model_pg import (
    CALIB_END,
    FEATURE_DIM,
    HOLD_START,
    fit_residual,
    residual_probs,
    ticket_features,
)


def ticket_map(value=1.0):
    return {
        f"{a}-{b}-{c}": value
        for a in v4.LANES
        for b in v4.LANES
        for c in v4.LANES
        if len({a, b, c}) == 3
    }


def test_strict_pretest_cutoff():
    assert CALIB_END.isoformat() == "2026-08-24"
    assert HOLD_START.isoformat() == "2026-08-25"
    assert CALIB_END < HOLD_START


def test_feature_dimension_and_clipping():
    x = ticket_features("1-2-3", 1e-9, 1.0)
    assert len(x) == FEATURE_DIM == 19
    assert x[0] == 3.0
    assert sum(x[1:7]) == 1.0
    assert sum(x[7:13]) == 1.0
    assert sum(x[13:19]) == 1.0


def test_zero_weights_reproduce_market():
    market = ticket_map(1.0)
    market["1-2-3"] = 3.0
    market = {
        k: v / sum(market.values())
        for k, v in market.items()
    }
    model = ticket_map(1.0)
    model = {
        k: v / sum(model.values())
        for k, v in model.items()
    }
    out = residual_probs(market, model, [0.0] * FEATURE_DIM)
    for ticket in market:
        assert abs(out[ticket] - market[ticket]) < 1e-12


def test_fit_is_deterministic_and_moves_on_simple_signal():
    market = ticket_map(1.0)
    market = {
        k: v / sum(market.values())
        for k, v in market.items()
    }
    model = dict(market)
    rows = [
        {
            "market_probs": market,
            "model_probs": model,
            "actual": "1-2-3",
        }
        for _ in range(4)
    ]
    w1, m1 = fit_residual(rows)
    w2, m2 = fit_residual(rows)
    assert w1 == w2
    assert m1 == m2
    assert m1["final_log_loss"] < m1["initial_log_loss"]


def test_source_freezes_heldout_before_result_and_is_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_market_residual_lane_model_pg.py"
    ).read_text(encoding="utf-8")
    heldout = source[source.index("def gather_heldout"):]
    assert heldout.index("frozen = {") < heldout.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "heldout_used_for_training" in low
    assert "hyperparameter_search" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_is_non_enumerating():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-market-residual-lane-model.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
