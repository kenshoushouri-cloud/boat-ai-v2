# -*- coding: utf-8 -*-
"""
run_daily_data_prepare_pg.py

Railway Postgres版：当日レース・出走表・オッズ取得用ランナー。

Railway Start Command:
    python -u run_daily_data_prepare_pg.py

ポイント:
- TARGET_DATE が未設定ならJSTの当日を使う。
- repair_month_all_pg.py はこのファイルと同じ階層から絶対パスで実行する。
  Railwayの作業ディレクトリ差異による FileNotFoundError を防ぐ。
"""

from __future__ import annotations

import os
import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).resolve().parent

# 同じ階層の db_pg.py / repair_month_all_pg.py を確実にimport・実行できるようにする
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


target_date = os.environ.setdefault("TARGET_DATE", _today_jst())

# 当日1日分を対象にする
os.environ.setdefault("REPAIR_START_DATE", target_date)
os.environ.setdefault("REPAIR_END_DATE", target_date)

# 全場・全R
os.environ.setdefault(
    "REPAIR_VENUES",
    "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24",
)
os.environ.setdefault("REPAIR_RACE_NOS", "1,2,3,4,5,6,7,8,9,10,11,12")

# 日中準備: レース・出走表・オッズを取得。結果は夜に取得。
os.environ.setdefault("REPAIR_DO_RACES", "1")
os.environ.setdefault("REPAIR_DO_RESULTS", "0")
os.environ.setdefault("REPAIR_DO_ODDS", "1")

# Railway Hobby向けの安全寄り設定
os.environ.setdefault("REPAIR_WORKERS", "4")
os.environ.setdefault("REPAIR_ODDS_WORKERS", "2")
os.environ.setdefault("REPAIR_SLEEP_SEC", "0.1")
os.environ.setdefault("REPAIR_SOURCE", "run_daily_data_prepare_pg")

print("✅ run_daily_data_prepare_pg.py", flush=True)
print(f"TARGET_DATE={target_date}", flush=True)
print("Railway Postgres版：当日レース・出走表・オッズ取得を開始します。", flush=True)

repair_path = BASE_DIR / "repair_month_all_pg.py"
if not repair_path.exists():
    raise FileNotFoundError(f"repair_month_all_pg.py が見つかりません: {repair_path}")

runpy.run_path(str(repair_path), run_name="__main__")