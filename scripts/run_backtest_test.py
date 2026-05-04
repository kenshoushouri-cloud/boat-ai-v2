# -*- coding: utf-8 -*-
"""
3日間テスト実行用

Railway Start Command:
    python scripts/run_backtest_test.py

特徴:
- run_backtest の途中ログを一旦キャプチャ
- 最後に stable / ana / portfolio の結果だけを整理して表示
- エラー時だけ内部ログを表示
"""

import io
import os
import sys
import traceback
from contextlib import redirect_stdout

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


def _safe_int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


def _print_one_summary(label, summary):
    print(f"\n[{label}]")

    if not summary:
        print("  結果なし")
        return

    print(f"  run_id:       {summary.get('run_id')}")
    print(f"  対象レース数: {summary.get('total_races', 0)}")
    print(f"  採用レース数: {summary.get('adopted_races', 0)}")
    print(f"  的中レース数: {summary.get('hit_races', 0)}")
    print(f"  的中率:       {_num(summary.get('hit_rate', 0), 1)}%")
    print(f"  投資額:       {_yen(summary.get('total_stake_yen', 0))}")
    print(f"  回収額:       {_yen(summary.get('total_payout_yen', 0))}")
    print(f"  損益:         {_safe_int(summary.get('profit_yen', 0)):+,}円")
    print(f"  回収率:       {_num(summary.get('roi', 0), 1)}%")
    print(f"  トリガミ率:   {_num(summary.get('trigami_rate', 0), 1)}%")
    print(f"  note:         {summary.get('note')}")


def _short(label, summary):
    if not summary:
        return f"{label}: 結果なし"

    return (
        f"{label}: "
        f"採用{summary.get('adopted_races', 0)}R / "
        f"的中{summary.get('hit_races', 0)}R / "
        f"投資{_yen(summary.get('total_stake_yen', 0))} / "
        f"回収{_yen(summary.get('total_payout_yen', 0))} / "
        f"損益{_safe_int(summary.get('profit_yen', 0)):+,}円 / "
        f"ROI{_num(summary.get('roi', 0), 1)}%"
    )


def _run_safely(label, fn):
    buf = io.StringIO()

    try:
        with redirect_stdout(buf):
            result = fn()
        return result, None, buf.getvalue()

    except Exception as e:
        return None, e, buf.getvalue()


def main():
    print("=== バックテスト実行開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)

    stable_summary, stable_err, stable_log = _run_safely(
        "stable",
        lambda: run_backtest(
            start_date=START_DATE,
            end_date=END_DATE,
            mode="stable",
            run_id=STABLE_RUN_ID,
        )
    )

    ana_summary, ana_err, ana_log = _run_safely(
        "ana",
        lambda: run_backtest(
            start_date=START_DATE,
            end_date=END_DATE,
            mode="ana",
            run_id=ANA_RUN_ID,
        )
    )

    portfolio_summary, portfolio_err, portfolio_log = _run_safely(
        "portfolio",
        lambda: run_portfolio_backtest(
            start_date=START_DATE,
            end_date=END_DATE,
            stable_run_id=STABLE_RUN_ID,
            ana_run_id=ANA_RUN_ID,
            portfolio_run_id=PORTFOLIO_RUN_ID,
        )
    )

    print("\n" + "=" * 72, flush=True)
    print("最終テスト結果まとめ", flush=True)
    print("=" * 72, flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print(f"stable_run_id:    {STABLE_RUN_ID}", flush=True)
    print(f"ana_run_id:       {ANA_RUN_ID}", flush=True)
    print(f"portfolio_run_id: {PORTFOLIO_RUN_ID}", flush=True)

    _print_one_summary("stable / 安定モード", stable_summary)
    _print_one_summary("ana / 馬王モード", ana_summary)
    _print_one_summary("portfolio / 統合", portfolio_summary)

    print("\n" + "=" * 72, flush=True)
    print("報告用ショート版", flush=True)
    print("=" * 72, flush=True)
    print(_short("stable", stable_summary), flush=True)
    print(_short("ana", ana_summary), flush=True)
    print(_short("portfolio", portfolio_summary), flush=True)
    print("=" * 72, flush=True)

    errors = [
        ("stable", stable_err, stable_log),
        ("ana", ana_err, ana_log),
        ("portfolio", portfolio_err, portfolio_log),
    ]

    has_error = any(err for _, err, _ in errors)

    if has_error:
        print("\n" + "=" * 72, flush=True)
        print("エラー詳細", flush=True)
        print("=" * 72, flush=True)

        for label, err, log in errors:
            if not err:
                continue

            print(f"\n--- {label} error ---", flush=True)
            print(str(err), flush=True)
            print(traceback.format_exc(), flush=True)

            if log:
                print(f"\n--- {label} captured log ---", flush=True)
                print(log[-8000:], flush=True)


if __name__ == "__main__":
    main()