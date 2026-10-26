"""Independent physical-stage, cutoff-aware V5 realtime queue runner.

Reads ONLY boat_data_stage.races/entries/odds_snapshots; never public.v2_*.
Delegates each race to native official HTTP+validation+atomic 6-family writer.
Default plan is READ ONLY (no official HTTP, no writes); --apply requires
explicit gates in v5.native_official_realtime_stage_pg. A cap is a capacity
alarm (nonzero status), never claimed as all-race completeness.
Requires same-day native core races in the physical stage; otherwise HOLD.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import os
import time

from v5.native_official_realtime_stage_pg import ready_to_apply, main as collect_one
from v5.native_stage_race_entries_pg import JST

def candidates(*,max_races=16):
    import psycopg
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_CONOHA_DB_ONLY")
    if not 1 <= max_races <= 48:
        raise ValueError("HOLD_MAX_RACES_1_TO_48")
    with psycopg.connect(os.environ["DATABASE_URL"],connect_timeout=5,
                         autocommit=True) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='5000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                # A zero-row queue is not a healthy collector when no
                # V5-native core/day data exists. Avoid silent false success.
                cur.execute("""SELECT count(*) FROM boat_data_stage.races
                               WHERE race_date =
                                 (now() AT TIME ZONE 'Asia/Tokyo')::date""")
                today_core_count=cur.fetchone()[0]
                if today_core_count==0:
                    raise RuntimeError("HOLD_NATIVE_TODAY_CORE_RACES_MISSING")
                cur.execute("""
                    SELECT r.race_id
                    FROM boat_data_stage.races r
                    WHERE r.race_date=(now() AT TIME ZONE 'Asia/Tokyo')::date
                      AND r.deadline_at::timestamptz
                            BETWEEN now()+interval '5 minutes'
                                AND now()+interval '32 minutes'
                      AND (SELECT count(*) FROM boat_data_stage.entries e
                           WHERE e.race_id=r.race_id)=6
                      AND NOT EXISTS (
                         SELECT 1 FROM boat_data_stage.odds_snapshots o
                         WHERE o.race_id=r.race_id
                           AND o.source='official_odds3t_v5_native'
                           AND o.snapshot_at >= now()-interval '4 minutes')
                    ORDER BY r.deadline_at::timestamptz,r.race_id
                    LIMIT %s
                """,(max_races+1,))
                return [x[0] for x in cur.fetchall()]

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply",action="store_true")
    ap.add_argument("--max-races",type=int,default=16)
    args=ap.parse_args(argv)
    if args.apply:
        ready_to_apply()  # fail before SELECT or official HTTP
    ids=candidates(max_races=args.max_races)
    extra=len(ids)>args.max_races
    planned=ids[:args.max_races]
    print(f"V5_NATIVE_REALTIME_QUEUE mode={'APPLY' if args.apply else 'PLAN'} "
          f"candidate_count={len(ids)} selected={len(planned)} cap={args.max_races}",
          flush=True)
    if not args.apply:
        for rid in planned:
            print("V5_NATIVE_REALTIME_DUE "+rid,flush=True)
        print("V5_NATIVE_REALTIME_PLAN_READ_ONLY_NO_HTTP_NO_WRITES_NO_BUY",flush=True)
        return 2 if extra else 0
    if not planned:
        print("V5_NATIVE_REALTIME_NO_DUE_RACES_NO_WRITES",flush=True)
        return 0
    failed=0
    for i,rid in enumerate(planned):
        # The per-race collector validates deadline, 120 odds, 6 exhibition
        # and ALL six physical targets before performing atomic writes.
        rc=collect_one(["--race-id",rid,"--apply"])
        if rc!=0:
            failed+=1
            print(f"V5_NATIVE_REALTIME_RACE_HOLD id={rid} status={rc}",
                  flush=True)
        if i+1<len(planned):
            time.sleep(.5)
    if failed or extra:
        print(f"V5_NATIVE_REALTIME_PARTIAL_FAILED={failed} MORE_THAN_CAP={extra}",
              flush=True)
        return 3
    print(f"V5_NATIVE_REALTIME_BATCH_OK selected={len(planned)} "
          "VERIFY_READ_AND_CUTOFF_BEFORE_CUTOVER_BUY_OFF",flush=True)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("V5_NATIVE_REALTIME_RUN_HOLD "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:150],flush=True)
        raise SystemExit(2)
