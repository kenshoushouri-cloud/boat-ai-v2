# -*- coding: utf-8 -*-
"""
run_pre_night_pg.py

Railway Postgres版。
ナイター・ミッドナイト向けの仮候補通知。

Railway Start Command:
    python run_pre_night_pg.py
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("PRE_SESSION", "night")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")
os.environ.setdefault("DAILY_LINE_LIMIT", "3")
os.environ.setdefault("MONTHLY_LINE_LIMIT", "100")
os.environ.setdefault("MAX_ITEMS_PER_MESSAGE", "6")
os.environ.setdefault("MIN_ODDS_ROWS", "100")

print("✅ run_pre_night_pg.py", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"PRE_SESSION={os.environ.get('PRE_SESSION')}", flush=True)
print("Railway Postgres版：ナイター仮候補通知を開始します。", flush=True)

runpy.run_path("v24_pre_candidate_notifier_pg.py", run_name="__main__")