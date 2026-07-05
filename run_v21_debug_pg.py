# -*- coding: utf-8 -*-
"""
run_v21_debug_pg.py

Railway Postgres版 v21 の軽量デバッグ起動。
止まって見える場合の切り分け用です。

通常の candidates 全件ではなく、まず1レースだけ取得します。
対象は TARGET_DATE の 22場4R をデフォルトにしています。

Railway Start Command:
    python -u run_v21_debug_pg.py
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

print("✅ run_v21_debug_pg.py start", flush=True)

target_date = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
default_race_id = target_date.replace("-", "") + "_22_04"

os.environ.setdefault("TARGET_DATE", target_date)
os.environ.setdefault("TARGET_RACE_ID", default_race_id)
os.environ.setdefault("SNAPSHOT_LABEL", "final_ab_debug")
os.environ.setdefault("COLLECT_SCOPE", "all")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("REALTIME_SLEEP_SEC", "0")
os.environ.setdefault("PARSE_ALLOW_PARTIAL", "0")
os.environ.setdefault("HTTP_TIMEOUT", "20")
os.environ.setdefault("RETRY_MAX", "1")
os.environ.setdefault("RETRY_SLEEP", "1.0")
os.environ.setdefault("ODDS_PAGE_SIZE", "1000")

print("✅ debug env set", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"TARGET_RACE_ID={os.environ.get('TARGET_RACE_ID')}", flush=True)
print(f"SNAPSHOT_LABEL={os.environ.get('SNAPSHOT_LABEL')}", flush=True)
print(f"COLLECT_SCOPE={os.environ.get('COLLECT_SCOPE')}", flush=True)
print("✅ loading v21_realtime_collector_pg.py", flush=True)

runpy.run_path("v21_realtime_collector_pg.py", run_name="__main__")

print("✅ run_v21_debug_pg.py finished", flush=True)