"""Native V5 direct OFFICIAL day program -> physical stage core (races/entries).

No public.v2_* DB reads/writes. Official event index discovers venues.
Official 1..12 racelists are verified individually. --apply is DISABLED by
default, requires upstream one-race stage canary guards and systemd review.
A bounded run FAILS (does not claim full success) on partial/errored targets.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import os
import time

from v5.native_official_index_preview import JST, choose_day, fetch_official_index, official_venues
from v5.native_stage_race_entries_pg import official_fetch, official_payload, apply_one, blocked_by_stage_delta

GATES = ("V5_NATIVE_CORE_STAGE_WRITE_APPROVED",
         "CONFIRM_V5_SHARED_PRIMARY_CANARY",
         "CONFIRM_LEGACY_WRITES_SEPARATELY")

def authorize() -> None:
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_DB_REQUIRED")
    if os.environ.get("V5_SHARED_PRIMARY_MODE") != "CANARY":
        raise RuntimeError("HOLD_ONLY_STAGED_CANARY_MODE")
    for name in GATES:
        if os.environ.get(name) != "YES":
            raise RuntimeError("HOLD_MISSING_GATE_" + name)
    for k in ("BUY_ENABLED","AUTO_BUY","ENABLE_PURCHASE"):
        if os.environ.get(k,"").upper() in ("1","YES","ON","TRUE"):
            raise RuntimeError("HOLD_BUY_ENABLED")
    blocked_by_stage_delta()

def target_ids(day,venues,max_venues=24,max_race_no=12):
    if not 1 <= max_venues <= 24 or not 1 <= max_race_no <= 12:
        raise ValueError("HOLD_OUT_OF_RANGE_DAY_PLAN")
    return [f"{day}_{venue}_{rno:02d}"
            for venue in venues[:max_venues]
            for rno in range(1,max_race_no+1)]

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day",default=None)
    ap.add_argument("--scope",choices=("today","tomorrow"),default="tomorrow")
    ap.add_argument("--apply",action="store_true")
    ap.add_argument("--max-venues",type=int,default=1)
    ap.add_argument("--max-race-no",type=int,default=1)
    ap.add_argument("--max-requests",type=int,default=200)
    opts=ap.parse_args(argv)
    now=datetime.now(JST)
    requested=opts.day or (now.date().strftime("%Y%m%d") if opts.scope=="today" else None)
    day=choose_day(now,requested)
    if opts.apply:
        authorize()  # deny before any HTTP request
    if not 1<=opts.max_requests<=288:
        raise ValueError("HOLD_MAX_HTTP_REQUESTS")
    html=fetch_official_index(day)
    venues=official_venues(html,day)
    if not venues:
        raise RuntimeError("HOLD_OFFICIAL_EVENT_LIST_EMPTY")
    selected=target_ids(day,venues,opts.max_venues,opts.max_race_no)
    if len(selected)>opts.max_requests:
        raise RuntimeError("HOLD_PLAN_HTTP_BUDGET_EXCEEDED")
    print(f"V5_NATIVE_CORE_DAY_MODE={'APPLY' if opts.apply else 'PREVIEW'} "
          f"day={day} venues={len(venues)} planned={len(selected)}",flush=True)
    valid=0
    inserted=0
    held=0
    for rid in selected:
        try:
            html,observed=official_fetch(rid)
            race,entries=official_payload(rid,html,observed)
            if race["race_id"]!=rid or len(entries)!=6:
                raise RuntimeError("HOLD_RACE_IDENTITY")
            if opts.apply:
                nr,ne=apply_one(race,entries,observed)
                if ne not in (0,6) or nr not in (0,1):
                    raise RuntimeError("HOLD_PARTIAL_STAGE_CORE_COMMIT")
                inserted+=ne
            valid+=1
            print(f"V5_CORE_DAY_OK race={rid} entrants=6"
                  f" stage_added_entries={ne if opts.apply else 'PREVIEW'}",flush=True)
        except Exception as exc:
            held+=1
            print(f"V5_CORE_DAY_HOLD race={rid} reason={type(exc).__name__}:"
                  f"{str(exc).splitlines()[0][:90]}",flush=True)
        if selected[-1]!=rid:
            time.sleep(.35)  # bounded official-site request spacing
    print(f"V5_CORE_DAY_SUMMARY valid={valid} held={held} "
          f"new_stage_entries={inserted} total={len(selected)}",flush=True)
    if held or valid!=len(selected):
        raise RuntimeError("HOLD_INCOMPLETE_CORE_DAY_NO_FULL_COVERAGE")
    if not opts.apply:
        print("V5_CORE_DAY_PREVIEW_NO_DB_NO_WRITES_NO_BUY",flush=True)
    else:
        print("V5_CORE_DAY_CANARY_EXECUTED_VERIFY_STORAGE_AND_READERS_NO_BUY",flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_CORE_DAY_STOP "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
