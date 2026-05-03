# -*- coding: utf-8 -*-
print("BACKTEST START")  # 追加
from backtest.runner import run_backtest


def main():
    start = "2025-03-13"
    end = "2026-04-30"

    stable = run_backtest(start_date=start, end_date=end, mode="stable")

    if stable:
        print("\n=== 安定モード サマリー ===")
        print(f"採用レース: {stable['adopted_races']}")
        print(f"的中率:     {stable['hit_rate']:.1f}%")
        print(f"回収率:     {stable['roi']:.1f}%")
        print(f"損益:       {stable['profit_yen']:+,}円")
        print(f"1日平均投資: {stable['total_stake_yen'] / 409:.0f}円")
        

if __name__ == "__main__":
    main()