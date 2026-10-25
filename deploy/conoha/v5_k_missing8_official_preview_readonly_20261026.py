#!/usr/bin/env python3
"""Read-only official K-file parse/coverage preview for the eight evidenced gaps.

Scope ONLY 2026-10-15,16,17,21,22,23,24,25, one HTTP GET per day maximum.
Reads public.v2_races and v2_result_entries via a READ ONLY SQL transaction;
does NOT INSERT, UPDATE, DELETE, CREATE, schedule, or activate collection.
Fetches up to eight official K archives using the repository's existing
audited parser. Reports parse completeness and source race-ID set parity.
Avoids HTTP storm: sequential requests with >=3 second gaps and STOP on
HTTP rate limiting. The user must run it deliberately; no hidden jobs.
This is NOT permission to backfill; backup + DB write safety separately.
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from importlib import import_module

import psycopg

JST = timezone(timedelta(hours=9))
DATES = (
    "2026-10-15", "2026-10-16", "2026-10-17",
    "2026-10-21", "2026-10-22", "2026-10-23",
    "2026-10-24", "2026-10-25",
)
ALLOW_TOTAL_REQUESTS = len(DATES)


def say(*items):
    print(*items, flush=True)


def known_races() -> dict[str, set[str]]:
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD: expected local railway socket DSN")
    rows_by_date: dict[str, set[str]] = {}
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=8,
                         autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as c:
                c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                c.execute("SET LOCAL statement_timeout='20000ms'")
                c.execute("SET LOCAL lock_timeout='1000ms'")
                c.execute("SET LOCAL TIME ZONE 'Asia/Tokyo'")
                c.execute("SELECT current_database(), current_user")
                if c.fetchone() != ("railway", "postgres"):
                    raise RuntimeError("HOLD: wrong DB/role")
                for day in DATES:
                    c.execute(
                        "SELECT race_id FROM public.v2_races WHERE race_date=%s "
                        "ORDER BY race_id", (day,))
                    ids = {str(row[0]) for row in c.fetchall()}
                    if not ids or len(ids)>288:
                        raise RuntimeError("HOLD: implausible race count for " + day)
                    # The original and stage are both expected to have ZERO
                    # detailed results on these dates (per verified K-gap audit).
                    c.execute(
                        "SELECT (SELECT count(*) FROM public.v2_result_entries "
                        "WHERE race_id LIKE %s), "
                        "(SELECT count(*) FROM boat_data_stage.racer_results "
                        "WHERE race_id LIKE %s)",
                        (day.replace("-", "") + "_%", day.replace("-", "") + "_%"))
                    src_n, stage_n = c.fetchone()
                    if src_n or stage_n:
                        raise RuntimeError(
                            f"HOLD: existing details changed {day} "
                            f"source={src_n} stage={stage_n}; re-audit first")
                    rows_by_date[day] = ids
    return rows_by_date


def run():
    if os.environ.get("V5_K_READONLY_PREVIEW") != "YES":
        raise RuntimeError("HOLD: V5_K_READONLY_PREVIEW=YES required")
    if datetime.now(JST).date() < date(2026, 10, 26):
        raise RuntimeError("HOLD: only after 2026-10-25")
    source = known_races()  # close database before starting outbound HTTP.
    # This is the existing audit-only official K parser, not save_k_day_results.
    ka = import_module("audit_k_day_all_pg")
    ka.TIMEOUT = 15
    say("V5_K_MISSING8_PREVIEW_START", "official_get_limit=8",
        "db_writes=NO", "cutover=NO_GO", "BUY=OFF")
    success = 0
    failed = 0
    attempts = 0
    started = time.monotonic()
    for day in DATES:
        if attempts>=ALLOW_TOTAL_REQUESTS or time.monotonic()-started>250:
            say("HOLD_TOTAL_REQUESTS_OR_RUNTIME_LIMIT")
            break
        if attempts:
            time.sleep(3)
        attempts += 1
        try:
            ka.TARGET_DATE = day  # parser uses module-level date in parse_section.
            text = ka.get_k_text(day)
            sections = ka.split_venue_sections(text.splitlines())
            races = [r for section in sections for r in ka.parse_section(section)]
            names = [str(x["race_id"]) for x in races]
            parse_fail = sum(len(x["parse_failed_candidate_lines"]) for x in races)
            non6 = sum(len(x["entries"]) != 6 for x in races)
            duplicates = sum(n-1 for n in Counter(names).values() if n>1)
            known = source[day]
            missing_ids = len(known - set(names))
            extra_ids = len(set(names) - known)
            good = (len(sections)>0 and parse_fail==0 and non6==0
                    and duplicates==0 and missing_ids==0 and extra_ids==0
                    and len(races)==len(known))
            say("K_DATE", day,
                "known_races="+str(len(known)),
                "parsed_races="+str(len(races)),
                "complete6="+str(len(races)-non6),
                "parser_failed_lines="+str(parse_fail),
                "duplicate_ids="+str(duplicates),
                "missing_race_ids="+str(missing_ids),
                "extra_race_ids="+str(extra_ids),
                "status="+("PARSE_READY_NO_DB_WRITES" if good
                           else "HOLD_K_SOURCE_OR_PARSE_MISMATCH"))
            success += int(good)
            failed += int(not good)
        except Exception as exc:
            # Only report error class and HTTP status, no credentials or K contents.
            try:
                status = getattr(getattr(exc, "response", None), "status_code", None)
            except Exception:
                status = None
            say("K_DATE", day, "status=HOLD_FETCH_OR_PARSE",
                "error_type="+type(exc).__name__,
                "http_status="+str(status or "NA"))
            failed += 1
            if status in (403, 429, 503):
                say("HOLD_RATE_LIMIT_STOP_NO_RETRY")
                break
    say("V5_K_MISSING8_PREVIEW_SUMMARY",
        "ready="+str(success), "held="+str(failed),
        "requests="+str(attempts), "total_days="+str(len(DATES)),
        "DB_WRITE=NO", "K_BACKFILL=NOT_PERFORMED", "BUY=OFF", "CUTOVER=NO_GO")
    return 0 if success==len(DATES) else 2


if __name__=="__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        safe = exc.sqlstate if isinstance(exc, psycopg.Error) else (
            str(exc).splitlines()[0][:150]
        )
        say("V5_K_MISSING8_HOLD", safe, "NO_DB_WRITE", "NO_CUTOVER")
        sys.exit(2)
