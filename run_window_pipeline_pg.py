# -*- coding: utf-8 -*-
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
    return (os.getenv(name, default) or default).strip() in (
        "1", "true", "True", "yes", "YES"
    )

def main() -> None:
    print("✅ run_window_pipeline_pg.py VERSION 2026-07-29-quality-guard", flush=True)

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    os.environ["TARGET_DATE"] = target_date

    window_name = (os.getenv("WINDOW_NAME") or "morning").strip().lower()
    os.environ["WINDOW_NAME"] = window_name

    run_odds = _bool_env("WINDOW_RUN_ODDS", "1")
    run_pre = _bool_env("WINDOW_RUN_PRE", "1")
    sleep_after_odds = float(os.getenv("WINDOW_SLEEP_AFTER_ODDS_SEC", "0"))

    os.environ.setdefault("WINDOW_SKIP_FULL_ODDS", "1")
    os.environ.setdefault("WINDOW_ODDS_RETRIES", "2")
    os.environ.setdefault("WINDOW_ODDS_RETRY_WAIT_SEC", "30")

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_RUN_ODDS={run_odds}", flush=True)
    print(f"WINDOW_RUN_PRE={run_pre}", flush=True)
    print(f"WINDOW_SKIP_FULL_ODDS={os.getenv('WINDOW_SKIP_FULL_ODDS')}", flush=True)
    print(f"WINDOW_ODDS_RETRIES={os.getenv('WINDOW_ODDS_RETRIES')}", flush=True)
    print(f"WINDOW_ODDS_RETRY_WAIT_SEC={os.getenv('WINDOW_ODDS_RETRY_WAIT_SEC')}", flush=True)
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