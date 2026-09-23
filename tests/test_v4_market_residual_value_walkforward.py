# -*- coding: utf-8 -*-
from research import candidate_discovery_v4_contract as v4
from research.v4_market_residual_value_walkforward_pg import (
    BETA_GRID,
    EV_THRESHOLDS,
    POINT_COUNTS,
    choose_beta,
    geometric_blend,
    normalize,
    predictive_metrics,
)


def tickets():
    return [
        f"{a}-{b}-{c}"
        for a in v4.LANES
        for b in v4.LANES
        if b != a
        for c in v4.LANES
        if c not in (a, b)
    ]


def uniform():
    ts = tickets()
    return {ticket: 1.0 / len(ts) for ticket in ts}


def test_grids_are_small_and_fixed():
    assert BETA_GRID == (0.0, 0.10, 0.25, 0.50, 1.0)
    assert POINT_COUNTS == (2, 3)
    assert EV_THRESHOLDS == (1.00, 1.05, 1.10)


def test_geometric_blend_endpoints():
    market = uniform()
    model = dict(market)
    ts = tickets()
    model[ts[0]] *= 2.0
    model = normalize(model)
    q0 = geometric_blend(market, model, 0.0)
    q1 = geometric_blend(market, model, 1.0)
    assert all(abs(q0[t] - market[t]) < 1e-12 for t in ts)
    assert all(abs(q1[t] - model[t]) < 1e-12 for t in ts)


def test_beta_selection_uses_predictive_loss_not_profit():
    market = uniform()
    actual = tickets()[0]
    better = dict(market)
    better[actual] *= 3.0
    better = normalize(better)
    rows = [{
        "actual": actual,
        "beta_probs": {
            "0.00": market,
            "0.10": geometric_blend(market, better, 0.10),
            "0.25": geometric_blend(market, better, 0.25),
            "0.50": geometric_blend(market, better, 0.50),
            "1.00": better,
        },
    }]
    chosen, report = choose_beta(rows)
    assert chosen == 1.0
    assert report["selection_metric"] == "min_log_loss_then_brier_then_smaller_beta"


def test_source_freezes_all_beta_value_candidates_before_result_read():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_market_residual_value_walkforward_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("day_frozen = [") < source.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "profit_used_for_beta_selection" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_is_read_only_non_enumerating():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-market-residual-value-walkforward.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
