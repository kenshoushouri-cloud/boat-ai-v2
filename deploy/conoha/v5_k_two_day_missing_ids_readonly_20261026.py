#!/usr/bin/env python3
"""Audit only 13 known/official K race-ID discrepancies on 2026-10-21/25.

One bounded official GET per day (max 2 total), no retries, 3-second gap.
Read-only SQL for source known races and status/ticket (never print raw).
Does NOT write any database, execute K backfill, or schedule anything.
The mismatch can be a cancelled/non-held race, NOT necessarily data loss.
"""
from __future__ import annotations
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from importlib import import_module
from collections import Counter

import psycopg

JST=timezone(timedelta(hours=9))
DAYS=("2026-10-21","2026-10-25")

def report(*pieces):
    print(*pieces,flush=True)

def collect_db():
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_WRONG_DB_ENDPOINT")
    dataset={}
    with psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=8,
                         autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as c:
                c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                c.execute("SET LOCAL TIME ZONE 'Asia/Tokyo'")
                c.execute("SET LOCAL statement_timeout='25000ms'")
                c.execute("SET LOCAL lock_timeout='1000ms'")
                c.execute("SELECT current_database(),current_user")
                if c.fetchone()!=("railway","postgres"):
                    raise RuntimeError("HOLD_DB_ROLE_MISMATCH")
                for day in DAYS:
                    c.execute(
                        "SELECT r.race_id,COALESCE(rs.result_status::text,'NULL'),"
                        "COALESCE(rs.trifecta_ticket::text,'NULL'), "
                        "rs.trifecta_payout_yen "
                        "FROM public.v2_races r LEFT JOIN public.v2_results rs "
                        "ON rs.race_id=r.race_id "
                        "WHERE r.race_date=%s ORDER BY r.race_id", (day,))
                    rows=c.fetchall()
                    if not (1<=len(rows)<=288):
                        raise RuntimeError("HOLD_SOURCE_DAY_COUNT_"+day)
                    dataset[day]={str(row[0]):row[1:] for row in rows}
    return dataset

def run():
    if os.environ.get("V5_K_TWO_DAY_READONLY")!="YES":
        raise RuntimeError("HOLD_EXPLICIT_READONLY_PREVIEW_REQUIRED")
    if datetime.now(JST).date().isoformat()<"2026-10-26":
        raise RuntimeError("HOLD_DATE_TOO_EARLY")
    sources=collect_db()
    # DB connection has been closed prior to official HTTP requests.
    ka=import_module("audit_k_day_all_pg")
    ka.TIMEOUT=15
    report("K_TWO_DAY_MISSING_IDS_START","HTTP_MAX=2",
           "SOURCE_DB_READ_ONLY=YES","K_BACKFILL=NO","BUY=OFF")
    total_missing=0
    for index, day in enumerate(DAYS):
        if index:
            time.sleep(3)
        try:
            ka.TARGET_DATE=day
            body=ka.get_k_text(day)
            sections=ka.split_venue_sections(body.splitlines())
            races=[race for sec in sections for race in ka.parse_section(sec)]
            ids=[str(x["race_id"]) for x in races]
            duplicates=sum(c-1 for c in Counter(ids).values() if c>1)
            bad_lines=sum(len(x["parse_failed_candidate_lines"]) for x in races)
            incomplete=sum(len(x["entries"])!=6 for x in races)
            expected=set(sources[day])
            seen=set(ids)
            missing=sorted(expected-seen)
            extra=sorted(seen-expected)
            if duplicates or bad_lines or incomplete or extra:
                report("K_DAY_HOLD",day,"duplicate="+str(duplicates),
                       "bad_lines="+str(bad_lines),
                       "incomplete="+str(incomplete),
                       "extra="+str(extra[:13]))
                return 2
            report("K_DAY",day,"db_races="+str(len(expected)),
                   "k_races="+str(len(ids)),
                   "db_only_count="+str(len(missing)),
                   "k_only_count="+str(len(extra)))
            for rid in missing:
                status,ticket,payout=sources[day][rid]
                # Ticket is a short result code or NULL, not sensitive data.
                report("K_DB_ONLY_RACE",rid,"db_result_status="+str(status),
                       "db_ticket="+str(ticket),"db_payout="+str(payout),
                       "K_DETAIL=ABSENT")
            total_missing+=len(missing)
        except Exception as exc:
            status=getattr(getattr(exc,"response",None),"status_code",None)
            report("K_DAY_FETCH_HOLD",day,"error="+type(exc).__name__,
                   "http_status="+str(status or "NA"),
                   "RETRY=NO","DB_WRITE=NO")
            return 2
    report("K_TWO_DAY_READONLY_FINISHED","db_only_races="+str(total_missing),
           "NO_DB_WRITES","NO_BACKFILL","NO_CUTOVER","BUY=OFF")
    return 0

if __name__=="__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        safe=(exc.sqlstate or "POSTGRES_ERROR") if isinstance(exc,psycopg.Error) else str(exc).splitlines()[0][:150]
        report("K_TWO_DAY_HOLD",safe,"NO_DB_WRITES","NO_CUTOVER")
        sys.exit(2)
