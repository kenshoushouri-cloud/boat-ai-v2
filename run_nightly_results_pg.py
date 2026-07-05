# -*- coding: utf-8 -*-
"""
run_nightly_results_pg.py

Railway Postgres版。
夜間の結果取得用。
当日の全場・全Rについて、結果だけを取得して v2_results に保存します。

Railway Start Command:
    python run_nightly_results_pg.py

通常運用:
    日本時間 23:30 以降に実行

テスト時:
    TARGET_DATE=2026-07-05 などを指定可能
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
today = os.getenv("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))

os.environ["REPAIR_START_DATE"] = today
os.environ["REPAIR_END_DATE"] = today

# 結果だけ取得
os.environ.setdefault("REPAIR_DO_RACES", "0")
os.environ.setdefault("REPAIR_DO_RESULTS", "1")
os.environ.setdefault("REPAIR_DO_ODDS", "0")

# 結果取得は軽めなので、並列は少しだけ上げてもOK
os.environ.setdefault("REPAIR_WORKERS", "4")
os.environ.setdefault("REPAIR_ODDS_WORKERS", "1")
os.environ.setdefault("REPAIR_SLEEP_SEC", "0.1")

print("✅ run_nightly_results_pg.py", flush=True)
print(f"TARGET_DATE={today}", flush=True)
print("Railway Postgres版：当日結果取得を開始します。", flush=True)

runpy.run_path("repair_month_all_pg.py", run_name="__main__")