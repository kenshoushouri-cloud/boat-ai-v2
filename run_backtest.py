# -*- coding: utf-8 -*-
from backtest.runner import run_backtest


def main():
    # テスト用: 直近1週間
    summary = run_backtest(
        start_date="2026-04-20",
        end_date="2026-04-27",
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