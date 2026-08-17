# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import repair_month_all_pg as rp

VERSION="2026-08-18 historical-odds-reparse-v1"
TARGET_RACE_ID=os.getenv("TARGET_RACE_ID","20250702_13_04")

def main():
    print(f"✅ probe_historical_odds_reparse_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print("DB書き込みなし。", flush=True)

    parsed=rp._parse_race_id(TARGET_RACE_ID)
    if not parsed:
        raise RuntimeError("TARGET_RACE_ID が不正です")

    date_str,venue_id,race_no=parsed
    url=rp._official_url("odds3t",date_str,venue_id,race_no)
    print(f"URL={url}", flush=True)

    html=rp._fetch(url)
    if not html:
        print("FETCH=NONE", flush=True)
        return

    print(f"html_chars={len(html)}", flush=True)
    print(f"looks_no_race={rp._looks_no_race(html)}", flush=True)

    rows=rp.parse_odds3t(html,TARGET_RACE_ID)
    tickets=[str(x.get("ticket") or "") for x in rows]

    print("=== PARSE SUMMARY ===", flush=True)
    print(f"parsed_rows={len(rows)}", flush=True)
    print(f"distinct_tickets={len(set(tickets))}", flush=True)

    invalid=0
    for t in tickets:
        parts=t.split("-")
        ok=(len(parts)==3 and all(p in "123456" and len(p)==1 for p in parts) and len(set(parts))==3)
        if not ok:
            invalid+=1
    print(f"invalid_tickets={invalid}", flush=True)

    print("=== PARSED ROWS ===", flush=True)
    for x in rows[:130]:
        print(f"{x.get('ticket')} odds={x.get('odds')} is_final={x.get('is_final')}", flush=True)

    if len(rows)==120:
        print("RESULT=FULL_120", flush=True)
    elif len(rows)==0:
        print("RESULT=ZERO", flush=True)
    else:
        print("RESULT=PARTIAL", flush=True)

if __name__=="__main__":
    main()