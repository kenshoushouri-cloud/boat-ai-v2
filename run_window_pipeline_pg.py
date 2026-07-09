# -*- coding: utf-8 -*-
"""
run_window_pipeline_pg.py

Railway Postgres版：時間帯ウィンドウ用の一括パイプライン。
1つのServiceで「対象ウィンドウのオッズ再取得」→「対象ウィンドウの仮候補抽出」を順に実行します。

Start Command:
    python -u run_window_pipeline_pg.py

主な環境変数:
    TARGET_DATE=2026-07-09          # 未指定ならJST当日
    WINDOW_NAME=morning|day|night   # morning/day/night のプリセット
    WINDOW_START=08:30              # WINDOW_NAMEより優先したい場合だけ指定
    WINDOW_END=10:15
    WINDOW_WORKERS=2
    WINDOW_SKIP_FULL_ODDS=0
    WINDOW_RUN_ODDS=1
    WINDOW_RUN_PRE=1

LINE/通知系:
    DRY_RUN=1
    TEST_MODE=1
    DAILY_LINE_LIMIT=3

想定Service:
    cron-window-morning: WINDOW_NAME=morning
    cron-window-day:     WINDOW_NAME=day
    cron-window-night:   WINDOW_NAME=night
"""

from __future__ import annotations

import os
import runpy
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def _bool_env(name: str, default: str = "1") -> bool:
    return (os.getenv(name, default) or default).strip() in ("1", "true", "True", "yes", "YES")


def main() -> None:
    print("✅ run_window_pipeline_pg.py VERSION 2026-07-09", flush=True)

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    os.environ["TARGET_DATE"] = target_date

    window_name = (os.getenv("WINDOW_NAME") or "morning").strip().lower()
    os.environ["WINDOW_NAME"] = window_name

    run_odds = _bool_env("WINDOW_RUN_ODDS", "1")
    run_pre = _bool_env("WINDOW_RUN_PRE", "1")
    sleep_after_odds = float(os.getenv("WINDOW_SLEEP_AFTER_ODDS_SEC", "0"))

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_RUN_ODDS={run_odds}", flush=True)
    print(f"WINDOW_RUN_PRE={run_pre}", flush=True)
    print(f"DRY_RUN={os.getenv('DRY_RUN', '')}", flush=True)
    print(f"TEST_MODE={os.getenv('TEST_MODE', '')}", flush=True)
    print(f"DAILY_LINE_LIMIT={os.getenv('DAILY_LINE_LIMIT', '')}", flush=True)
    print(f"DATABASE_URL={'OK' if os.getenv('DATABASE_URL') else 'MISSING'}", flush=True)

    base_dir = Path(__file__).resolve().parent

    if run_odds:
        odds_path = base_dir / "run_odds_window_pg.py"
        if not odds_path.exists():
            raise FileNotFoundError(f"run_odds_window_pg.py が見つかりません: {odds_path}")

        print("=== STEP 1: odds window start ===", flush=True)
        runpy.run_path(str(odds_path), run_name="__main__")
        print("=== STEP 1: odds window done ===", flush=True)

        if sleep_after_odds > 0:
            print(f"sleep_after_odds={sleep_after_odds}", flush=True)
            time.sleep(sleep_after_odds)

    if run_pre:
        pre_path = base_dir / "run_pre_window_pg.py"
        if not pre_path.exists():
            raise FileNotFoundError(f"run_pre_window_pg.py が見つかりません: {pre_path}")

        print("=== STEP 2: pre window start ===", flush=True)
        runpy.run_path(str(pre_path), run_name="__main__")
        print("=== STEP 2: pre window done ===", flush=True)

    print("=== window pipeline finished ===", flush=True)


if __name__ == "__main__":
    main()