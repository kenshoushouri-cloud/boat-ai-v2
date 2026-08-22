# -*- coding: utf-8 -*-
"""Read-only post-audit for the one-day opponent-pressure Shadow pilot."""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.getenv('DATABASE_URL','').strip()

def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPP_PRESSURE_POST_MODE=read_only',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.v2_opponent_pressure_shadow') as t")
            if cur.fetchone()['t'] is None:
                print('OPP_PRESSURE_POST_TABLE=missing',flush=True)
                raise SystemExit(2)
            cur.execute("""
              select count(*)::bigint total,
                     count(*) filter(where race_date=date '2026-08-22')::bigint target_rows,
                     count(*) filter(where race_date<>date '2026-08-22')::bigint non_target_rows,
                     count(*) filter(where jsonb_array_length(lane_scores)=6)::bigint six_lane_rows,
                     count(*) filter(where model_version='2026-08-22 opponent-pressure-shadow-v1')::bigint version_rows,
                     min(train_end) min_train_end,max(train_end) max_train_end,
                     pg_total_relation_size('v2_opponent_pressure_shadow')::bigint relation_bytes
              from v2_opponent_pressure_shadow
            """)
            r=cur.fetchone()
            cur.execute("""
              select count(*)::bigint bad_lane_objects
              from v2_opponent_pressure_shadow s,
                   lateral jsonb_array_elements(s.lane_scores) x
              where race_date=date '2026-08-22'
                and (
                  not (x ? 'lane' and x ? 'class' and x ? 'matched_opponents' and x ? 'score_win' and x ? 'score_top3' and x ? 'adj_win' and x ? 'adj_top3')
                  or (x->>'lane')::int not between 1 and 6
                  or (x->>'class')::int not between 1 and 4
                  or (x->>'matched_opponents')::int < 4
                )
            """)
            bad=cur.fetchone()['bad_lane_objects']
    print(f"OPP_PRESSURE_POST_ROWS=total:{r['total']} target:{r['target_rows']} non_target:{r['non_target_rows']} six_lane:{r['six_lane_rows']} version:{r['version_rows']}",flush=True)
    print(f"OPP_PRESSURE_POST_TRAIN_END=min:{r['min_train_end']} max:{r['max_train_end']}",flush=True)
    print(f"OPP_PRESSURE_POST_BAD_LANE_OBJECTS={bad}",flush=True)
    print(f"OPP_PRESSURE_POST_RELATION_BYTES={r['relation_bytes']}",flush=True)
    ok=(r['target_rows']==156 and r['non_target_rows']==0 and r['six_lane_rows']==156 and r['version_rows']==156 and bad==0 and str(r['min_train_end'])=='2026-08-21' and str(r['max_train_end'])=='2026-08-21')
    if not ok:
        print('OPP_PRESSURE_POST_RESULT=FAIL',flush=True); raise SystemExit(2)
    print('OPP_PRESSURE_POST_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f"OPP_PRESSURE_POST_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
