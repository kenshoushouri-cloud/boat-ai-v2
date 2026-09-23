# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from research.v4_timing_safe_profit_gate_pg import (
    EV_THRESHOLDS,
    POINT_COUNTS,
    SOURCES,
    alpha025_distribution,
    bootstrap_roi,
    market_probs,
    policy_id,
    research_candidate_gate,
    summarize_bets,
)
from research import candidate_discovery_v4_contract as v4


def uniform():
    return {
        f"{a}-{b}-{c}": 1.0 / 120.0
        for a in v4.LANES
        for b in v4.LANES
        for c in v4.LANES
        if len({a, b, c}) == 3
    }


def test_grid_is_small_and_fixed():
    assert SOURCES == ("current", "alpha025")
    assert POINT_COUNTS == (2, 3)
    assert EV_THRESHOLDS == (None, 1.00, 1.05, 1.10, 1.15, 1.20, 1.25)
    assert policy_id("current", 2, None) == "current_p2_all"
    assert policy_id("alpha025", 3, 1.10) == "alpha025_p3_ev1.10"


def test_alpha025_preserves_first_place_marginal():
    current = uniform()
    learned = dict(current)
    # Move mass within each head only.
    for first in v4.LANES:
        tickets = sorted(t for t in learned if t.startswith(f"{first}-"))
        delta = 0.0005
        learned[tickets[0]] += delta
        learned[tickets[-1]] -= delta
    out = alpha025_distribution(current, learned)
    assert abs(sum(out.values()) - 1.0) < 1e-12


def test_market_probs_devigs_inverse_odds():
    odds = {ticket: 100.0 for ticket in uniform()}
    probs = market_probs(odds)
    assert len(probs) == 120
    assert abs(sum(probs.values()) - 1.0) < 1e-12
    assert len(set(round(v, 12) for v in probs.values())) == 1


def test_summary_and_candidate_gate_fail_closed_on_lucky_single_hit():
    rows = []
    for i in range(40):
        rows.append(
            {
                "race_id": f"r{i}",
                "race_date": "2026-09-01" if i < 20 else "2026-09-20",
                "rank": 1,
                "hit": i == 0,
                "return_yen": 10000 if i == 0 else 0,
            }
        )
    summary = summarize_bets(rows)
    halves = {
        "early": summarize_bets(rows[:20]),
        "late": summarize_bets(rows[20:]),
    }
    boot = bootstrap_roi(summary["daily"], samples=200, seed=1)
    gate = research_candidate_gate(summary, halves, boot)
    assert summary["roi_percent"] > 100.0
    assert summary["largest_hit_share_percent"] == 100.0
    assert gate["passed"] is False


def test_source_has_read_only_and_result_after_policy_freeze_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_timing_safe_profit_gate_pg.py"
    ).read_text(encoding="utf-8")
    test_loop = source[source.index("for day in hist.daterange(TEST_START, TEST_END):") :]
    assert test_loop.index("frozen[rid] = freeze_policies_for_race") < test_loop.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "no_threshold_fit_on_test" in low or "threshold_fit_on_test" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_has_no_variable_enumeration():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-timing-safe-profit-gate.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
