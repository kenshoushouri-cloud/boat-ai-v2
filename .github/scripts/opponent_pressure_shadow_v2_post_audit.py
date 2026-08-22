# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import psycopg
from psycopg.rows import dict_row

TARGET_DATE='2026-08-22'


def main():
    url=os.getenv('DATABASE_URL','').strip()
    if not url: raise RuntimeError('DATABASE_URL required')
    print('OPP_PRESSURE_V2_POST_MODE=read_only',flush=True)
    with psycopg.connect(url,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='60s'")
            cur.execute("""
              select count(*)::bigint total,
                     count(*) filter(where race_date=date '2026-08-22')::bigint target_rows,
                     count(*) filter(where race_date<>date '2026-08-22')::bigint non_target_rows,
                     count(*) filter(where model_version=2 and train_end=date '2026-08-21')::bigint version_rows,
                     count(*) filter(where cardinality(racer_classes)=6 and cardinality(matched_opponents)=6
                       and cardinality(base_win)=6 and cardinality(base_top3)=6
                       and cardinality(score_win)=6 and cardinality(score_top3)=6
                       and cardinality(adj_win)=6 and cardinality(adj_top3)=6)::bigint arrays_ok,
                     count(*) filter(where 4 <= all(matched_opponents))::bigint matched_ok,
                     pg_relation_size('v2_opponent_pressure_shadow_v2')::bigint heap_bytes,
                     pg_indexes_size('v2_opponent_pressure_shadow_v2')::bigint index_bytes,
                     pg_total_relation_size('v2_opponent_pressure_shadow_v2')::bigint total_bytes
              from v2_opponent_pressure_shadow_v2
            """)
            s=cur.fetchone()
            cur.execute("""
              with x as (
                select v2.race_id,
                  greatest(
                    (select max(abs((v1.lane_scores->(i-1)->>'base_win')::float8-v2.base_win[i]::float8)) from generate_subscripts(v2.base_win,1) i),
                    (select max(abs((v1.lane_scores->(i-1)->>'base_top3')::float8-v2.base_top3[i]::float8)) from generate_subscripts(v2.base_top3,1) i),
                    (select max(abs((v1.lane_scores->(i-1)->>'score_win')::float8-v2.score_win[i]::float8)) from generate_subscripts(v2.score_win,1) i),
                    (select max(abs((v1.lane_scores->(i-1)->>'score_top3')::float8-v2.score_top3[i]::float8)) from generate_subscripts(v2.score_top3,1) i),
                    (select max(abs((v1.lane_scores->(i-1)->>'adj_win')::float8-v2.adj_win[i]::float8)) from generate_subscripts(v2.adj_win,1) i),
                    (select max(abs((v1.lane_scores->(i-1)->>'adj_top3')::float8-v2.adj_top3[i]::float8)) from generate_subscripts(v2.adj_top3,1) i)
                  ) max_abs,
                  not exists (
                    select 1 from generate_subscripts(v2.racer_classes,1) i
                    where (v1.lane_scores->(i-1)->>'class')::int <> v2.racer_classes[i]
                       or (v1.lane_scores->(i-1)->>'matched_opponents')::int <> v2.matched_opponents[i]
                  ) ints_ok
                from v2_opponent_pressure_shadow_v2 v2
                join v2_opponent_pressure_shadow v1 using(race_id)
                where v2.race_date=date '2026-08-22'
              )
              select count(*)::bigint compared,
                     count(*) filter(where ints_ok)::bigint ints_ok,
                     max(max_abs)::float8 max_abs,
                     count(*) filter(where max_abs>0.000002 or not ints_ok)::bigint mismatch_rows
              from x
            """)
            c=cur.fetchone()
            cur.execute("select pg_total_relation_size('v2_opponent_pressure_shadow')::bigint v1_bytes")
            v1=cur.fetchone()['v1_bytes']
    print(f"OPP_PRESSURE_V2_POST_ROWS=total:{s['total']} target:{s['target_rows']} non_target:{s['non_target_rows']} version:{s['version_rows']} arrays:{s['arrays_ok']} matched:{s['matched_ok']}",flush=True)
    print(f"OPP_PRESSURE_V2_POST_COMPARE=compared:{c['compared']} ints_ok:{c['ints_ok']} mismatch_rows:{c['mismatch_rows']} max_abs:{float(c['max_abs'] or 0):.8f}",flush=True)
    print(f"OPP_PRESSURE_V2_POST_SIZE=v1_total:{v1} v2_heap:{s['heap_bytes']} v2_indexes:{s['index_bytes']} v2_total:{s['total_bytes']} saving_pct:{(1-float(s['total_bytes'])/float(v1))*100:.1f}",flush=True)
    ok=(s['total']==156 and s['target_rows']==156 and s['non_target_rows']==0 and s['version_rows']==156 and s['arrays_ok']==156 and s['matched_ok']==156 and c['compared']==156 and c['ints_ok']==156 and c['mismatch_rows']==0 and float(c['max_abs'] or 0)<=0.000002)
    if not ok: raise RuntimeError('compact v2 post-audit failed')
    print('OPP_PRESSURE_V2_POST_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f"OPP_PRESSURE_V2_POST_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
