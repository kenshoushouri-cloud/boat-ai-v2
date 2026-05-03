# -*- coding: utf-8 -*-
from backtest.runner import run_backtest

def main():
    run_backtest(
        start_date="2025-03-13",
        end_date="2026-04-30",
        mode="ana",
    )

if __name__ == "__main__":
    main()