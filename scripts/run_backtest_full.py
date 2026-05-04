# -*- coding: utf-8 -*-
"""
全期間バックテスト実行用

Railway Shell / ローカル実行例:
    python scripts/run_backtest_full.py
"""

from backtest.runner import run_backtest
from backtest.portfolio_runner import run_portfolio_backtest


START_DATE = "2025-03-13"
END_DATE = "2026-04-30"

STABLE_RUN_ID = "v2_stable_20250313_20260430"
ANA_RUN_ID = "v2_ana_20250313_20260430"
PORTFOLIO_RUN_ID = "v2_portfolio_20250313_20260430"


def main():
    run_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        mode="stable",
        run_id=STABLE_RUN_ID,
    )

    run_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        mode="ana",
        run_id=ANA_RUN_ID,
    )

    run_portfolio_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        stable_run_id=STABLE_RUN_ID,
        ana_run_id=ANA_RUN_ID,
        portfolio_run_id=PORTFOLIO_RUN_ID,
    )


if __name__ == "__main__":
    main()