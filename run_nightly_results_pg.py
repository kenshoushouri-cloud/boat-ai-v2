# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版：当日結果取得。
同じ階層の repair_month_all_pg.py を実行します。

Start Command:
    python -u run_nightly_results_pg.py
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def main() -> None:
    print("✅ run_nightly_results_pg.py", flush=True)

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")
        os.environ["TARGET_DATE"] = target_date

    os.environ["REPAIR_START_DATE"] = target_date
    os.environ["REPAIR_END_DATE"] = target_date

    # 夜間結果取得：結果のみ。レース・出走表・オッズは触らない。
    os.environ["REPAIR_DO_RACES"] = "0"
    os.environ["REPAIR_DO_RESULTS"] = "1"
    os.environ["REPAIR_DO_ODDS"] = "0"

    os.environ.setdefault("REPAIR_WORKERS", os.getenv("WORKERS", "4"))
    os.environ.setdefault("REPAIR_ODDS_WORKERS", os.getenv("ODDS_WORKERS", "1"))
    os.environ.setdefault("REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1"))

    print(f"TARGET_DATE={target_date}", flush=True)
    print("Railway Postgres版：当日結果取得を開始します。", flush=True)

    base_dir = Path(__file__).resolve().parent
    repair_path = base_dir / "repair_month_all_pg.py"

    if not repair_path.exists():
        raise FileNotFoundError(f"repair_month_all_pg.py が見つかりません: {repair_path}")

    runpy.run_path(str(repair_path), run_name="__main__")


if __name__ == "__main__":
    main()