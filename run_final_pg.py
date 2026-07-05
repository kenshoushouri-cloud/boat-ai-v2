# -*- coding: utf-8 -*-
"""
run_final_pg.py

Railway Postgres版。
直前オッズ・最終判定・LINE通知用の起動ラッパー。

Railway Start Command:
    python run_final_pg.py
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("SNAPSHOT_LABEL", "final_ab")
os.environ.setdefault("DECISION_LABEL", "final_ab")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("REQUIRE_EXHIBITION", "0")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")
os.environ.setdefault("DAILY_LINE_LIMIT", "3")
os.environ.setdefault("MONTHLY_LINE_LIMIT", "100")
os.environ.setdefault("MAX_ITEMS_PER_MESSAGE", "6")
os.environ.setdefault("BATCH_NOTIFY", "1")

print("✅ run_final_pg.py", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"SNAPSHOT_LABEL={os.environ.get('SNAPSHOT_LABEL')}", flush=True)
print(f"DECISION_LABEL={os.environ.get('DECISION_LABEL')}", flush=True)
print(f"SELECTOR_MODE={os.environ.get('SELECTOR_MODE')}", flush=True)
print("Railway Postgres版：直前最終判定を開始します。", flush=True)

runpy.run_path("v25_final_realtime_pipeline_pg.py", run_name="__main__")