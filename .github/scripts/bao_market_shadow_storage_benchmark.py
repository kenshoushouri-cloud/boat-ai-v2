# -*- coding: utf-8 -*-
"""Read-only storage benchmark for Bao early/late 120-ticket market snapshots.

Compares estimated PostgreSQL payload size of 120 row-per-ticket records against
one row per race/phase carrying a fixed-order real[] odds vector. Uses existing
historical odds only; creates no tables and writes nothing.
"""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()
SAMPLE_LIMIT=5000

def main():
    if not DB: raise RuntimeError('DATABASE_URL is required')
    print('BAO_STORE_MODE=read_only_no_temp_table',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute("set statement_timeout='120s'")
            # Restrict to complete 120-ticket races, sample recent IDs.  The row
            # estimate includes repeated identity/ticket/odds payload; the array
            # estimate stores identity once plus one real[] in canonical ticket
            # order. pg_column_size(record) measures the payload representation,
            # not heap/index overhead, so annual projections are comparative.
            c.execute('''
              with complete as (
                select race_id from v2_odds_trifecta where odds>1
                group by race_id having count(*)=120
                order by race_id desc limit %s
              ), rowwise as (
                select o.race_id,
                       sum(pg_column_size(row(o.race_id::text,'early'::text,o.ticket::text,o.odds::real)))::float8 row_bytes,
                       count(*) n
                from v2_odds_trifecta o join complete x using(race_id)
                where o.odds>1 group by o.race_id
              ), compact as (
                select o.race_id,
                       pg_column_size(row(o.race_id::text,'early'::text,array_agg(o.odds::real order by o.ticket)))::float8 compact_bytes,
                       cardinality(array_agg(o.odds::real order by o.ticket)) n
                from v2_odds_trifecta o join complete x using(race_id)
                where o.odds>1 group by o.race_id
              )
              select count(*)::bigint races,
                     avg(r.row_bytes)::float8 avg_rowwise_bytes,
                     avg(k.compact_bytes)::float8 avg_compact_bytes,
                     percentile_cont(.5) within group(order by r.row_bytes)::float8 median_rowwise,
                     percentile_cont(.5) within group(order by k.compact_bytes)::float8 median_compact,
                     min(k.n)::int min_array_n,max(k.n)::int max_array_n
              from rowwise r join compact k using(race_id)
            ''',(SAMPLE_LIMIT,))
            r=dict(c.fetchone() or {})
            rw=float(r.get('avg_rowwise_bytes') or 0); cp=float(r.get('avg_compact_bytes') or 0)
            reduction=(1-cp/rw)*100 if rw else 0
            print(f"BAO_STORE_SAMPLE=races:{r.get('races')} array_n:{r.get('min_array_n')}-{r.get('max_array_n')}",flush=True)
            print(f"BAO_STORE_PAYLOAD=rowwise_avg:{rw:.1f} compact_avg:{cp:.1f} rowwise_median:{float(r.get('median_rowwise') or 0):.1f} compact_median:{float(r.get('median_compact') or 0):.1f} reduction_pct:{reduction:.1f}",flush=True)
            # Projection: 144 races/day, two phases, 365 days. Pure payload only.
            snapshots=144*2*365
            print(f"BAO_STORE_ANNUAL_PAYLOAD=snapshots:{snapshots} rowwise_mb:{rw*snapshots/1024/1024:.1f} compact_mb:{cp*snapshots/1024/1024:.1f}",flush=True)
            # Also report current shadow relation if smoke already created it.
            c.execute("select to_regclass('public.v2_bao_market_shadow_snapshots')::text t")
            exists=bool((c.fetchone() or {}).get('t'))
            if exists:
                c.execute("select pg_total_relation_size('v2_bao_market_shadow_snapshots')::bigint bytes,count(*)::bigint rows,count(distinct race_id)::bigint races from v2_bao_market_shadow_snapshots")
                x=dict(c.fetchone() or {})
                print(f"BAO_STORE_CURRENT_TABLE=bytes:{x.get('bytes')} rows:{x.get('rows')} races:{x.get('races')}",flush=True)
            else:
                print('BAO_STORE_CURRENT_TABLE=not_created_yet',flush=True)
    print('BAO_STORE_POLICY=benchmark_only_no_db_writes',flush=True)
    print('BAO_STORE_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
