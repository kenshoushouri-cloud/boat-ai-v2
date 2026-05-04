# -*- coding: utf-8 -*-
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtest.runner import run_backtest
from backtest.portfolio_runner import run_portfolio_backtest

START_DATE = "2025-03-13"
END_DATE = "2026-04-30"

STABLE_RUN_ID = "v2_stable_explore5_noodds_20250313_20260430"
ANA_RUN_ID = "v2_ana_explore5_noodds_20250313_20260430"
PORTFOLIO_RUN_ID = "v2_portfolio_explore5_noodds_20250313_20260430"

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

def _short(label, s):
    if not s:
        return f"{label}: 結果なし"
    return (
        f"{label}: 採用{s.get('adopted_races', 0)}R / "
        f"的中{s.get('hit_races', 0)}R / "
        f"投資{_yen(s.get('total_stake_yen', 0))} / "
        f"回収{_yen(s.get('total_payout_yen', 0))} / "
        f"損益{_safe_int(s.get('profit_yen', 0)):+,}円 / "
        f"ROI{_num(s.get('roi', 0), 1)}%"
    )

def main():
    print("=== 探索用・利用可能5場バックテスト開始 ===", flush=True)
    print(f"期間: {START_DATE} -> {END_DATE}", flush=True)
    print("対象: 01/06/12/18/24", flush=True)

    stable = run_backtest(START_DATE, END_DATE, mode="stable", run_id=STABLE_RUN_ID, odds_mode="no_odds")
    ana = run_backtest(START_DATE, END_DATE, mode="ana", run_id=ANA_RUN_ID, odds_mode="no_odds")
    portfolio = run_portfolio_backtest(START_DATE, END_DATE, STABLE_RUN_ID, ANA_RUN_ID, PORTFOLIO_RUN_ID)

    print("\n" + "=" * 72, flush=True)
    print("探索用バックテスト結果まとめ", flush=True)
    print("=" * 72, flush=True)
    print(f"stable_run_id:    {STABLE_RUN_ID}", flush=True)
    print(f"ana_run_id:       {ANA_RUN_ID}", flush=True)
    print(f"portfolio_run_id: {PORTFOLIO_RUN_ID}", flush=True)
    print(_short("stable", stable), flush=True)
    print(_short("ana", ana), flush=True)
    print(_short("portfolio", portfolio), flush=True)
    print("=" * 72, flush=True)

if __name__ == "__main__":
    main()