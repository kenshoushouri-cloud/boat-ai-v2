# -*- coding: utf-8 -*-
"""
run_v21_debug_pg.py

Railway Postgres版 v21 の軽量デバッグ起動。
1レースだけ取得して切り分けます。

Railway Start Command:
    python -u run_v21_debug_pg.py
"""

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def _assert_fix4_file():
    p = Path("v21_realtime_collector_pg.py")
    if not p.exists():
        raise RuntimeError("v21_realtime_collector_pg.py が見つかりません。")
    s = p.read_text(encoding="utf-8", errors="ignore")
    if "railway-postgres-fix4" not in s:
        raise RuntimeError("v21_realtime_collector_pg.py が古いです。fix4版で上書きしてください。")
    if "select race_id,lane,racer_number,racer_name,racer_class,motor_no,boat_no,tilt" in s:
        raise RuntimeError("v21_realtime_collector_pg.py に古いtilt明示SELECTが残っています。fix4版で上書きしてください。")

print("✅ run_v21_debug_pg.py fix4 start", flush=True)

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
print("✅ checking v21_realtime_collector_pg.py fix4", flush=True)

_assert_fix4_file()

print("✅ loading v21_realtime_collector_pg.py", flush=True)
runpy.run_path("v21_realtime_collector_pg.py", run_name="__main__")

print("✅ run_v21_debug_pg.py finished", flush=True)