# -*- coding: utf-8 -*-
"""
run_performance_report_now.py
動作確認用。今月途中の月間成績 + 累積成績をLINE配信します。

Railway Start Command:
    python run_performance_report_now.py
"""

import os
import runpy

os.environ.setdefault("REPORT_MONTH", "current")
os.environ.setdefault("PERFORMANCE_START_DATE", "2026-06-28")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")

print("✅ run_performance_report_now.py", flush=True)
print(
    "REPORT_MONTH={m} PERFORMANCE_START_DATE={s} SELECTOR_MODE={mode}".format(
        m=os.environ.get("REPORT_MONTH"),
        s=os.environ.get("PERFORMANCE_START_DATE"),
        mode=os.environ.get("SELECTOR_MODE"),
    ),
    flush=True,
)

runpy.run_path("v27_performance_report_line.py", run_name="__main__")