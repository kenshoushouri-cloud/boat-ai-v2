# -*- coding: utf-8 -*-
"""
backfill_k_date_range_pg.py

監査済み save_k_day_results_pg.py を日単位で呼び出す期間補修ランナー。
各日が独立プロセス＋独立トランザクションなので、異常日はその日だけ失敗/ROLLBACKし、
他の日の正常保存を壊さない。

環境変数:
  K_START_DATE=2026-08-01
  K_END_DATE=2026-08-15
  CONFIRM_K_DB_WRITE=YES
  STOP_ON_ERROR=1   # 推奨。1日でも異常ならそこで停止
"""
from __future__ import annotations
import os, subprocess, sys
from datetime import datetime, timedelta

VERSION="2026-08-17 k-range-backfill-v1"
START=os.getenv("K_START_DATE","2026-08-01")
END=os.getenv("K_END_DATE","2026-08-15")
CONFIRM=os.getenv("CONFIRM_K_DB_WRITE","")
STOP=os.getenv("STOP_ON_ERROR","1")=="1"

def days(a,b):
    d=datetime.strptime(a,"%Y-%m-%d").date()
    e=datetime.strptime(b,"%Y-%m-%d").date()
    if d>e: raise ValueError("K_START_DATE > K_END_DATE")
    while d<=e:
        yield d.isoformat()
        d += timedelta(days=1)

def main():
    print(f"✅ backfill_k_date_range_pg.py VERSION {VERSION}",flush=True)
    print(f"RANGE={START} -> {END} STOP_ON_ERROR={STOP}",flush=True)
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")
    if CONFIRM!="YES":
        raise RuntimeError("安全装置: CONFIRM_K_DB_WRITE=YES が必要です")
    if not os.path.exists("save_k_day_results_pg.py"):
        raise RuntimeError("save_k_day_results_pg.py が同じRepositoryに必要です")

    ok=[]; failed=[]
    for ds in days(START,END):
        print("="*88,flush=True)
        print(f"DAY START {ds}",flush=True)
        env=os.environ.copy()
        env["TARGET_DATE"]=ds
        env["CONFIRM_K_DB_WRITE"]="YES"
        p=subprocess.run(
            [sys.executable,"-u","save_k_day_results_pg.py"],
            env=env,
            text=True,
        )
        if p.returncode==0:
            ok.append(ds)
            print(f"DAY PASS {ds}",flush=True)
        else:
            failed.append(ds)
            print(f"DAY FAIL {ds} returncode={p.returncode}",flush=True)
            if STOP:
                break

    print("="*88,flush=True)
    print("=== RANGE SUMMARY ===",flush=True)
    print(f"requested_days={(datetime.strptime(END,'%Y-%m-%d').date()-datetime.strptime(START,'%Y-%m-%d').date()).days+1}",flush=True)
    print(f"passed_days={len(ok)} failed_days={len(failed)}",flush=True)
    if failed: print("failed="+",".join(failed),flush=True)
    print("RESULT="+("PASS" if not failed else "CHECK"),flush=True)
    if failed:
        raise SystemExit(1)

if __name__=="__main__":
    main()