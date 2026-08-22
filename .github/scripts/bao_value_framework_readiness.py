# -*- coding: utf-8 -*-
"""Read-only readiness audit for a Bao-inspired value-betting framework.

The goal is NOT to copy horse-racing formulas. It checks whether boat-ai-v2 has
sufficient model probability / market odds / payout / time-series odds data to
test a separated "ability probability vs market price" edge framework out of
sample.

No DB writes, no prediction changes, no Shadow changes, no LINE changes.
"""
from __future__ import annotations

import os
import psycopg
from psycopg.rows import dict_row

DB = os.environ.get("DATABASE_URL", "").strip()
START = os.environ.get("BAO_AUDIT_START", "2025-07-01")
END = os.environ.get("BAO_AUDIT_END", "2026-08-22")

KEYWORDS = ("prob", "odds", "ev", "expect", "market", "payout", "ticket", "rank")


def rows(conn, q, p=()):
    with conn.cursor() as cur:
        cur.execute(q, p)
        return [dict(x) for x in cur.fetchall()]


def scalar(conn, q, p=()):
    xs = rows(conn, q, p)
    if not xs:
        return None
    return next(iter(xs[0].values()))


def has_table(conn, name):
    return bool(scalar(conn, "select to_regclass(%s) is not null", (f"public.{name}",)))


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("BAO_VALUE_MODE=read_only", flush=True)
    print(f"BAO_VALUE_PERIOD={START}..{END}", flush=True)
    print("BAO_VALUE_PRINCIPLE=model_probability_separate_from_market_price", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")

        schema = rows(conn, """
          select table_name,column_name,data_type
          from information_schema.columns
          where table_schema='public'
          order by table_name,ordinal_position
        """)
        hits=[]
        for r in schema:
            c=str(r['column_name']).lower()
            if any(k in c for k in KEYWORDS):
                hits.append(r)
        print(f"BAO_VALUE_SCHEMA_SIGNAL_COLUMNS={len(hits)}", flush=True)
        by_table={}
        for r in hits:
            by_table.setdefault(r['table_name'], []).append(r['column_name'])
        for t,cs in sorted(by_table.items()):
            if any(k in ' '.join(cs).lower() for k in ('prob','ev','odds','payout','market')):
                print(f"BAO_VALUE_TABLE={t} columns:{','.join(cs[:30])}", flush=True)

        # Core historical market/result coverage.
        if has_table(conn, 'v2_races') and has_table(conn, 'v2_odds_trifecta'):
            r=rows(conn,"""
              with d as (
                select race_id from v2_races where race_date between %s and %s
              ), o as (
                select distinct race_id from v2_odds_trifecta
              )
              select count(*)::bigint races,
                     count(*) filter(where o.race_id is not null)::bigint odds_races
              from d left join o using(race_id)
            """,(START,END))[0]
            print(f"BAO_VALUE_HIST_ODDS=races:{r['races']} covered:{r['odds_races']}", flush=True)

        if has_table(conn, 'v2_races') and has_table(conn, 'v2_results'):
            r=rows(conn,"""
              select count(*)::bigint races,
                     count(*) filter(where vr.trifecta_ticket is not null)::bigint ticket_rows,
                     count(*) filter(where coalesce(vr.trifecta_payout_yen,vr.trifecta_payout) is not null)::bigint payout_rows
              from v2_races r left join v2_results vr using(race_id)
              where r.race_date between %s and %s
            """,(START,END))[0]
            print(f"BAO_VALUE_RESULTS=races:{r['races']} ticket:{r['ticket_rows']} payout:{r['payout_rows']}", flush=True)

        if has_table(conn, 'v2_realtime_odds_snapshots'):
            cols={r['column_name'] for r in schema if r['table_name']=='v2_realtime_odds_snapshots'}
            rid_date = 'race_id' in cols
            snap = 'snapshot_at' in cols
            print(f"BAO_VALUE_REALTIME_ODDS=table:1 race_id:{int(rid_date)} snapshot_at:{int(snap)}", flush=True)
            if rid_date:
                r=rows(conn,"""
                  select count(*)::bigint rows,count(distinct race_id)::bigint races
                  from v2_realtime_odds_snapshots
                  where race_id >= %s and race_id < %s
                """,(START.replace('-',''), (END.replace('-','')+'z')))[0]
                print(f"BAO_VALUE_REALTIME_ODDS_COUNTS=rows:{r['rows']} races:{r['races']}", flush=True)
        else:
            print("BAO_VALUE_REALTIME_ODDS=table:0", flush=True)

        # Find persisted candidate/decision tables that already expose probability/EV/market dimensions.
        candidate_tables=[]
        for t,cs in by_table.items():
            s={str(c).lower() for c in cs}
            has_prob=any('prob' in c for c in s)
            has_odds=any('odds' in c for c in s)
            has_ev=any(c in {'ev','raw_ev','expected_value'} or 'expect' in c for c in s)
            has_market=any('market' in c for c in s)
            if has_prob and (has_odds or has_market or has_ev):
                candidate_tables.append((t,has_prob,has_odds,has_ev,has_market))
        print(f"BAO_VALUE_MODEL_MARKET_TABLES={len(candidate_tables)}", flush=True)
        for x in sorted(candidate_tables):
            print(f"BAO_VALUE_MODEL_MARKET={x[0]} prob:{int(x[1])} odds:{int(x[2])} ev:{int(x[3])} market:{int(x[4])}", flush=True)

        ready = bool(candidate_tables) and has_table(conn,'v2_odds_trifecta') and has_table(conn,'v2_results')
        print(f"BAO_VALUE_READINESS={'READY_FOR_OOS' if ready else 'NEEDS_BRIDGE'}", flush=True)
        print("BAO_VALUE_NEXT=calibration_then_edge_buckets_then_walk_forward_roi", flush=True)
        print("BAO_VALUE_RESULT=PASS_READ_ONLY", flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f"BAO_VALUE_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
