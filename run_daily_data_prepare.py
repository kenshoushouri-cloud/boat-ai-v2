# -*- coding: utf-8 -*-
"""
run_daily_data_prepare.py

当日予想前のデータ準備用。
今日のレース一覧・出走表・3連単オッズを取得します。
結果は夜の run_nightly_results_learning.py 側で取得します。

Railway Start Command:
    python run_daily_data_prepare.py
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
today = os.getenv("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))

os.environ["REPAIR_START_DATE"] = today
os.environ["REPAIR_END_DATE"] = today
os.environ.setdefault("REPAIR_DO_RACES", "1")
os.environ.setdefault("REPAIR_DO_RESULTS", "0")
os.environ.setdefault("REPAIR_DO_ODDS", "1")
os.environ.setdefault("REPAIR_WORKERS", "4")
os.environ.setdefault("REPAIR_ODDS_WORKERS", "2")

print("✅ run_daily_data_prepare.py", flush=True)
print(f"TARGET_DATE={today}", flush=True)
print("当日レース・出走表・オッズ取得を開始します。", flush=True)

runpy.run_path("repair_month_all_v5_fixed2.py", run_name="__main__")