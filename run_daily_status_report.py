# -*- coding: utf-8 -*-
"""
run_daily_status_report.py
夜間結果取得・学習集計後に、日次稼働レポートをLINE配信します。

Railway Start Command:
    python run_daily_status_report.py

Cron Schedule:
    50 14 * * *

JSTでは毎日23:50です。
"""

import os
import runpy

os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")

print("✅ run_daily_status_report.py", flush=True)
print(
    "TARGET_DATE={d} SELECTOR_MODE={mode}".format(
        d=os.environ.get("TARGET_DATE", "today_jst"),
        mode=os.environ.get("SELECTOR_MODE"),
    ),
    flush=True,
)

runpy.run_path("v28_daily_status_report_line.py", run_name="__main__")