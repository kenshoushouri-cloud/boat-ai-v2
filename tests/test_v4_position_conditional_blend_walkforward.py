# -*- coding: utf-8 -*-
from pathlib import Path

from research import candidate_discovery_v4_contract as v4
from research.v4_position_conditional_blend_walkforward_pg import (
    ALPHAS,
    aggregate,
    blend_distribution,
    choose_alpha,
    first_marginals,
)


def control_distribution():
    raw = {lane: 7.0 - lane for lane in v4.LANES}
    return v4.ticket_probabilities(raw)


def learned_same_heads(control):
    heads = first_marginals(control)
    out = {}
    for first in v4.LANES:
        tails = [
            f"{first}-{second}-{third}"
            for second in v4.LANES
            if second != first
            for third in v4.LANES
            if third not in (first, second)
        ]
        for idx, ticket in enumerate(tails, 1):
            out[ticket] = heads[first] * idx
        subtotal = sum(out[t] for t in tails)
        scale = heads[first] / subtotal
        for ticket in tails:
            out[ticket] *= scale
    return v4._normalize_tickets(out)


def row(day, hits, logloss, gross=0):
    return {
        "date": day,
        "races": 6,
        "investment_yen": 1200,
        "gross_return_yen": gross,
        "profit_yen": gross - 1200,
        "top2_hits": hits,
        "log_loss_sum": logloss,
        "actual_prob_sum": 0.1,
    }


def test_alpha_family_is_small_and_frozen():
    assert ALPHAS == {
        "a000": 0.0,
        "a025": 0.25,
        "a050": 0.5,
        "a075": 0.75,
        "a100": 1.0,
    }


def test_blend_preserves_first_place_marginal_and_endpoints():
    control = control_distribution()
    learned = learned_same_heads(control)
    a0 = blend_distribution(control, learned, 0.0)
    a1 = blend_distribution(control, learned, 1.0)
    amid = blend_distribution(control, learned, 0.5)
    assert v4.top_tickets(a0, 5) == v4.top_tickets(control, 5)
    assert all(abs(a1[t] - learned[t]) < 1e-12 for t in learned)
    before = first_marginals(control)
    for candidate in (a0, amid, a1):
        after = first_marginals(candidate)
        for lane in v4.LANES:
            assert abs(before[lane] - after[lane]) < 1e-12


def test_choose_alpha_uses_only_supplied_prior_oos_and_is_conservative_on_tie():
    prior = {label: [] for label in ALPHAS}
    chosen, metrics = choose_alpha(prior)
    assert chosen == "a000"
    assert metrics is None

    for label in ALPHAS:
        prior[label].append(row("2025-08-15", 1, 24.0))
    chosen, _ = choose_alpha(prior)
    assert chosen == "a000"

    prior["a025"] = [row("2025-08-15", 2, 25.0)]
    chosen, _ = choose_alpha(prior)
    assert chosen == "a025"


def test_aggregate_exact():
    got = aggregate([
        row("2025-08-15", 2, 18.0, 1600),
        row("2025-08-16", 1, 24.0, 0),
    ])
    assert got["races"] == 12
    assert got["top2_hits"] == 3
    assert got["top2_hit_rate_percent"] == 25.0
    assert got["mean_log_loss"] == 3.5


def test_source_enforces_past_only_alpha_and_result_freeze():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_position_conditional_blend_walkforward_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("chosen_label, chosen_prior_metrics = choose_alpha(prior_oos)") < source.index(
        "results = hist.fetch_selected_results"
    )
    assert source.index("frozen = build_day_snapshot") < source.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "alpha_choice_uses_prior_unseen_blocks_only" in low
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
        root / ".github/workflows/v4-position-conditional-blend-readonly.yml"
    ).read_text(encoding="utf-8").lower()
    assert "secrets.v4_backtest_database_url" in workflow
    assert "secrets.railway_token" in workflow
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
