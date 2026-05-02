# -*- coding: utf-8 -*-
from backtest.runner import run_backtest


def main():
    summary = run_backtest(
    start_date="2025-03-13",
    end_date="2026-04-30",
    run_id="v2.0.0_threshold_015",
    )

    if summary:
        print("\n=== 最終サマリー ===")
        print(f"採用レース: {summary['adopted_races']}")
        print(f"的中率:     {summary['hit_rate']:.1f}%")
        print(f"回収率:     {summary['roi']:.1f}%")
        print(f"損益:       {summary['profit_yen']:+,}円")
        print(f"トリガミ率: {summary['trigami_rate']:.1f}%")


if __name__ == "__main__":
    main()