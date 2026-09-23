# -*- coding: utf-8 -*-
from research.v4_point_count_historical_walkforward_pg import (
    max_drawdown,
    split_blocks,
    strategy_stats,
)


def row(actual, payout, ranked):
    return {
        "actual_trifecta": actual,
        "payout_yen": payout,
        "ranked_top5": ranked,
        "date": "2026-07-01",
    }


def test_strategy_stats_cumulative_and_marginal_are_distinct():
    rows = [
        row("1-2-3", 500, ["1-2-3","1-3-2","1-2-4","1-4-2","1-3-4"]),
        row("2-3-1", 900, ["2-1-3","2-3-1","2-1-4","2-4-1","2-3-4"]),
        row("3-1-4", 1400, ["3-1-2","3-2-1","3-1-4","3-4-1","3-2-4"]),
    ]

    one = strategy_stats(rows, 1)
    two = strategy_stats(rows, 2)
    three = strategy_stats(rows, 3)

    assert one["gross_return_yen"] == 500
    assert one["investment_yen"] == 300
    assert one["profit_yen"] == 200
    assert one["marginal"]["gross_return_yen"] == 500

    assert two["gross_return_yen"] == 1400
    assert two["investment_yen"] == 600
    assert two["profit_yen"] == 800
    assert two["marginal"]["gross_return_yen"] == 900
    assert two["marginal"]["profit_yen"] == 600

    assert three["gross_return_yen"] == 2800
    assert three["investment_yen"] == 900
    assert three["profit_yen"] == 1900
    assert three["marginal"]["gross_return_yen"] == 1400
    assert three["marginal"]["profit_yen"] == 1100


def test_max_drawdown_uses_chronological_profit_path():
    assert max_drawdown([400, -100, -100, 800, -100]) == 200
    assert max_drawdown([-100, -100, 500]) == 200


def test_walkforward_blocks_are_chronological_and_cover_all_days_once():
    days = [f"2026-07-{day:02d}" for day in range(1, 11)]
    blocks = split_blocks(days, 4)
    assert [len(block) for block in blocks] == [3, 3, 2, 2]
    assert set().union(*blocks) == set(days)
    assert sum(len(block) for block in blocks) == len(days)


def test_source_enforces_read_only_and_result_after_freeze_boundary():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "research/v4_point_count_historical_walkforward_pg.py"
    ).read_text(encoding="utf-8")

    assert "set transaction read only" in source
    assert "fetch_selected_results(cur, day, selected_ids)" in source
    assert "frozen = freeze_day(cur, day)" in source
    assert source.index("frozen = freeze_day(cur, day)") < source.index(
        "fetch_selected_results(cur, day, selected_ids)"
    )
    assert "v4.select_daily(" in source
    assert "v4.top_tickets(distributions[rid], 5)" in source
    assert "NO_5R_SHRINK" in source
    assert "NO_REPLACEMENT" in source

    low = source.lower()
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "send_line",
        "line_notify",
        "purchase_action=true",
    ):
        assert forbidden not in low, forbidden


def test_workflow_never_enumerates_railway_variables_or_uses_railway_token():
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/v4-point-count-historical-walkforward-readonly.yml"
    ).read_text(encoding="utf-8").lower()

    assert "railway variable list" not in workflow
    assert "railway-vars.json" not in workflow
    assert "railway_token" not in workflow
    assert "v4_backtest_database_url" in workflow
