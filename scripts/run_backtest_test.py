# -*- coding: utf-8 -*-
"""
3日間テスト実行用

Railway Start Command:
    python scripts/run_backtest_test.py

変更点:
- stable / ana / portfolio の結果を最後にまとめて表示
- Railwayログで途中出力が前後しても、最終報告だけ見れば確認できる
"""

import os
import sys

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


def _yen(v):
    try:
        return f"{int(v):,}円"
    except Exception:
        return "0円"


def _num(v, digits=1):
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return f"{0:.{digits}f}"


def _print_one_summary(label, summary):
    print(f"\n[{label}]")

    if not summary:
        print("  結果なし")
        return

    total_races = summary.get("total_races", 0)
    adopted_races = summary.get("adopted_races", 0)
    hit_races = summary.get("hit_races", 0)
    hit_rate = summary.get("hit_rate", 0)
    stake = summary.get("total_stake_yen", 0)
    payout = summary.get("total_payout_yen", 0)
    profit = summary.get("profit_yen", 0)
    roi = summary.get("roi", 0)
    trigami_rate = summary.get("trigami_rate", 0)

    print(f"  run_id:       {summary.get('run_id')}")
    print(f"  対象レース数: {total_races}")
    print(f"  採用レース数: {adopted_races}")
    print(f"  的中レース数: {hit_races}")
    print(f"  的中率:       {_num(hit_rate, 1)}%")
    print(f"  投資額:       {_yen(stake)}")
    print(f"  回収額:       {_yen(payout)}")
    print(f"  損益:         {int(profit):+,}円")
    print(f"  回収率:       {_num(roi, 1)}%")
    print(f"  トリガミ率:   {_num(trigami_rate, 1)}%")
    print(f"  note:         {summary.get('note')}")


def _print_final_report(stable_summary, ana_summary, portfolio_summary):
    print("\n\n" + "=" * 72)
    print("最終テスト結果まとめ")
    print("=" * 72)
    print(f"期間: {START_DATE} -> {END_DATE}")
    print(f"stable_run_id:    {STABLE_RUN_ID}")
    print(f"ana_run_id:       {ANA_RUN_ID}")
    print(f"portfolio_run_id: {PORTFOLIO_RUN_ID}")

    _print_one_summary("stable / 安定モード", stable_summary)
    _print_one_summary("ana / 馬王モード", ana_summary)
    _print_one_summary("portfolio / 統合", portfolio_summary)

    print("\n" + "=" * 72)
    print("報告用ショート版")
    print("=" * 72)

    def short(label, s):
        if not s:
            return f"{label}: 結果なし"
        return (
            f"{label}: "
            f"採用{s.get('adopted_races', 0)}R / "
            f"的中{s.get('hit_races', 0)}R / "
            f"投資{_yen(s.get('total_stake_yen', 0))} / "
            f"回収{_yen(s.get('total_payout_yen', 0))} / "
            f"損益{int(s.get('profit_yen', 0)):+,}円 / "
            f"ROI{_num(s.get('roi', 0), 1)}%"
        )

    print(short("stable", stable_summary))
    print(short("ana", ana_summary))
    print(short("portfolio", portfolio_summary))
    print("=" * 72)


def main():
    stable_summary = run_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        mode="stable",
        run_id=STABLE_RUN_ID,
    )

    ana_summary = run_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        mode="ana",
        run_id=ANA_RUN_ID,
    )

    portfolio_summary = run_portfolio_backtest(
        start_date=START_DATE,
        end_date=END_DATE,
        stable_run_id=STABLE_RUN_ID,
        ana_run_id=ANA_RUN_ID,
        portfolio_run_id=PORTFOLIO_RUN_ID,
    )

    _print_final_report(
        stable_summary=stable_summary,
        ana_summary=ana_summary,
        portfolio_summary=portfolio_summary,
    )


if __name__ == "__main__":
    main()