# -*- coding: utf-8 -*-
"""
run_v22_pg.py

Railway Postgres版 v22 起動ラッパー。
Variablesを毎回増減しなくても、通常値をコード側で設定します。

Railway Start Command:
    python -u run_v22_pg.py
"""
import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def _assert_pg_file():
    p = Path("v22_realtime_decision_engine_pg.py")
    if not p.exists():
        raise RuntimeError("v22_realtime_decision_engine_pg.py が見つかりません。")
    s = p.read_text(encoding="utf-8", errors="ignore")
    if "railway-postgres-short1" not in s:
        raise RuntimeError("v22_realtime_decision_engine_pg.py が古い、またはPG版ではありません。")

os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("SNAPSHOT_LABEL", "final_ab")
os.environ.setdefault("DECISION_LABEL", "final_ab")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("REQUIRE_EXHIBITION", "0")
os.environ.setdefault("SAVE_DECISIONS", "1")
os.environ.setdefault("MIN_ODDS", "3.0")
os.environ.setdefault("MAX_ODDS", "5.5")
os.environ.setdefault("MIN_ODDS_ROWS", "100")
os.environ.setdefault("MAX_WIND_M", "6.0")
os.environ.setdefault("MAX_WAVE_CM", "8.0")
os.environ.setdefault("BAD_EXH_TIME_DIFF", "0.18")
os.environ.setdefault("BAD_ST_DIFF", "0.10")
os.environ.setdefault("EVENT_DAY_LOOKBACK", "10")

print("✅ run_v22_pg.py", flush=True)
print(f"TARGET_DATE={os.environ.get('TARGET_DATE')}", flush=True)
print(f"SNAPSHOT_LABEL={os.environ.get('SNAPSHOT_LABEL')}", flush=True)
print(f"DECISION_LABEL={os.environ.get('DECISION_LABEL')}", flush=True)
print(f"SELECTOR_MODE={os.environ.get('SELECTOR_MODE')}", flush=True)
print("Railway Postgres版：v22直前判定を開始します。", flush=True)

_assert_pg_file()
runpy.run_path("v22_realtime_decision_engine_pg.py", run_name="__main__")