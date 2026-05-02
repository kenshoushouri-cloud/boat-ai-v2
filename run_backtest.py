# -*- coding: utf-8 -*-
from backtest.runner import run_backtest


def main():
    start = "2025-03-13"
    end = "2026-04-30"

    # 安定モード
    print("\n" + "=" * 60)
    print("安定モード バックテスト")
    print("=" * 60)
    stable = run_backtest(start_date=start, end_date=end, mode="stable")

    if stable:
        print("\n=== 安定モード サマリー ===")
        print(f"採用レース: {stable['adopted_races']}")
        print(f"的中率:     {stable['hit_rate']:.1f}%")
        print(f"回収率:     {stable['roi']:.1f}%")
        print(f"損益:       {stable['profit_yen']:+,}円")

    # 馬王モード
    print("\n" + "=" * 60)
    print("馬王モード バックテスト")
    print("=" * 60)
    ana = run_backtest(start_date=start, end_date=end, mode="ana")

    if ana:
        print("\n=== 馬王モード サマリー ===")
        print(f"採用レース: {ana['adopted_races']}")
        print(f"的中率:     {ana['hit_rate']:.1f}%")
        print(f"回収率:     {ana['roi']:.1f}%")
        print(f"損益:       {ana['profit_yen']:+,}円")


if __name__ == "__main__":
    main()