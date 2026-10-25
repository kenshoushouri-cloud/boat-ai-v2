# -*- coding: utf-8 -*-
"""Historical BOAT RACE racelist reconstruction into a dedicated provenance table.

No canonical v2_race_entries overwrite.
No result/odds read.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from db_pg import execute, fetch_all, upsert_rows
import repair_month_all_pg as repair

JST=timezone(timedelta(hours=9))
START=os.getenv("HIST_RACELIST_START_DATE","2025-07-01")
END=os.getenv("HIST_RACELIST_END_DATE",START)
MAX_RACES=max(0,int(os.getenv("HIST_RACELIST_MAX_RACES","24")))
PARSER_VERSION="repair_month_all_entry_stat_window_v12"
EVIDENCE_CLASS="historical_reconstructed_predeadline_assumption"
SOURCE="boatrace_official_racelist_history"

DDL=[
"""create table if not exists v2_historical_racelist_reconstruction (
    race_id text not null,
    lane integer not null,
    race_date date,
    venue_id text,
    race_no integer,
    racer_number integer,
    racer_class integer,
    racer_class_text text,
    branch text,
    origin text,
    f_count integer,
    l_count integer,
    avg_st numeric,
    national_win_rate numeric,
    national_place2_rate numeric,
    national_place3_rate numeric,
    local_win_rate numeric,
    local_place2_rate numeric,
    local_place3_rate numeric,
    motor_no integer,
    motor_place2_rate numeric,
    motor_place3_rate numeric,
    boat_no integer,
    boat_place2_rate numeric,
    boat_place3_rate numeric,
    source text not null,
    source_url text not null,
    source_text_sha256 text not null,
    fetched_at timestamptz not null,
    evidence_class text not null,
    parser_version text not null,
    identity_match boolean not null,
    primary key (race_id,lane)
);""",
"create index if not exists ix_v2_hist_racelist_date on v2_historical_racelist_reconstruction(race_date);",
"create index if not exists ix_v2_hist_racelist_racer on v2_historical_racelist_reconstruction(racer_number);",
]


def now_iso()->str:
    return datetime.now(JST).isoformat()


def ensure_schema()->None:
    for sql in DDL:
        execute(sql)


def text_sha256(text:str)->str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main()->None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")
    ensure_schema()
    races=fetch_all(
        """select race_id,race_date,coalesce(venue_id,venue_code) venue_id,race_no
             from v2_races
            where race_date between %s and %s
            order by race_date,coalesce(venue_id,venue_code),race_no""",
        (START,END),
    )
    if MAX_RACES:
        races=races[:MAX_RACES]
    ids=[str(r["race_id"]) for r in races]
    existing={}
    if ids:
        for e in fetch_all(
            """select race_id,lane,racer_number
                 from v2_race_entries
                where race_id=any(%s)
                order by race_id,lane""",
            (ids,),
        ):
            existing[(str(e["race_id"]),int(e["lane"]))]=(
                int(e["racer_number"]) if e.get("racer_number") is not None else None
            )

    counts={"races":len(races),"ok":0,"no_page":0,"parse_incomplete":0,"identity_rejected":0,"saved_rows":0}
    rejected=[]
    print("HIST_RACELIST_CANONICAL_OVERWRITE=0 RESULT_READ=0 ODDS_READ=0 LINE=0 BUY=0",flush=True)
    print(f"HIST_RACELIST_PERIOD={START}..{END} max_races={MAX_RACES}",flush=True)

    for i,race in enumerate(races,1):
        date_str=str(race["race_date"])
        venue=str(race["venue_id"]).zfill(2)
        rno=int(race["race_no"])
        rid=str(race["race_id"])
        url=repair._official_url("racelist",date_str,venue,rno)
        html=repair._fetch(url)
        if not html or repair._looks_no_race(html):
            counts["no_page"]+=1
            continue
        parsed=repair.parse_entries(html,rid)
        if len(parsed)!=6:
            counts["parse_incomplete"]+=1
            continue
        identity_ok=True
        for p in parsed:
            key=(rid,int(p["lane"]))
            old=existing.get(key)
            new=p.get("racer_number")
            if old is not None and new is not None and int(old)!=int(new):
                identity_ok=False
                rejected.append({"race_id":rid,"lane":int(p["lane"]),"existing":old,"parsed":new})
        if not identity_ok:
            counts["identity_rejected"]+=1
            continue

        h=text_sha256(html)
        fetched=now_iso()
        rows=[]
        for p in parsed:
            rows.append({
                "race_id":rid,
                "lane":int(p["lane"]),
                "race_date":date_str,
                "venue_id":venue,
                "race_no":rno,
                "racer_number":p.get("racer_number"),
                "racer_class":p.get("racer_class"),
                "racer_class_text":p.get("racer_class_text"),
                "branch":p.get("branch"),
                "origin":p.get("origin"),
                "f_count":p.get("f_count"),
                "l_count":p.get("l_count"),
                "avg_st":p.get("avg_st"),
                "national_win_rate":p.get("national_win_rate"),
                "national_place2_rate":p.get("national_place2_rate"),
                "national_place3_rate":p.get("national_place3_rate"),
                "local_win_rate":p.get("local_win_rate"),
                "local_place2_rate":p.get("local_place2_rate"),
                "local_place3_rate":p.get("local_place3_rate"),
                "motor_no":p.get("motor_no"),
                "motor_place2_rate":p.get("motor_place2_rate"),
                "motor_place3_rate":p.get("motor_place3_rate"),
                "boat_no":p.get("boat_no"),
                "boat_place2_rate":p.get("boat_place2_rate"),
                "boat_place3_rate":p.get("boat_place3_rate"),
                "source":SOURCE,
                "source_url":url,
                "source_text_sha256":h,
                "fetched_at":fetched,
                "evidence_class":EVIDENCE_CLASS,
                "parser_version":PARSER_VERSION,
                "identity_match":True,
            })
        counts["saved_rows"]+=upsert_rows(
            "v2_historical_racelist_reconstruction",rows,["race_id","lane"]
        )
        counts["ok"]+=1
        if i<=10 or i%20==0 or i==len(races):
            print(f"HIST_RACELIST_PROGRESS={i}/{len(races)} ok={counts['ok']} saved={counts['saved_rows']}",flush=True)

    print("HIST_RACELIST_COUNTS="+str(counts),flush=True)
    if rejected:
        print("HIST_RACELIST_IDENTITY_REJECT_SAMPLE="+str(rejected[:10]),flush=True)
    print("HIST_RACELIST_RESULT=PASS",flush=True)


if __name__=="__main__":
    main()
