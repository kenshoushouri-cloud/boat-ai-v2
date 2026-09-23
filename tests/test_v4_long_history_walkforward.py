# -*- coding: utf-8 -*-
from pathlib import Path

from research.v4_long_history_selector_diagnostic import (
    bootstrap_rank_half,
    cumulative_metric,
    marginal_metric,
)
from research.v4_long_history_walkforward_pg import max_drawdown, split_blocks, strategy_stats


def row(day, daily_rank, actual, payout, ranked):
    return {
        "date": day,
        "race_id": f"{day}-{daily_rank}",
        "daily_rank": daily_rank,
        "actual_trifecta": actual,
        "payout_yen": payout,
        "ranked_top5": ranked,
    }


def test_long_replay_defaults_start_2025_07_and_stays_read_only():
    source = (Path(__file__).resolve().parents[1] / "research/v4_long_history_walkforward_pg.py").read_text(encoding="utf-8")
    assert '"2025-07-01"' in source
    assert '"2026-09-22"' in source
    assert "set transaction read only" in source
    assert source.index("frozen = freeze_day(cur, day)") < source.index("fetch_selected_results(cur, day, selected_ids)")
    low = source.lower()
    for forbidden in ("insert into", "update v2_", "delete from", "vacuum ", "purchase_action=true"):
        assert forbidden not in low


def test_existing_economics_helpers_remain_exact():
    ranked = ["1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"]
    rows = [
        row("2025-07-01", 1, "1-2-3", 500, ranked),
        row("2025-07-01", 2, "1-3-2", 900, ranked),
        row("2025-07-02", 3, "1-2-4", 1400, ranked),
    ]
    one = strategy_stats(rows, 1)
    three = strategy_stats(rows, 3)
    assert one["gross_return_yen"] == 500
    assert three["gross_return_yen"] == 2800
    assert max_drawdown([400, -100, -100, 800, -100]) == 200
    blocks = split_blocks(["2025-07-01","2025-07-02","2025-07-03","2025-07-04"], 2)
    assert [len(x) for x in blocks] == [2, 2]


def test_selector_diagnostic_keeps_formal_and_marginal_separate():
    ranked = ["1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"]
    rows = [
        row("2025-07-01", 1, "1-2-3", 500, ranked),
        row("2025-07-01", 4, "1-2-4", 1400, ranked),
    ]
    formal = cumulative_metric(rows, 2)
    third = marginal_metric(rows, 3)
    assert formal["investment_yen"] == 400
    assert formal["gross_return_yen"] == 500
    assert third["investment_yen"] == 200
    assert third["gross_return_yen"] == 1400


def test_bootstrap_is_deterministic_and_does_not_mutate_policy():
    ranked = ["1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"]
    rows = [
        row("2025-07-01", 1, "1-2-3", 500, ranked),
        row("2025-07-01", 4, "6-5-4", 1000, ranked),
        row("2025-07-02", 2, "1-3-2", 600, ranked),
        row("2025-07-02", 5, "6-5-4", 1000, ranked),
    ]
    a = bootstrap_rank_half(rows)
    b = bootstrap_rank_half(rows)
    assert a == b
    assert a["samples"] > 0


def test_workflow_has_dedicated_secret_only_and_no_railway_enumeration():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/v4-long-history-walkforward-readonly.yml").read_text(encoding="utf-8").lower()
    assert "v4_backtest_database_url" in workflow
    assert "railway variable list" not in workflow
    assert "railway-vars.json" not in workflow
    assert "railway_token" not in workflow
