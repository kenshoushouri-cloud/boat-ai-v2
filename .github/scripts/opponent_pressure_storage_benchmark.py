# -*- coding: utf-8 -*-
"""Read-only storage benchmark for opponent-pressure Shadow payloads."""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()

def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPP_STORAGE_MODE=read_only',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
            with encoded as (
              select
                pg_column_size(lane_scores)::bigint json_bytes,
                pg_column_size(array(select (x->>'class')::smallint from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint class_bytes,
                pg_column_size(array(select (x->>'matched_opponents')::smallint from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint matched_bytes,
                pg_column_size(array(select (x->>'base_win')::real from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint base_win_bytes,
                pg_column_size(array(select (x->>'base_top3')::real from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint base_top3_bytes,
                pg_column_size(array(select (x->>'score_win')::real from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint score_win_bytes,
                pg_column_size(array(select (x->>'score_top3')::real from jsonb_array_elements(lane_scores) x order by (x->>'lane')::int))::bigint score_top3_bytes
              from v2_opponent_pressure_shadow
              where race_date=date '2026-08-22'
            )
            select count(*)::bigint n,
                   avg(json_bytes)::float8 avg_json_bytes,
                   avg(class_bytes+matched_bytes+base_win_bytes+base_top3_bytes+score_win_bytes+score_top3_bytes)::float8 avg_array_payload_bytes,
                   min(json_bytes)::bigint min_json_bytes,max(json_bytes)::bigint max_json_bytes,
                   pg_relation_size('v2_opponent_pressure_shadow')::bigint heap_bytes,
                   pg_indexes_size('v2_opponent_pressure_shadow')::bigint index_bytes,
                   pg_total_relation_size('v2_opponent_pressure_shadow')::bigint total_bytes
            from encoded
            """)
            r=cur.fetchone()
    n=int(r['n'] or 0); j=float(r['avg_json_bytes'] or 0); a=float(r['avg_array_payload_bytes'] or 0)
    saving=0.0 if not j else (1-a/j)*100
    annual_rows=144*365
    json_annual=annual_rows*j/1024/1024
    array_annual=annual_rows*a/1024/1024
    print(f"OPP_STORAGE_ROWS={n}",flush=True)
    print(f"OPP_STORAGE_JSON=avg:{j:.1f} min:{r['min_json_bytes']} max:{r['max_json_bytes']}",flush=True)
    print(f"OPP_STORAGE_ARRAY_PAYLOAD=avg:{a:.1f} saving_pct:{saving:.1f}",flush=True)
    print(f"OPP_STORAGE_RELATION=heap:{r['heap_bytes']} indexes:{r['index_bytes']} total:{r['total_bytes']}",flush=True)
    print(f"OPP_STORAGE_PAYLOAD_PROJECTION_144R_DAY=json_mb_year:{json_annual:.1f} arrays_mb_year:{array_annual:.1f}",flush=True)
    if n!=156: raise SystemExit('pilot row count changed')
    print('OPP_STORAGE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f"OPP_STORAGE_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
