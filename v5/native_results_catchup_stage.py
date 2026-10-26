"""V5 standalone OFFICIAL postrace-results catchup -> physical stage ONLY.

Uses boat_data_stage.races/results, official raceresult page, existing parser
FUNCTION only; never imports old collector save/fetch functions and never
writes public.v2_*. Default --plan is read-only and makes NO HTTP requests.
One INSERT/UPDATE per verified result with fail-closed guarded stage/BUY.
No K-file racer-results promise (separate historically missing data family).
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import os
import re
import time
from urllib.parse import urlsplit, parse_qs

from v5.native_stage_race_entries_pg import JST, race_parts, blocked_by_stage_delta

RID=re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")
FINAL=frozenset(("official","cancelled","trifecta_invalid"))
FIELDS=("race_id","race_date","result_status","race_status",
        "trifecta_ticket","trifecta_payout_yen","source","fetched_at",
        "first_lane","second_lane","third_lane","fourth_lane",
        "fifth_lane","sixth_lane")
GATES=("V5_NATIVE_RESULTS_STAGE_APPROVED",
       "CONFIRM_V5_SHARED_PRIMARY_CANARY",
       "CONFIRM_LEGACY_WRITES_SEPARATELY")

def target_day(raw):
    today=datetime.now(JST).date()
    result=date.fromisoformat(raw) if raw else today-timedelta(days=1)
    if not date(2025,7,1)<=result<today:
        raise ValueError("HOLD_ONLY_COMPLETED_PREVIOUS_DAY")
    return result

def authorize():
    if os.environ.get("DATABASE_URL")!="postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_DB_ONLY")
    if os.environ.get("V5_SHARED_PRIMARY_MODE")!="CANARY":
        raise RuntimeError("HOLD_CANARY_REQUIRED")
    for gate in GATES:
        if os.environ.get(gate)!="YES":
            raise RuntimeError("HOLD_MISSING_GATE_"+gate)
    if any(os.environ.get(k,"").upper() in ("1","YES","ON","TRUE")
           for k in ("BUY_ENABLED","AUTO_BUY","ENABLE_PURCHASE")):
        raise RuntimeError("HOLD_BUY_ENABLED")
    blocked_by_stage_delta()

def pending(day):
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=5,
                         autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("""SELECT r.race_id
                   FROM boat_data_stage.races r
                   LEFT JOIN boat_data_stage.results x ON x.race_id=r.race_id
                   WHERE r.race_date=%s
                     AND (x.race_id IS NULL OR
                          x.result_status NOT IN ('official','cancelled','trifecta_invalid')
                          OR x.result_status IS NULL)
                   ORDER BY r.race_id""",(day,))
                return [row[0] for row in cur.fetchall()]

def verified_result(parsed):
    state=parsed.get("result_status")
    if state in ("cancelled","trifecta_invalid"):
        return True
    t=parsed.get("trifecta_ticket")
    if state!="official" or not isinstance(t,str):
        return False
    bits=t.split("-")
    return len(bits)==3 and all(x in "123456" and len(x)==1 for x in bits) \
        and len(set(bits))==3 \
        and type(parsed.get("trifecta_payout_yen")) is int \
        and parsed["trifecta_payout_yen"]>0

def fetch_parsed(rid):
    import requests
    from repair_month_all_pg import parse_result  # parser only, no legacy writes
    day,venue,rno=race_parts(rid)
    url=(f"https://www.boatrace.jp/owpc/pc/race/raceresult"
         f"?rno={rno}&jcd={venue}&hd={day.replace('-','')}")
    with requests.Session() as client:
        response=client.get(url,timeout=(8,18),headers={
            "User-Agent":"Mozilla/5.0 (compatible; V5-stage-results/1.0)"
        })
        response.raise_for_status()
        actual=urlsplit(response.url)
        expected={"rno":[str(rno)],"jcd":[venue],"hd":[day.replace("-","")]}
        if (actual.scheme!="https" or actual.netloc!="www.boatrace.jp"
                or actual.path!="/owpc/pc/race/raceresult"
                or actual.fragment or parse_qs(actual.query)!=expected
                or not response.content or len(response.content)>2_000_000):
            raise RuntimeError("HOLD_OFFICIAL_RESULT_URL_OR_SIZE")
        captured=datetime.now(JST)
        parsed=parse_result(response.text)
    if not verified_result(parsed):
        raise RuntimeError("HOLD_OFFICIAL_RESULT_UNRESOLVED")
    parsed.update({"race_id":rid,"race_date":day,
                   "source":"official_v5_native_result",
                   "fetched_at":captured.isoformat()})
    return parsed

def save_one(parsed):
    authorize()
    from psycopg import connect,sql
    rid=parsed["race_id"]
    if not RID.fullmatch(rid):
        raise ValueError("HOLD_INVALID_RACE_ID")
    with connect(os.environ["DATABASE_URL"],connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SELECT pg_try_advisory_xact_lock(%s)",(2026102503,))
                if not cur.fetchone()[0]:
                    raise RuntimeError("HOLD_STAGE_DELTA_BUSY")
                cur.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",
                            ("boat_data_stage.results",))
                found=cur.fetchone()
                if not found or found[0] not in ("r","p"):
                    raise RuntimeError("HOLD_RESULTS_NOT_PHYSICAL")
                cur.execute("SELECT count(*) FROM boat_data_stage.races WHERE race_id=%s",
                            (rid,))
                if cur.fetchone()[0]!=1:
                    raise RuntimeError("HOLD_STAGE_RACE_MISSING")
                query=sql.SQL("""INSERT INTO boat_data_stage.results AS t ({})
                   VALUES ({}) ON CONFLICT (race_id) DO UPDATE SET {}
                   WHERE COALESCE(t.result_status,'') NOT IN
                         ('official','cancelled','trifecta_invalid')""").format(
                      sql.SQL(",").join(map(sql.Identifier,FIELDS)),
                      sql.SQL(",").join(sql.Placeholder() for _ in FIELDS),
                      sql.SQL(",").join(
                          sql.SQL("{}=EXCLUDED.{}").format(
                              sql.Identifier(col),sql.Identifier(col))
                          for col in FIELDS if col!="race_id"))
                cur.execute(query,[parsed.get(field) for field in FIELDS])
                changed=cur.rowcount
                cur.execute("""SELECT result_status,trifecta_ticket,trifecta_payout_yen::integer
                               FROM boat_data_stage.results WHERE race_id=%s""",(rid,))
                saved=cur.fetchone()
                if not saved:
                    raise RuntimeError("HOLD_RESULT_NOT_SAVED")
                if not verified_result(dict(zip(
                     ("result_status","trifecta_ticket","trifecta_payout_yen"),
                     saved))):
                    raise RuntimeError("HOLD_RESULT_UNVERIFIED_AFTER_WRITE")
                return changed

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date",default=None)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--max-races",type=int,default=48)
    args=p.parse_args(argv)
    if not 1<=args.max_races<=288:
        raise ValueError("HOLD_MAX_RACES")
    if os.environ.get("DATABASE_URL")!="postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_DB_ONLY")
    if args.apply:
        authorize()
    day=target_day(args.date)
    ids=pending(day.isoformat())
    print(f"V5_RESULTS_NATIVE_STAGE day={day} pending={len(ids)} "
          f"mode={'APPLY' if args.apply else 'PLAN'}",flush=True)
    if not args.apply:
        print("V5_RESULTS_PLAN_READ_ONLY_NO_HTTP_NO_WRITES_NO_BUY",flush=True)
        return 0
    failed=0
    for i,rid in enumerate(ids[:args.max_races]):
        try:
            parsed=fetch_parsed(rid)
            n=save_one(parsed)
            print(f"V5_RESULTS_NATIVE_OK {rid} stage_changed={n}",flush=True)
        except Exception as exc:
            failed+=1
            print(f"V5_RESULTS_NATIVE_HOLD {rid} {type(exc).__name__}:"
                  f"{str(exc).splitlines()[0][:100]}",flush=True)
        if i+1<len(ids[:args.max_races]):
            time.sleep(.8)
    remaining=pending(day.isoformat())
    print(f"V5_RESULTS_NATIVE_REMAINING={len(remaining)}",flush=True)
    if failed or remaining or len(ids)>args.max_races:
        return 3
    print("V5_RESULTS_NATIVE_STAGE_CATCHUP_COMPLETE_BUY_OFF",flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_RESULTS_NATIVE_STOP "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
