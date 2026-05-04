# -*- coding: utf-8 -*-
"""
3日間テスト実行用

Railway Start Command:
    python scripts/run_backtest_test.py
"""

import os
import sys

# Railwayで scripts/ から実行しても、プロジェクト直下の backtest/ models/ を読めるようにする
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtest.runner import run_backtest
from backtest.portfolio_runner import run_portfolio_backtest


START_DATE = "2026-04-01"
END_DATE = "2026-04-03"

STABLE_RUN_ID = "test_stable_20260401_20260403"
ANA_RUN_ID = "test_ana_20260401_20260403"
PORTFOLIO_RUN_ID = "test_portfolio_20260401_20260403"


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