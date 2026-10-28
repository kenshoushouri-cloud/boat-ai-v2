"""V5 native official deadline sync for boat_data_stage.races.

For every venue that still has an unstarted race today, fetches the OFFICIAL
racelist page ONCE (its deadline table lists 1R..12R) and compares all of that
venue's stored deadlines with the official ones. A shifted deadline would
otherwise leave the realtime queue window and the 180s pre-deadline guard
based on a stale value.

--compare-stage is the ONLY preview: official HTTP GET + READ ONLY SELECT,
prints the diff for all venues, never writes.
--apply (after ready_to_apply gates) runs only when JST minute%15<5 and never
03:00-06:00. Per venue the official table must have 12 races, valid HH:MM and
strictly increasing times, whose page links carry only that venue's jcd; otherwise the venue
is not updated and the reason is logged. Each update is limited to +-60 min,
never to a past time, and is written together with a row in
boat_data_stage.race_deadline_changes in ONE transaction.
Never public.v2_*, never BUY.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
import os
import re
import time

from v5.native_official_realtime_stage_pg import ready_to_apply
from v5.native_stage_race_entries_pg import (
    JST, LOCK, official_fetch, race_parts)

MAX_SHIFT=timedelta(minutes=60)
TIME_RE=re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")
BLOCK_HOURS=(3,4,5)   # JST hours where this code itself never writes
SLOT_MINUTES=5        # apply only when minute%15 < SLOT_MINUTES

def _connect():
    import psycopg
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_CONOHA_DB_ONLY")
    return psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=5,
                           autocommit=True)

def apply_blocked(now):
    """Reason string when --apply must not run at this JST time, else None."""
    now=now.astimezone(JST)
    if now.hour in BLOCK_HOURS:
        return "HOLD_STAGE_DELTA_WRITE_WINDOW_0300_0600"
    if now.minute%15>=SLOT_MINUTES:
        return "SKIP_NOT_APPLY_SLOT_MINUTE_MOD15_LT5"
    return None

def stored_races():
    """Read-only: today's unstarted races, all venues."""
    with _connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("""
                    SELECT race_id, deadline_at, deadline_time
                    FROM boat_data_stage.races
                    WHERE race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
                      AND deadline_at > now()
                    ORDER BY race_id
                """)
                return cur.fetchall()

def check_table(texts):
    """Validate one venue's official table {race_no: 'HH:MM'}."""
    if sorted(texts)!=list(range(1,13)):
        raise RuntimeError("HOLD_NOT_12_RACES_IN_TABLE")
    if any(not TIME_RE.fullmatch(str(t)) for t in texts.values()):
        raise RuntimeError("HOLD_BAD_TIME_TEXT")
    seq=[texts[i] for i in range(1,13)]  # zero padded: text order == time order
    if any(a>=b for a,b in zip(seq,seq[1:])):
        raise RuntimeError("HOLD_NOT_MONOTONIC_INCREASING")

def official_venue_table(day,venue):
    """One official racelist request -> ({race_no: 'HH:MM'}, captured)."""
    import repair_month_all_pg as parser  # parser only, no storage functions
    html,captured=official_fetch(f"{day.replace('-','')}_{venue}_01")
    if parser._looks_no_race(html):
        raise RuntimeError("HOLD_NO_OFFICIAL_RACELIST")
    # The venue name is only an <img alt>; the page's own links carry jcd=.
    if set(re.findall(r"jcd=(\d{2})",html))!={venue}:
        raise RuntimeError("HOLD_PAGE_VENUE_CODE_MISMATCH")
    texts=parser.parse_deadline_table(html)
    check_table(texts)
    return texts,captured

def compare(rows,*,fetch=None,sleep=None,now=None):
    """-> (diffs, venue_holds). One fetch per venue; errors never raised."""
    fetch=fetch or official_venue_table
    sleep=sleep or time.sleep
    now=now or datetime.now(JST)
    venues={}
    for rid,stored,stext in rows:
        day,venue,no=race_parts(rid)
        venues.setdefault((day,venue),[]).append((rid,no,stored,stext))
    diffs=[]; holds={}
    for i,((day,venue),races) in enumerate(sorted(venues.items())):
        try:
            texts,captured=fetch(day,venue)
        except Exception as exc:
            holds[venue]=(f"{type(exc).__name__}:"
                          f"{str(exc).splitlines()[0][:150]}")
        else:
            for rid,no,stored,stext in races:
                new_text=texts[no]
                official=datetime.fromisoformat(f"{day}T{new_text}:00+09:00")
                shift=official-stored
                status,reason="SAME" if not shift else "SHIFT",None
                if shift and abs(shift)>MAX_SHIFT:
                    status,reason="REJECT","HOLD_SHIFT_OVER_60MIN"
                elif shift and official<=now:
                    status,reason="REJECT","HOLD_NEW_DEADLINE_IN_PAST"
                diffs.append({"race_id":rid,"venue":venue,"stored":stored,
                    "old_text":stext,"official":official,"new_text":new_text,
                    "shift":shift,"captured":captured,"status":status,
                    "reason":reason})
        if i+1<len(venues):
            sleep(.5)
    return diffs,holds

def apply_changes(diffs):
    """One transaction per venue: UPDATE + history INSERT together."""
    by_venue={}
    for d in diffs:
        if d["status"]=="SHIFT":
            by_venue.setdefault(d["venue"],[]).append(d)
    n=0
    if not by_venue:
        return n
    with _connect() as conn:
        for venue,items in sorted(by_venue.items()):
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout='5000ms'")
                    cur.execute("SET LOCAL lock_timeout='500ms'")
                    cur.execute("SELECT pg_try_advisory_xact_lock(%s)",(LOCK,))
                    if not cur.fetchone()[0]:
                        raise RuntimeError("HOLD_STAGE_ADVISORY_LOCK_BUSY")
                    for d in items:
                        cur.execute("""UPDATE boat_data_stage.races
                            SET deadline_at=%s, deadline_time=%s,
                                updated_at=now()
                            WHERE race_id=%s AND deadline_at=%s
                              AND %s > now()""",
                            (d["official"],d["new_text"],d["race_id"],
                             d["stored"],d["official"]))
                        if cur.rowcount!=1:
                            continue  # changed meanwhile: no history either
                        old_text=d["old_text"] or \
                            d["stored"].astimezone(JST).strftime("%H:%M")
                        cur.execute("""INSERT INTO
                            boat_data_stage.race_deadline_changes
                            (race_id,race_date,old_deadline,new_deadline,
                             old_time_text,new_time_text,delta_minutes,
                             captured_at)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (d["race_id"],race_parts(d["race_id"])[0],
                             d["stored"],d["official"],old_text,d["new_text"],
                             int(round(d["shift"].total_seconds()/60)),
                             d["captured"]))
                        n+=1
    return n

def report(diffs,holds):
    for venue,reason in sorted(holds.items()):
        print(f"V5_NATIVE_DEADLINE_VENUE_HOLD jcd={venue} {reason}",flush=True)
    for d in diffs:
        if d["status"]=="SAME":
            continue
        print(f"V5_NATIVE_DEADLINE_{d['status']} id={d['race_id']} "
              f"stored={d['stored'].astimezone(JST):%H:%M} "
              f"official={d['new_text']} "
              f"shift_min={int(d['shift'].total_seconds()//60)}"
              +(f" {d['reason']}" if d["reason"] else ""),flush=True)

def sync(*,apply,now=None):
    now=now or datetime.now(JST)
    if apply:
        why=apply_blocked(now)
        if why:  # before any DB or official HTTP
            print(f"V5_NATIVE_DEADLINE_SYNC_SKIP {why}",flush=True)
            return None
    diffs,holds=compare(stored_races(),now=now)
    report(diffs,holds)
    n=apply_changes(diffs) if apply else 0
    count=lambda s:sum(1 for d in diffs if d["status"]==s)
    print(f"V5_NATIVE_DEADLINE_SYNC mode={'APPLY' if apply else 'COMPARE'} "
          f"venues_ok={len({d['venue'] for d in diffs})} "
          f"venues_hold={len(holds)} same={count('SAME')} "
          f"shift={count('SHIFT')} reject={count('REJECT')} updated={n}",
          flush=True)
    return diffs,holds

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compare-stage",action="store_true")
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args(argv)
    if args.apply:
        ready_to_apply()  # fail before SELECT or official HTTP
    elif not args.compare_stage:
        print("V5_NATIVE_DEADLINE_SYNC_NOOP use --compare-stage (read only) "
              "or --apply",flush=True)
        return 0
    res=sync(apply=args.apply)
    return 3 if res and res[1] else 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_NATIVE_DEADLINE_SYNC_HOLD "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
