# -*- coding: utf-8 -*-
"""Read-only OOS audit for a global opponent-pressure score.

Train-only effects are learned for own_class x own_lane x opponent_lane x
opponent_class, shrunk toward the own_class x own_lane baseline, averaged
across the five opponents, then evaluated on later races.
No DB writes, coefficients persistence, Production, Shadow, or LINE changes.
"""
from __future__ import annotations
from datetime import date
import os
import psycopg
from psycopg.rows import dict_row

DB=os.environ.get('DATABASE_URL','').strip()
START=date(2025,7,1); END=date(2026,8,22)
SPLITS=(date(2026,3,31),date(2026,4,30),date(2026,5,31))
SHRINK_K=100.0
TRAIN_COND_MIN=40
TRAIN_BASE_MIN=500

def one(conn,q,p=()):
    with conn.cursor() as c:
        c.execute(q,p); r=c.fetchone(); return dict(r) if r else {}

def audit(conn,split):
    q="""
    with base as (
      select r.race_date,a.race_id,a.lane own_lane,a.racer_class own_class,
             b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ),
    tbase as (
      select own_class,own_lane,count(*)/5.0 n,avg(win) pwin,avg(top3) ptop3
      from base where race_date<=%s group by 1,2
    ),
    teff as (
      select b.own_class,b.own_lane,b.opp_lane,b.opp_class,count(*) n,
             (avg(b.win)-tb.pwin) * (count(*)::float8/(count(*)+%s)) ewin,
             (avg(b.top3)-tb.ptop3) * (count(*)::float8/(count(*)+%s)) etop3
      from base b join tbase tb using(own_class,own_lane)
      where b.race_date<=%s and tb.n>=%s
      group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,tb.pwin,tb.ptop3
      having count(*)>=%s
    ),
    scored as (
      select b.race_id,b.own_lane,b.own_class,max(b.win) win,max(b.top3) top3,
             tb.pwin,tb.ptop3,
             avg(coalesce(t.ewin,0)) score_win,
             avg(coalesce(t.etop3,0)) score_top3,
             count(t.opp_lane) matched_opp
      from base b
      join tbase tb using(own_class,own_lane)
      left join teff t using(own_class,own_lane,opp_lane,opp_class)
      where b.race_date>%s and tb.n>=%s
      group by b.race_id,b.own_lane,b.own_class,tb.pwin,tb.ptop3
    ),
    pred as (
      select *,greatest(.001,least(.999,pwin+score_win)) pwin_adj,
               greatest(.001,least(.999,ptop3+score_top3)) ptop3_adj,
               ntile(4) over(order by score_win) qwin,
               ntile(4) over(order by score_top3) qtop3
      from scored where matched_opp>=4
    ),
    metrics as (
      select count(*) n,
        avg((win-pwin)^2) brier_win_base,avg((win-pwin_adj)^2) brier_win_adj,
        avg((top3-ptop3)^2) brier_top3_base,avg((top3-ptop3_adj)^2) brier_top3_adj,
        avg(win) filter(where qwin=1) q1_win,avg(win) filter(where qwin=4) q4_win,
        avg(top3) filter(where qtop3=1) q1_top3,avg(top3) filter(where qtop3=4) q4_top3,
        avg(score_win) score_win_mean,avg(abs(score_win)) score_win_abs,
        avg(score_top3) score_top3_mean,avg(abs(score_top3)) score_top3_abs
      from pred
    )
    select * from metrics
    """
    return one(conn,q,(START,END,split,SHRINK_K,SHRINK_K,split,TRAIN_BASE_MIN,TRAIN_COND_MIN,split,TRAIN_BASE_MIN))

def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPP_PRESSURE_MODE=read_only',flush=True)
    print(f'OPP_PRESSURE_PERIOD={START}..{END}',flush=True)
    print(f'OPP_PRESSURE_GATES=train_cond>={TRAIN_COND_MIN},train_base>={TRAIN_BASE_MIN},shrink_k={SHRINK_K}',flush=True)
    print('OPP_PRESSURE_POLICY=train_only_effects_oos_eval_no_writes',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
      with conn.cursor() as c:
        c.execute('set max_parallel_workers_per_gather=0'); c.execute("set work_mem='8MB'"); c.execute("set statement_timeout='180s'")
      for split in SPLITS:
        r=audit(conn,split)
        n=int(r.get('n') or 0)
        bw=float(r.get('brier_win_base') or 0); aw=float(r.get('brier_win_adj') or 0)
        bt=float(r.get('brier_top3_base') or 0); at=float(r.get('brier_top3_adj') or 0)
        q1w=float(r.get('q1_win') or 0); q4w=float(r.get('q4_win') or 0)
        q1t=float(r.get('q1_top3') or 0); q4t=float(r.get('q4_top3') or 0)
        print(f'OPP_PRESSURE_SPLIT={split} n:{n} win_brier_base:{bw:.6f} win_brier_adj:{aw:.6f} win_improve:{bw-aw:.6f} win_q1:{q1w:.4f} win_q4:{q4w:.4f} win_spread:{q4w-q1w:.4f} top3_brier_base:{bt:.6f} top3_brier_adj:{at:.6f} top3_improve:{bt-at:.6f} top3_q1:{q1t:.4f} top3_q4:{q4t:.4f} top3_spread:{q4t-q1t:.4f} mean_abs_win_score:{float(r.get("score_win_abs") or 0):.4f} mean_abs_top3_score:{float(r.get("score_top3_abs") or 0):.4f}',flush=True)
    print('OPP_PRESSURE_RESULT=PASS_READ_ONLY',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
      print(f"OPP_PRESSURE_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}",flush=True); raise
