# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_selector_challenger_walkforward_pg import (
    METRICS,
    SELECTORS,
    aggregate_days,
    choose_selector,
    percentile_rank,
)


def day(date, *, top2_hits, head_hits, gross, logloss):
    return {
        "date": date,
        "races": 6,
        "investment_yen": 1200,
        "gross_return_yen": gross,
        "profit_yen": gross - 1200,
        "top1_hits": 0,
        "top2_hits": top2_hits,
        "head_hits": head_hits,
        "log_loss_sum": logloss,
        "actual_prob_sum": 0.6,
        "selected": [],
    }


def test_selector_family_is_fixed_and_contains_current_contract():
    assert len(SELECTORS) == 15
    assert SELECTORS["current_equal4"] == METRICS
    assert METRICS == ("head_p1", "head_margin", "top3_mass", "concentration")


def test_percentile_rank_is_deterministic():
    rows = [
        {"race_id": "b", "head_p1": 0.4},
        {"race_id": "a", "head_p1": 0.4},
        {"race_id": "c", "head_p1": 0.2},
    ]
    ranks = percentile_rank(rows, "head_p1")
    assert ranks["a"] == 1.0
    assert ranks["b"] == 0.5
    assert ranks["c"] == 0.0


def test_aggregate_days_keeps_accuracy_and_economics_separate():
    rows = [
        day("2025-07-01", top2_hits=2, head_hits=3, gross=1600, logloss=18.0),
        day("2025-07-02", top2_hits=1, head_hits=2, gross=0, logloss=24.0),
    ]
    got = aggregate_days(rows)
    assert got["days"] == 2
    assert got["races"] == 12
    assert got["top2_hits"] == 3
    assert got["top2_hit_rate_percent"] == 25.0
    assert got["head_hits"] == 5
    assert got["gross_return_yen"] == 1600
    assert got["investment_yen"] == 2400
    assert got["mean_log_loss"] == 3.5


def test_choose_selector_uses_only_supplied_train_days():
    by = {name: {} for name in SELECTORS}
    for name in SELECTORS:
        by[name]["2025-07-01"] = day(
            "2025-07-01", top2_hits=0, head_hits=0, gross=0, logloss=60.0
        )
        by[name]["2025-08-01"] = day(
            "2025-08-01", top2_hits=0, head_hits=0, gross=0, logloss=60.0
        )
    by["head_p1_only"]["2025-07-01"] = day(
        "2025-07-01", top2_hits=6, head_hits=6, gross=3000, logloss=6.0
    )
    by["top3_mass_only"]["2025-08-01"] = day(
        "2025-08-01", top2_hits=6, head_hits=6, gross=3000, logloss=6.0
    )
    chosen, _ = choose_selector(by, ["2025-07-01"])
    assert chosen == "head_p1_only"


def test_source_freezes_all_selectors_before_result_query_and_is_read_only():
    root = Path(__file__).resolve().parents[1]
    source = (root / "research/v4_selector_challenger_walkforward_pg.py").read_text(
        encoding="utf-8"
    )
    assert source.index("frozen = freeze_selectors") < source.index(
        "results = fetch_results_after_freeze"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "all_selectors_frozen_before_result" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_has_non_enumerating_route_only():
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-selector-challenger-walkforward-readonly.yml"
    ).read_text(encoding="utf-8").lower()
    assert "secrets.v4_backtest_database_url" in workflow
    assert "secrets.railway_token" in workflow
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
    assert "".join(("env", " |")) not in workflow
