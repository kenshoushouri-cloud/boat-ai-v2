# -*- coding: utf-8 -*-
from research import candidate_discovery_v4_contract as v4
from research.v4_market_core_residual_value_pg import (
    MARKET_RANK_CAPS,
    POINT_COUNTS,
    candidate_gate,
    freeze_race,
    policy_id,
    summarize,
)


def ticket_probs():
    tickets = [
        f"{a}-{b}-{c}"
        for a in v4.LANES
        for b in v4.LANES
        for c in v4.LANES
        if len({a, b, c}) == 3
    ]
    weights = {ticket: float(len(tickets) - idx) for idx, ticket in enumerate(tickets)}
    total = sum(weights.values())
    return {ticket: value / total for ticket, value in weights.items()}


def test_policy_family_is_small_and_fixed():
    assert MARKET_RANK_CAPS == (5, 10, 20)
    assert POINT_COUNTS == (2, 3)
    assert policy_id(10, 2) == "market_top10_residual_p2"


def test_freeze_restricts_candidates_to_market_core_and_positive_residual():
    market_probs = ticket_probs()
    # Pick odds whose de-vig inverse probabilities match market_probs.
    odds = {ticket: 1.0 / prob for ticket, prob in market_probs.items()}
    # Model starts at market then moves probability among the top market tickets.
    model = dict(market_probs)
    ranked = sorted(market_probs, key=lambda t: (-market_probs[t], t))
    model[ranked[0]] += 0.002
    model[ranked[1]] += 0.001
    model[ranked[4]] -= 0.003
    model = v4._normalize_tickets(model)
    row = {"probabilities": {"alpha025": model}}
    frozen = freeze_race(row, {"odds": odds})
    bets = frozen["market_top5_residual_p2"]
    assert len(bets) == 2
    assert all(int(bet["market_rank"]) <= 5 for bet in bets)
    assert all(float(bet["residual_ratio"]) > 1.0 for bet in bets)


def test_gate_rejects_single_hit_dependence_even_when_roi_positive():
    rows = []
    for idx in range(40):
        rows.append(
            {
                "race_id": f"r{idx}",
                "race_date": "2026-09-01" if idx < 20 else "2026-09-20",
                "rank": 1,
                "market_rank": 3,
                "residual_ratio": 1.2,
                "hit": idx == 0,
                "return_yen": 10000 if idx == 0 else 0,
            }
        )
    summary = summarize(rows)
    gate = candidate_gate(
        summary,
        summarize(rows[:20]),
        summarize(rows[20:]),
        {"positive_share_percent": 99.0},
    )
    assert summary["roi_percent"] > 100.0
    assert summary["largest_hit_share_percent"] == 100.0
    assert gate["passed"] is False


def test_source_freezes_before_result_and_is_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_market_core_residual_value_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("frozen[rid] = freeze_race") < source.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
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
        root / ".github/workflows/v4-market-core-residual-value.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
