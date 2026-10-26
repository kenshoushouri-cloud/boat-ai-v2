#!/usr/bin/env python3
"""Oct 26 ONLY: 12 source->stage families, guarded Oct26-scoped insert/update reconciliation.

Old sources and previously reconciled dates are never written. Existing date-scoped divergent source rows are reconciled. Entire APPLY
transaction rolls back if ANY extra stage-only 2026-10-26 key persists.
The 13th venues table is date-independent, deliberately excluded.
Snapshot captures are copied as-is; not authenticated predeadline evidence.
No legacy stop, stage timer cancellation, schema DDL, sequence changes or BUY.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

JST=ZoneInfo("Asia/Tokyo")
DAY="2026-10-26"
LOW,HIGH="20261026_","20261027_"
LOCK=2026102503
PAIRS=(
 ("v2_races","races","race_id"),
 ("v2_race_entries","entries","race_id"),
 ("v2_results","results","race_id"),
 ("v2_result_entries","racer_results","race_id"),
 ("v2_odds_trifecta","trifecta_odds","race_id"),
 ("v2_racer_course_stats_snapshots","racer_course_stats_snapshots","snapshot_date"),
 ("v2_realtime_entry_snapshots","entry_snapshots","race_id"),
 ("v2_realtime_exhibition_snapshots","exhibition_snapshots","race_id"),
 ("v2_realtime_odds_snapshots","odds_snapshots","race_id"),
 ("v2_realtime_weather_snapshots","weather_snapshots","race_id"),
 ("v2_realtime_race_condition_snapshots","race_condition_snapshots","race_id"),
 ("v2_realtime_racer_condition_snapshots","racer_condition_snapshots","race_id"),
)

def day_condition(alias,field,sql):
    col=sql.SQL("{}.{}").format(sql.Identifier(alias),sql.Identifier(field))
    return (sql.SQL("{} >= {} AND {} < {}").format(
       col,sql.Literal(LOW),col,sql.Literal(HIGH))
       if field=="race_id"
       else sql.SQL("{} = DATE {}").format(col,sql.Literal(DAY)))

def catalog(cur,sql,src,dst,field):
    for full in (src,dst):
        cur.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)",(full,))
        x=cur.fetchone()
        if not x or x[0] not in ("r","p"):
            raise RuntimeError("HOLD_NOT_PHYSICAL_"+full)
    def attributes(name):
        cur.execute("""SELECT attname,atttypid::text,atttypmod,
                            attnotnull,attcollation::text,attgenerated
                 FROM pg_attribute WHERE attrelid=to_regclass(%s)
                   AND attnum>0 AND NOT attisdropped ORDER BY attnum""",(name,))
        return cur.fetchall()
    a,b=attributes(src),attributes(dst)
    if not a or a!=b or any(row[5] for row in a):
        raise RuntimeError("HOLD_SCHEMA_OR_GENERATED_COLUMNS_"+dst)
    columns=tuple(r[0] for r in a)
    if field not in columns:
        raise RuntimeError("HOLD_DATE_FILTER_COLUMN_MISSING_"+dst)
    def keys(name):
        cur.execute("""SELECT a.attname FROM pg_index i
          JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(num,ord)
            ON x.ord<=i.indnkeyatts
          JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=x.num
          WHERE i.indrelid=to_regclass(%s) AND i.indisprimary
          ORDER BY x.ord""",(name,))
        return tuple(x[0] for x in cur.fetchall())
    pk=keys(src)
    if not pk or len(pk)>4 or pk!=keys(dst):
        raise RuntimeError("HOLD_DIFFERENT_PRIMARY_KEYS_"+dst)
    cur.execute("""SELECT count(*) FROM pg_trigger
                   WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal""",(dst,))
    if cur.fetchone()[0]:
        raise RuntimeError("HOLD_STAGE_USER_TRIGGER_"+dst)
    return columns,pk

def parity(cur,sql,src,dst,field,keys):
    s=sql.Identifier(*src.split("."))
    d=sql.Identifier(*dst.split("."))
    scope_s=day_condition("s",field,sql)
    scope_d=day_condition("d",field,sql)
    join=sql.SQL(" AND ").join(sql.SQL("s.{}=d.{}").format(
             sql.Identifier(k),sql.Identifier(k)) for k in keys)
    q=sql.SQL("""
       SELECT (SELECT count(*) FROM {} s WHERE {}) AS src_count,
              (SELECT count(*) FROM {} d WHERE {}) AS dst_count,
              (SELECT count(*) FROM {} s WHERE {} AND NOT EXISTS
                   (SELECT 1 FROM {} d WHERE {})) AS missing_count,
              (SELECT count(*) FROM {} d WHERE {} AND NOT EXISTS
                   (SELECT 1 FROM {} s WHERE {})) AS extra_count,
              (SELECT count(*) FROM {} s JOIN {} d ON {}
                   WHERE {} AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))
                   AS different_count
    """).format(s,scope_s,d,scope_d,
                s,scope_s,d,join,d,scope_d,s,join,
                s,d,join,scope_s)
    cur.execute(q)
    return cur.fetchone()

def copy_oct26_upsert(cur,sql,src,dst,field,columns,keys):
    """Insert new PKs and repair changed columns only within the Oct26 source slice.

    Never deletes anything and never touches an older-date source key. Existing
    stage-only keys are a HOLD before this function runs.
    """
    s=sql.Identifier(*src.split("."))
    d=sql.Identifier(*dst.split("."))
    cols=sql.SQL(",").join(sql.Identifier(c) for c in columns)
    values=sql.SQL(",").join(sql.SQL("s.{}").format(sql.Identifier(c))
                             for c in columns)
    cond=day_condition("s",field,sql)
    nonkey=[col for col in columns if col not in keys]
    if not nonkey:
        raise RuntimeError("HOLD_NO_UPDATABLE_COLUMNS_"+dst)
    updates=sql.SQL(",").join(
       sql.SQL("{}=EXCLUDED.{}").format(sql.Identifier(col),sql.Identifier(col))
       for col in nonkey)
    differs=sql.SQL(" OR ").join(
       sql.SQL("t.{} IS DISTINCT FROM EXCLUDED.{}").format(
           sql.Identifier(col),sql.Identifier(col)) for col in nonkey)
    conflict=sql.SQL(",").join(sql.Identifier(k) for k in keys)
    q=sql.SQL("""INSERT INTO {} AS t ({}) OVERRIDING SYSTEM VALUE
        SELECT {} FROM {} s WHERE {}
        ON CONFLICT ({}) DO UPDATE SET {}
        WHERE {}
    """).format(d,cols,values,s,cond,conflict,updates,differs)
    cur.execute(q)
    return cur.rowcount

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply",action="store_true")
    arg=p.parse_args()
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_ONLY_LOCAL_RAILWAY_DB")
    if arg.apply and os.environ.get("V5_OCT26_ONLY_SYNC_APPROVED")!="YES":
        raise RuntimeError("HOLD_EXPLICIT_OCT26_APPROVAL_REQUIRED")
    n=datetime.now(JST)
    if arg.apply and (n.date().isoformat()!="2026-10-27" or not (0<=n.hour<3)):
        raise RuntimeError("HOLD_EARLY_WINDOW_ONLY_BEFORE_0300_JST")
    # Prevent crossing stage11 scheduled synchronization window.
    if arg.apply and n.hour==2 and n.minute>=30:
        raise RuntimeError("HOLD_TOO_CLOSE_TO_0305_TIMER")
    if arg.apply and os.environ.get("V5_MIDNIGHT_CATCHUP_CONFIRMED")!="YES":
        raise RuntimeError("HOLD_0045_CATCHUP_NOT_CONFIRMED")
    import psycopg
    from psycopg import sql
    print("V5_OCT26_ONLY_MODE="+("APPLY" if arg.apply else "PREVIEW"),
          "date="+DAY,flush=True)
    with psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=5,
                         autocommit=True) as db:
        with db.transaction():
            with db.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ "+
                            ("" if arg.apply else "READ ONLY"))
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SET LOCAL statement_timeout='120000ms'")
                cur.execute("SET LOCAL work_mem='8MB'")
                if arg.apply:
                    cur.execute("SELECT pg_try_advisory_xact_lock(%s)",(LOCK,))
                    if not cur.fetchone()[0]:
                        raise RuntimeError("HOLD_STAGE_DELTA_LOCK_BUSY")
                report=[]
                for old,new,field in PAIRS:
                    src,dst="public."+old,"boat_data_stage."+new
                    columns,keys=catalog(cur,sql,src,dst,field)
                    before=parity(cur,sql,src,dst,field,keys)
                    sc,dc,missing,extra,different=before
                    print("OCT26_BEFORE|"+new+
                          f"|source={sc}|stage={dc}|missing={missing}"+
                          f"|extra={extra}|different={different}",flush=True)
                    if extra:
                        raise RuntimeError("HOLD_STAGE_ONLY_KEYS_"+new)
                    if arg.apply:
                        changed=copy_oct26_upsert(cur,sql,src,dst,field,columns,keys)
                        after=parity(cur,sql,src,dst,field,keys)
                        if (after[0]!=after[1] or
                            any(after[i] for i in (2,3,4)) or changed!=(missing+different)):
                            raise RuntimeError("HOLD_OCT26_PARITY_ROLLBACK_"+new)
                        report.append((new,changed,after[0]))
                        print(f"OCT26_VERIFIED|{new}|inserted_or_updated={changed}|rows={after[0]}",
                              flush=True)
                if not arg.apply:
                    print("V5_OCT26_ONLY_PREVIEW_COMPLETE_NO_WRITES_NO_BUY",
                          flush=True)
                    return
                # If ANY table failed, transaction rollback would prevent all writes.
                print("V5_OCT26_ONLY_ALL_12_FAMILIES_COMMIT_REQUEST "+
                      str(report),flush=True)
    print("V5_OCT26_ONLY_12_FAMILIES_COMMITTED_NO_LEGACY_WRITES_NO_DELETE_NO_BUY",
          flush=True)
    print("CAUTION_EMPTY_SOURCE_FAMILY_NOT_HISTORICALLY_COMPLETE",flush=True)
    print("CAUTION_NO_SEQUENCE_REPAIR_OR_ALL_HISTORY_PARITY",flush=True)

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("V5_OCT26_ONLY_HOLD "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:140],flush=True)
        sys.exit(2)
