# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

print("✅ run_daily_data_prepare_pg.py", flush=True)

target_date = os.getenv("TARGET_DATE")
if not target_date:
    target_date = datetime.now(JST).strftime("%Y-%m-%d")
    os.environ["TARGET_DATE"] = target_date

os.environ["REPAIR_START_DATE"] = target_date
os.environ["REPAIR_END_DATE"] = target_date

os.environ["REPAIR_DO_RACES"] = "1"
os.environ["REPAIR_DO_RESULTS"] = "0"
os.environ["REPAIR_DO_ODDS"] = "1"

print(f"TARGET_DATE={target_date}", flush=True)
print("Railway Postgres版：当日レース・出走表・オッズ取得を開始します。", flush=True)

BASE_DIR = Path(__file__).resolve().parent
CWD = Path.cwd()

candidates = [
    BASE_DIR / "repair_month_all_pg.py",
    CWD / "repair_month_all_pg.py",
    BASE_DIR.parent / "repair_month_all_pg.py",
    Path("/app/repair_month_all_pg.py"),
    Path("/app/app/repair_month_all_pg.py"),
    Path("/app/boat-ai-v2/repair_month_all_pg.py"),
]

repair_path = None
for p in candidates:
    if p.exists():
        repair_path = p
        break

if repair_path is None:
    print("❌ repair_month_all_pg.py が見つかりません", flush=True)
    print(f"__file__={__file__}", flush=True)
    print(f"BASE_DIR={BASE_DIR}", flush=True)
    print(f"CWD={CWD}", flush=True)

    print("=== /app files sample ===", flush=True)
    app_root = Path("/app")
    if app_root.exists():
        for p in sorted(app_root.rglob("*"))[:300]:
            try:
                print(str(p), flush=True)
            except Exception:
                pass

    raise FileNotFoundError("repair_month_all_pg.py がRailwayコンテナ内に存在しません")

print(f"✅ repair script found: {repair_path}", flush=True)
runpy.run_path(str(repair_path), run_name="__main__")