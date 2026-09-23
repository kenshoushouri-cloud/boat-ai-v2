# -*- coding: utf-8 -*-
from research import candidate_discovery_v4_contract as v4
from research.v4_market_confirmation_value_pg import (
    GATES,
    MIN_ODDS,
    POINT_COUNTS,
    SOURCES,
    market_ranks,
    policy_id,
    split_eligible_dates,
    top_head,
)


def tickets():
    return [
        f"{a}-{b}-{c}"
        for a in v4.LANES
        for b in v4.LANES
        for c in v4.LANES
        if len({a, b, c}) == 3
    ]


def test_fixed_policy_family():
    assert SOURCES == ("current", "alpha025")
    assert POINT_COUNTS == (2, 3)
    assert GATES == (
        "head_agree",
        "ticket_market10",
        "head_agree_market10",
    )
    assert MIN_ODDS == (None, 3.0)
    assert policy_id("current", 2, "head_agree", None) == (
        "current_p2_head_agree_anyodds"
    )


def test_market_rank_is_lowest_odds_first():
    ts = tickets()
    odds = {ticket: 20.0 for ticket in ts}
    odds[ts[7]] = 2.0
    odds[ts[2]] = 3.0
    ranks = market_ranks(odds)
    assert ranks[ts[7]] == 1
    assert ranks[ts[2]] == 2


def test_top_head_uses_ticket_first_marginal():
    probs = {ticket: 1e-6 for ticket in tickets()}
    for ticket in probs:
        if ticket.startswith("3-"):
            probs[ticket] = 1.0
    assert top_head(probs) == 3


def test_eligible_date_split_is_chronological():
    dates = [f"2026-09-{day:02d}" for day in range(1, 11)]
    blocks = split_eligible_dates(dates)
    assert len(blocks) == 5
    flattened = [d for block in blocks for d in block]
    assert flattened == sorted(dates)


def test_source_freezes_confirmation_before_result_and_is_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_market_confirmation_value_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("policies, diag = freeze_confirmation_policies") < source.index(
        "results = hist.fetch_selected_results"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "no_heldout_policy_selection" in low
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
        root / ".github/workflows/v4-market-confirmation-value.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
