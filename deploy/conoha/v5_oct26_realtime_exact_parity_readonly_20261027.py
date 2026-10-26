#!/usr/bin/env python3
"""Exact Oct26 realtime source/stage parity on 6 physical snapshot tables.

For EACH family, bounded READ ONLY snapshot compares identities and all
non-generated column values using to_jsonb(). No writes, VACUUM, deletion,
service changes, BUY, or giant historical scans. This is only one day:
not a legacy deletion authorization nor proof of original capture time.
"""
from __future__ import annotations
import os
import sys

PAIRS = (
  ("v2_realtime_entry_snapshots","entry_snapshots",("race_id","snapshot_label","lane")),
  ("v2_realtime_exhibition_snapshots","exhibition_snapshots",("race_id","snapshot_label","lane")),
  ("v2_realtime_odds_snapshots","odds_snapshots",("race_id","snapshot_label","ticket")),
  ("v2_realtime_weather_snapshots","weather_snapshots",("race_id","snapshot_label")),
  ("v2_realtime_race_condition_snapshots","race_condition_snapshots",("race_id","snapshot_label")),
  ("v2_realtime_racer_condition_snapshots","racer_condition_snapshots",("race_id","snapshot_label","lane")),
)
LOW, HIGH = "20261026_", "20261027_"

def check_one(db, src, dest, keys):
    from psycopg import sql
    source = sql.Identifier("public",src)
    target = sql.Identifier("boat_data_stage",dest)
    comparison = sql.SQL(" AND ").join(
        sql.SQL("d.{}=s.{}").format(sql.Identifier(k),sql.Identifier(k)) for k in keys
    )
    key_absence_s = sql.SQL("s.{} IS NULL").format(sql.Identifier(keys[0]))
    key_absence_d = sql.SQL("d.{} IS NULL").format(sql.Identifier(keys[0]))
    with db.transaction():
        with db.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            cur.execute("SET LOCAL statement_timeout='15000ms'")
            cur.execute("SET LOCAL lock_timeout='500ms'")
            cur.execute("SET LOCAL work_mem='4MB'")
            for fullname in (f"public.{src}",f"boat_data_stage.{dest}"):
                cur.execute("""SELECT relkind FROM pg_class
                               WHERE oid=to_regclass(%s)""",(fullname,))
                found = cur.fetchone()
                if not found or found[0] not in ("r","p"):
                    raise RuntimeError("HOLD_NOT_PHYSICAL_"+fullname)
            source_scope = sql.SQL("s.race_id >= {} AND s.race_id < {}").format(
                sql.Literal(LOW), sql.Literal(HIGH))
            stage_scope = sql.SQL("d.race_id >= {} AND d.race_id < {}").format(
                sql.Literal(LOW), sql.Literal(HIGH))
            # Query real indexed physical tables directly (no MATERIALIZED CTE).
            # Otherwise 35k odds snapshot keys can degrade to quadratic scans.
            query=sql.SQL("""
              SELECT (SELECT count(*) FROM {} s WHERE {}) AS source_count,
                     (SELECT count(*) FROM {} d WHERE {}) AS stage_count,
                     (SELECT count(*) FROM {} s WHERE {} AND NOT EXISTS(
                          SELECT 1 FROM {} d WHERE {})) AS missing_stage,
                     (SELECT count(*) FROM {} d WHERE {} AND NOT EXISTS(
                          SELECT 1 FROM {} s WHERE {})) AS extra_stage,
                     (SELECT count(*) FROM {} s JOIN {} d ON {}
                          WHERE {} AND to_jsonb(s) IS DISTINCT FROM to_jsonb(d))
                       AS changed_common
            """).format(
                source,source_scope,target,stage_scope,
                source,source_scope,target,comparison,
                target,stage_scope,source,comparison,
                source,target,comparison,source_scope)
            cur.execute(query)
            source_count,stage_count,missing,extra,changed=cur.fetchone()
            if source_count == 0:
                verdict="HOLD_EMPTY_SOURCE"
            elif missing == 0 and extra == 0 and changed == 0 and source_count == stage_count:
                verdict="OCT26_EXACT_ROWS_EQUAL_CURRENT_ONLY"
            else:
                verdict="HOLD_OCT26_REALTIME_MISMATCH"
            return {
                "source":source_count,"stage":stage_count,
                "missing_stage":missing,"extra_stage":extra,
                "different_common":changed,"verdict":verdict
            }

def main():
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_LOCAL_CONOHA_ONLY")
    import psycopg
    print("V5_OCT26_EXACT_REALTIME_PARITY_BEGIN_READ_ONLY",flush=True)
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5,
                         autocommit=True) as db:
        for src,dest,keys in PAIRS:
            row=check_one(db,src,dest,keys)
            print("PARITY|"+dest+"|"+"|".join(
                f"{k}={v}" for k,v in row.items()),flush=True)
    print("V5_OCT26_EXACT_REALTIME_PARITY_END_NO_WRITES_NO_DELETE_NO_BUY",flush=True)
    print("NOT_FULL_HISTORY_PARITY_NOT_LEGACY_DELETION_APPROVAL",flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("V5_OCT26_PARITY_HOLD "+type(exc).__name__+":"+
              str(exc).splitlines()[0][:130],flush=True)
        sys.exit(2)
