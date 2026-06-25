# -*- coding: utf-8 -*-
"""
run_backfill_from_20260601.py

2026-06-01 から今日までの不足データを一括補修するワンタイム/手動用。
レース一覧・出走表・3連単オッズ・結果を取得します。

Railway Start Command:
    python run_backfill_from_20260601.py

任意:
    BACKFILL_START_DATE=2026-06-01
    BACKFILL_END_DATE=2026-06-25
"""

import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

start = os.getenv("BACKFILL_START_DATE", "2026-06-01")
end = os.getenv("BACKFILL_END_DATE", datetime.now(JST).strftime("%Y-%m-%d"))

os.environ["REPAIR_START_DATE"] = start
os.environ["REPAIR_END_DATE"] = end

# 全部取得。既にあるものはupsert/スキップされる想定。
os.environ.setdefault("REPAIR_DO_RACES", "1")
os.environ.setdefault("REPAIR_DO_RESULTS", "1")
os.environ.setdefault("REPAIR_DO_ODDS", "1")

# Railway負荷を抑えめにする
os.environ.setdefault("REPAIR_WORKERS", "4")
os.environ.setdefault("REPAIR_ODDS_WORKERS", "2")

print("✅ run_backfill_from_20260601.py", flush=True)
print(f"BACKFILL range: {start} -> {end}", flush=True)
print(
    "DO_RACES={r} DO_RESULTS={res} DO_ODDS={o}".format(
        r=os.environ.get("REPAIR_DO_RACES"),
        res=os.environ.get("REPAIR_DO_RESULTS"),
        o=os.environ.get("REPAIR_DO_ODDS"),
    ),
    flush=True,
)

runpy.run_path("repair_month_all_v5_fixed2.py", run_name="__main__")