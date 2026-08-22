# -*- coding: utf-8 -*-
"""Read-only multi-split OOS audit for opponent lane/class effects.

Tests whether a racer's outcome deviation in a given own lane against an
opponent lane/class is directionally reproducible out of sample, relative to
the same racer's own-lane baseline. Also reports a much denser global
own-class/own-lane/opponent-lane/opponent-class baseline.

No writes. No Production/Shadow/LINE changes.
"""
from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row

DB=os.environ.get('DATABASE_URL','').strip()
START='2025-07-01'
END='2026-08-22'
SPLITS=('2026-03-31','2026-04-30','2026-05-31')


def one(conn,q,p=()):
    with conn.cursor() as c:
        c.execute(q,p)
        r=c.fetchone()
        return dict(r) if r else {}


def fmt(prefix,row):
    return prefix+' '.join(f'{k}:{v}' for k,v in row.items())


def racer_pair(conn,split):
    return one(conn,"""
    with obs as (
      select r.race_date,a.racer_number,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s
        and a.racer_number is not null and a.lane between 1 and 6
        and b.lane between 1 and 6 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ), tr_base as (
      select racer_number,own_lane,count(*)/5.0 n,avg(win) win,avg(top3) top3
      from obs where race_date<=%s group by 1,2
    ), te_base as (
      select racer_number,own_lane,count(*)/5.0 n,avg(win) win,avg(top3) top3
      from obs where race_date>%s group by 1,2
    ), tr_pair as (
      select racer_number,own_lane,opp_lane,opp_class,count(*) n,avg(win) win,avg(top3) top3
      from obs where race_date<=%s group by 1,2,3,4
    ), te_pair as (
      select racer_number,own_lane,opp_lane,opp_class,count(*) n,avg(win) win,avg(top3) top3
      from obs where race_date>%s group by 1,2,3,4
    ), m as (
      select p.racer_number,p.own_lane,p.opp_lane,p.opp_class,p.n tr_n,t.n te_n,
             p.win-b.win tr_win_eff,t.win-e.win te_win_eff,
             p.top3-b.top3 tr_top3_eff,t.top3-e.top3 te_top3_eff
      from tr_pair p join te_pair t using(racer_number,own_lane,opp_lane,opp_class)
      join tr_base b using(racer_number,own_lane)
      join te_base e using(racer_number,own_lane)
      where p.n>=20 and t.n>=5 and b.n>=20 and e.n>=5
    )
    select count(*)::bigint matched,
      count(*) filter(where abs(tr_win_eff)>=0.02)::bigint win_signal,
      count(*) filter(where abs(tr_win_eff)>=0.02 and tr_win_eff*te_win_eff>0)::bigint win_same,
      round(100.0*count(*) filter(where abs(tr_win_eff)>=0.02 and tr_win_eff*te_win_eff>0)/nullif(count(*) filter(where abs(tr_win_eff)>=0.02),0),1)::float8 win_same_pct,
      count(*) filter(where abs(tr_top3_eff)>=0.02)::bigint top3_signal,
      count(*) filter(where abs(tr_top3_eff)>=0.02 and tr_top3_eff*te_top3_eff>0)::bigint top3_same,
      round(100.0*count(*) filter(where abs(tr_top3_eff)>=0.02 and tr_top3_eff*te_top3_eff>0)/nullif(count(*) filter(where abs(tr_top3_eff)>=0.02),0),1)::float8 top3_same_pct,
      round(avg(abs(tr_win_eff))::numeric,4)::float8 mean_abs_train_win_eff,
      round(avg(abs(te_win_eff))::numeric,4)::float8 mean_abs_test_win_eff
    from m
    """,(START,END,split,split,split,split))


def global_pair(conn,split):
    return one(conn,"""
    with obs as (
      select r.race_date,a.racer_class own_class,a.lane own_lane,b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and a.lane between 1 and 6 and b.lane between 1 and 6
        and re.finish_position between 1 and 6
    ), tr_base as (
      select own_class,own_lane,avg(win) win,avg(top3) top3 from obs where race_date<=%s group by 1,2
    ), te_base as (
      select own_class,own_lane,avg(win) win,avg(top3) top3 from obs where race_date>%s group by 1,2
    ), tr_pair as (
      select own_class,own_lane,opp_lane,opp_class,count(*) n,avg(win) win,avg(top3) top3
      from obs where race_date<=%s group by 1,2,3,4
    ), te_pair as (
      select own_class,own_lane,opp_lane,opp_class,count(*) n,avg(win) win,avg(top3) top3
      from obs where race_date>%s group by 1,2,3,4
    ), m as (
      select p.*,t.n te_n,p.win-b.win tr_win_eff,t.win-e.win te_win_eff,
             p.top3-b.top3 tr_top3_eff,t.top3-e.top3 te_top3_eff
      from tr_pair p join te_pair t using(own_class,own_lane,opp_lane,opp_class)
      join tr_base b using(own_class,own_lane) join te_base e using(own_class,own_lane)
      where p.n>=100 and t.n>=30
    )
    select count(*)::bigint matched,
      count(*) filter(where abs(tr_win_eff)>=0.005)::bigint win_signal,
      count(*) filter(where abs(tr_win_eff)>=0.005 and tr_win_eff*te_win_eff>0)::bigint win_same,
      round(100.0*count(*) filter(where abs(tr_win_eff)>=0.005 and tr_win_eff*te_win_eff>0)/nullif(count(*) filter(where abs(tr_win_eff)>=0.005),0),1)::float8 win_same_pct,
      count(*) filter(where abs(tr_top3_eff)>=0.005)::bigint top3_signal,
      count(*) filter(where abs(tr_top3_eff)>=0.005 and tr_top3_eff*te_top3_eff>0)::bigint top3_same,
      round(100.0*count(*) filter(where abs(tr_top3_eff)>=0.005 and tr_top3_eff*te_top3_eff>0)/nullif(count(*) filter(where abs(tr_top3_eff)>=0.005),0),1)::float8 top3_same_pct
    from m
    """,(START,END,split,split,split,split))


def main():
    if not DB: raise RuntimeError('DATABASE_URL required')
    print('OPPONENT_OOS_MODE=read_only',flush=True)
    print(f'OPPONENT_OOS_PERIOD={START}..{END}',flush=True)
    print('OPPONENT_OOS_RULE=racer_pair_train20_test5_effect_gate_2pct',flush=True)
    with psycopg.connect(DB,row_factory=dict_row,autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute('set max_parallel_workers_per_gather=0')
            c.execute("set work_mem='8MB'")
            c.execute("set statement_timeout='180s'")
        for split in SPLITS:
            r=racer_pair(conn,split)
            g=global_pair(conn,split)
            print(fmt(f'OPPONENT_OOS_RACER split:{split} ',r),flush=True)
            print(fmt(f'OPPONENT_OOS_GLOBAL split:{split} ',g),flush=True)
    print('OPPONENT_OOS_RESULT=PASS_READ_ONLY',flush=True)
    print('OPPONENT_OOS_NEXT=shadow_only_if_reproducible_across_all_splits',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        msg=str(exc).replace('\n',' ').replace('\r',' ')[:700]
        print(f'OPPONENT_OOS_ERROR={type(exc).__name__}:{msg}',flush=True)
        raise
