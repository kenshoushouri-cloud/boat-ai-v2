# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_tail_order_challenger_walkforward_pg import (
    CANDIDATES,
    aggregate,
    head_masses,
    place2_signal,
    reweight_tail_preserve_head,
)
from research import candidate_discovery_v4_contract as v4


def uniform_control():
    return {
        f"{a}-{b}-{c}": 1.0 / 120.0
        for a in v4.LANES
        for b in v4.LANES
        for c in v4.LANES
        if len({a, b, c}) == 3
    }


def test_candidate_family_is_fixed():
    assert len(CANDIDATES) == 9
    assert CANDIDATES["control"] == (0.0, 0.0, 0.0)
    assert CANDIDATES["p2_b030_s150_t050"] == (0.30, 1.50, 0.50)


def test_tail_reweight_preserves_first_place_marginal():
    control = uniform_control()
    signal = {1: 1.2, 2: 0.8, 3: 0.2, 4: -0.2, 5: -0.8, 6: -1.2}
    out = reweight_tail_preserve_head(
        control, signal, boost=0.3, second_weight=1.0, third_weight=0.5
    )
    before = head_masses(control)
    after = head_masses(out)
    assert set(out) == set(control)
    assert abs(sum(out.values()) - 1.0) < 1e-12
    for lane in v4.LANES:
        assert abs(before[lane] - after[lane]) < 1e-12


def test_place2_signal_prefers_high_place_rates():
    entries = []
    for lane in v4.LANES:
        entries.append(
            {
                "lane": lane,
                "national_place2_rate": 20.0 + lane * 5,
                "local_place2_rate": 18.0 + lane * 4,
            }
        )
    signal = place2_signal(entries)
    assert signal[6] > signal[5] > signal[1]


def test_aggregate_exact():
    rows = [
        {
            "races": 6,
            "investment_yen": 1200,
            "gross_return_yen": 1500,
            "profit_yen": 300,
            "top1_hits": 1,
            "top2_hits": 2,
            "log_loss_sum": 24.0,
            "actual_prob_sum": 0.12,
        },
        {
            "races": 6,
            "investment_yen": 1200,
            "gross_return_yen": 0,
            "profit_yen": -1200,
            "top1_hits": 0,
            "top2_hits": 1,
            "log_loss_sum": 30.0,
            "actual_prob_sum": 0.06,
        },
    ]
    got = aggregate(rows)
    assert got["races"] == 12
    assert got["top2_hits"] == 3
    assert got["top2_hit_rate_percent"] == 25.0
    assert got["gross_return_yen"] == 1500
    assert got["mean_log_loss"] == 4.5


def test_source_freezes_tail_candidates_before_results_and_is_read_only():
    root = Path(__file__).resolve().parents[1]
    source = (root / "research/v4_tail_order_challenger_walkforward_pg.py").read_text(
        encoding="utf-8"
    )
    assert source.index("freeze_candidate_tickets") < source.index(
        "hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "first_place_marginal_preserved" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_is_non_enumerating():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-tail-order-challenger-readonly.yml"
    ).read_text(encoding="utf-8").lower()
    assert "secrets.v4_backtest_database_url" in workflow
    assert "secrets.railway_token" in workflow
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
