# -*- coding: utf-8 -*-
"""Read-only storage audit for Exhibition ST-only payloads."""
import os
import psycopg

START = "2025-07-01"

def main() -> None:
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db) as conn:
        conn.execute("set default_transaction_read_only=on")
        with conn.cursor() as cur:
            cur.execute("""
                select
                  pg_total_relation_size('v2_realtime_exhibition_snapshots')::bigint,
                  pg_table_size('v2_realtime_exhibition_snapshots')::bigint,
                  pg_indexes_size('v2_realtime_exhibition_snapshots')::bigint,
                  count(*)::bigint,
                  count(*) filter (
                    where race_date >= %s
                  )::bigint,
                  count(*) filter (
                    where race_date >= %s
                      and (start_timing is not null
                           or start_timing_rank is not null
                           or start_timing_diff is not null)
                  )::bigint,
                  coalesce(sum(pg_column_size(start_timing))
                    filter (where race_date >= %s and start_timing is not null),0)::bigint,
                  coalesce(sum(pg_column_size(start_timing_rank))
                    filter (where race_date >= %s and start_timing_rank is not null),0)::bigint,
                  coalesce(sum(pg_column_size(start_timing_diff))
                    filter (where race_date >= %s and start_timing_diff is not null),0)::bigint
                from v2_realtime_exhibition_snapshots
            """,(START,START,START,START,START))
            total,table,idx,rows,period_rows,st_rows,b1,b2,b3=cur.fetchone()

            cur.execute("select to_regclass('public.v2_exhibition_st_forward_shadow')")
            shadow_exists=cur.fetchone()[0] is not None
            if shadow_exists:
                cur.execute("""
                    select
                      pg_total_relation_size('v2_exhibition_st_forward_shadow')::bigint,
                      pg_table_size('v2_exhibition_st_forward_shadow')::bigint,
                      pg_indexes_size('v2_exhibition_st_forward_shadow')::bigint,
                      count(*)::bigint,
                      min(race_date)::text,
                      max(race_date)::text
                    from v2_exhibition_st_forward_shadow
                """)
                s_total,s_table,s_idx,s_rows,s_min,s_max=cur.fetchone()
            else:
                s_total=s_table=s_idx=s_rows=0
                s_min=s_max=""

    st_bytes=int(b1 or 0)+int(b2 or 0)+int(b3 or 0)
    print(f"EXH_RELATION_BYTES={total}")
    print(f"EXH_TABLE_BYTES={table}")
    print(f"EXH_INDEX_BYTES={idx}")
    print(f"EXH_ROWS={rows}")
    print(f"EXH_PERIOD_START={START}")
    print(f"EXH_PERIOD_ROWS={period_rows}")
    print(f"ST_NONEMPTY_PERIOD_ROWS={st_rows}")
    print(f"ST_START_TIMING_BYTES={b1}")
    print(f"ST_START_TIMING_RANK_BYTES={b2}")
    print(f"ST_START_TIMING_DIFF_BYTES={b3}")
    print(f"ST_3COL_BYTES={st_bytes}")
    print(f"ST_3COL_MB={st_bytes/1_000_000:.3f}")
    print(f"ST_FORWARD_SHADOW_EXISTS={1 if shadow_exists else 0}")
    print(f"ST_FORWARD_SHADOW_TOTAL_BYTES={s_total}")
    print(f"ST_FORWARD_SHADOW_TABLE_BYTES={s_table}")
    print(f"ST_FORWARD_SHADOW_INDEX_BYTES={s_idx}")
    print(f"ST_FORWARD_SHADOW_ROWS={s_rows}")
    print(f"ST_FORWARD_SHADOW_MIN_DATE={s_min or ''}")
    print(f"ST_FORWARD_SHADOW_MAX_DATE={s_max or ''}")
    print(f"ST_DIRECT_RECLAIM_CANDIDATE_BYTES={st_bytes + int(s_total or 0)}")
    print(f"ST_DIRECT_RECLAIM_CANDIDATE_MB={(st_bytes + int(s_total or 0))/1_000_000:.3f}")
    print("RAW_JSON_EXCLUDED_FROM_ST_ONLY_ESTIMATE=1")
    print("DB_READ_ONLY=1 DB_WRITE=0 RESULT_ODDS_PAYOUT_READ=0")

if __name__ == "__main__":
    main()
