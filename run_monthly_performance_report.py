# -*- coding: utf-8 -*-
"""
run_monthly_performance_report.py
毎月1日に、前月成績 + 累積成績をLINE配信します。

Railway Start Command:
    python run_monthly_performance_report.py

Cron Schedule:
    10 15 1 * *

JSTでは毎月2日 0:10です。
"""

import os
import runpy

os.environ.setdefault("REPORT_MONTH", "previous")
os.environ.setdefault("PERFORMANCE_START_DATE", "2026-06-28")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")

print("✅ run_monthly_performance_report.py", flush=True)
print(
    "REPORT_MONTH={m} PERFORMANCE_START_DATE={s} SELECTOR_MODE={mode}".format(
        m=os.environ.get("REPORT_MONTH"),
        s=os.environ.get("PERFORMANCE_START_DATE"),
        mode=os.environ.get("SELECTOR_MODE"),
    ),
    flush=True,
)

runpy.run_path("v27_performance_report_line.py", run_name="__main__")