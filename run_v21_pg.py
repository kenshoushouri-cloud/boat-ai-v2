# -*- coding: utf-8 -*-
"""
run_v21_pg.py

Railway Postgres版 v21 起動ラッパー。
v22のab判定と揃えるため、候補収集は1〜9R全場を含めます。

Railway Start Command:
    python -u run_v21_pg.py
"""

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def _assert_fix5_file():
    p = Path("v21_realtime_collector_pg.py")
    if not p.exists():
        raise RuntimeError("v21_realtime_collector_pg.py が見つかりません。")
    s = p.read_text(encoding="utf-8", errors="ignore")
    if "railway-postgres-fix5-scope" not in s:
        raise RuntimeError("v21_realtime_collector_pg.py が古いです。fix5-scope版で上書きしてください。")

os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("SNAPSHOT_LABEL", "final_ab")
os.environ.setdefault("COLLECT_SCOPE", "candidates")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("REALTIME_SLEEP_SEC", "0.10")
os.environ.setdefault("PARSE_ALLOW_PARTIAL", "0")
os.environ.setdefault("HTTP_TIMEOUT", "35")
os.environ.setdefault("RETRY_MAX", "2")
os.environ.setdefault("RETRY_SLEEP", "2.0")
os.environ.setdefault("ODDS_PAGE_SIZE", "1000")

print("✅ run_v21_pg.py fix5-scope", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"SNAPSHOT_LABEL={os.environ.get('SNAPSHOT_LABEL')}", flush=True)
print(f"COLLECT_SCOPE={os.environ.get('COLLECT_SCOPE')}", flush=True)
print("Railway Postgres版：v21直前情報収集を開始します。", flush=True)

_assert_fix5_file()
runpy.run_path("v21_realtime_collector_pg.py", run_name="__main__")