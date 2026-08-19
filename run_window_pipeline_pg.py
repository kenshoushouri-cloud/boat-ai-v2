# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-20 window-pipeline-motor2-shadow-v4"

def _today_jst():
    return datetime.now(JST).strftime("%Y-%m-%d")

def _bool_env(name, default="1"):
    return (os.getenv(name, default) or default).strip() in ("1","true","True","yes","YES")

def main():
    print(f"✅ run_window_pipeline_pg.py VERSION {VERSION}", flush=True)

    target_date=os.getenv("TARGET_DATE") or _today_jst()
    os.environ["TARGET_DATE"]=target_date
    window_name=(os.getenv("WINDOW_NAME") or "morning").strip().lower()
    os.environ["WINDOW_NAME"]=window_name

    run_odds=_bool_env("WINDOW_RUN_ODDS","1")
    run_motor2=_bool_env("WINDOW_RUN_MOTOR2_SHADOW","1")
    run_pre=_bool_env("WINDOW_RUN_PRE","1")
    sleep_after_odds=float(os.getenv("WINDOW_SLEEP_AFTER_ODDS_SEC","0"))

    os.environ.setdefault("WINDOW_SKIP_FULL_ODDS","1")
    os.environ.setdefault("WINDOW_ODDS_RETRIES","2")
    os.environ.setdefault("WINDOW_ODDS_RETRY_WAIT_SEC","30")

    print(f"TARGET_DATE={target_date}",flush=True)
    print(f"WINDOW_NAME={window_name}",flush=True)
    print(f"WINDOW_RUN_ODDS={run_odds}",flush=True)
    print(f"WINDOW_RUN_MOTOR2_SHADOW={run_motor2}",flush=True)
    print(f"WINDOW_RUN_PRE={run_pre}",flush=True)
    print(f"DATABASE_URL={'OK' if os.getenv('DATABASE_URL') else 'MISSING'}",flush=True)

    base_dir=Path(__file__).resolve().parent
    os.environ.pop("MOTOR2_SHADOW_TARGET_RACE_IDS",None)

    if run_odds:
        p=base_dir/"run_odds_window_pg.py"
        if not p.exists(): raise FileNotFoundError(p)
        print("=== STEP 1: odds window start ===",flush=True)
        runpy.run_path(str(p),run_name="__main__")
        print("=== STEP 1: odds window done ===",flush=True)
        if sleep_after_odds>0: time.sleep(sleep_after_odds)

    if run_motor2:
        target_ids=(os.getenv("MOTOR2_SHADOW_TARGET_RACE_IDS") or "").strip()
        if not target_ids:
            print("=== STEP 1.5: Motor2 Shadow skipped (window target ids empty) ===",flush=True)
        else:
            p=base_dir/"collect_v24_motor2_forward_shadow_pg.py"
            if not p.exists(): raise FileNotFoundError(p)
            os.environ["MOTOR2_SHADOW_RUN_CLASS"]="live"
            os.environ.setdefault("MOTOR2_SHADOW_SESSION","all")
            os.environ["MOTOR2_SHADOW_SNAPSHOT_KEY"]=(
                f"{target_date.replace('-','')}_{window_name}_{datetime.now(JST).strftime('%H%M%S')}"
            )
            print("=== STEP 1.5: Motor2 Forward Shadow start ===",flush=True)
            print(f"window_target_ids={len([x for x in target_ids.split(',') if x.strip()])}",flush=True)
            runpy.run_path(str(p),run_name="__main__")
            print("=== STEP 1.5: Motor2 Forward Shadow done ===",flush=True)

    if run_pre:
        p=base_dir/"run_pre_window_pg.py"
        if not p.exists(): raise FileNotFoundError(p)
        print("=== STEP 2: pre window start ===",flush=True)
        runpy.run_path(str(p),run_name="__main__")
        print("=== STEP 2: pre window done ===",flush=True)

    print("=== window pipeline finished ===",flush=True)

if __name__=="__main__":
    main()