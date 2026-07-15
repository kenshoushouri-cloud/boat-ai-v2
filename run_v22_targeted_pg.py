# -*- coding: utf-8 -*-
"""TARGET_RACE_IDSのレースだけに絞って既存v22を実行するラッパー。"""
from __future__ import annotations
import os
from typing import Any, Dict, List, Tuple
import v22_realtime_decision_engine_pg as engine

TARGET_IDS={x.strip() for x in os.getenv("TARGET_RACE_IDS","").split(",") if x.strip()}
_original_live=engine._fetch_live_day_rows
_original_rt=engine._fetch_realtime_for_day

def _live(date_str: str):
    races, entries_by, odds_by = _original_live(date_str)
    if not TARGET_IDS:
        return [], {}, {}
    races=[r for r in races if str(r.get("race_id")) in TARGET_IDS]
    ids={str(r.get("race_id")) for r in races}
    return (
        races,
        {k:v for k,v in entries_by.items() if k in ids},
        {k:v for k,v in odds_by.items() if k in ids},
    )

def _rt(date_str: str, snapshot_label: str):
    exh, weather, odds, entries = _original_rt(date_str, snapshot_label)
    if not TARGET_IDS:
        return {}, {}, {}, {}
    return (
        {k:v for k,v in exh.items() if k in TARGET_IDS},
        {k:v for k,v in weather.items() if k in TARGET_IDS},
        {k:v for k,v in odds.items() if k in TARGET_IDS},
        {k:v for k,v in entries.items() if k in TARGET_IDS},
    )

def main() -> None:
    print("✅ run_v22_targeted_pg.py VERSION 2026-07-15 target-race-ids", flush=True)
    print(f"TARGET_RACE_IDS enabled: {len(TARGET_IDS)} races", flush=True)
    if not TARGET_IDS:
        print("今回の締切ウィンドウ対象は0件です。v22判定を終了します。", flush=True)
        return
    engine._fetch_live_day_rows=_live
    engine._fetch_realtime_for_day=_rt
    engine.main()

if __name__=="__main__":
    main()