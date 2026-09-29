# -*- coding: utf-8 -*-
"""Read-only monthly historical data gap audit."""
from __future__ import annotations
import json, os
from datetime import date
import psycopg
from psycopg.rows import dict_row

START="2025-07-01"
END="2026-09-29"


def table_exists(cur, name:str)->bool:
    cur.execute("""select exists(
        select 1 from information_schema.tables
        where table_schema='public' and table_name=%s
    ) ok""",(name,))
    return bool(cur.fetchone()["ok"])


def main()->None:
    db=os.environ["DATABASE_URL"]
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
      with conn.cursor() as c:
        c.execute("set transaction read only")
        c.execute("set local statement_timeout='120s'")
        hist_racelist=table_exists(c,"v2_historical_racelist_reconstruction")
        c.execute("""
        with months as (
          select gs::date month_start,
                 (gs + interval '1 month - 1 day')::date month_end
          from generate_series(%s::date,date_trunc('month',%s::date),interval '1 month') gs
        ),
        base as (
          select date_trunc('month',race_date)::date m,count(distinct race_id)::int n
          from v2_races where race_date between %s and %s group by 1
        ),
        wx as (
          select date_trunc('month',race_date)::date m,count(distinct race_id)::int n
          from v2_realtime_weather_snapshots
          where race_date between %s and %s and snapshot_label='historical' group by 1
        ),
        ex6 as (
          select date_trunc('month',race_date)::date m,count(*)::int n from (
            select race_date,race_id from v2_realtime_exhibition_snapshots
            where race_date between %s and %s and snapshot_label='historical'
            group by race_date,race_id having count(distinct lane)=6
          ) x group by 1
        ),
        rc as (
          select date_trunc('month',race_date)::date m,count(distinct race_id)::int n
          from v2_realtime_race_condition_snapshots
          where race_date between %s and %s and snapshot_label='historical' group by 1
        ),
        rcr6 as (
          select date_trunc('month',race_date)::date m,count(*)::int n from (
            select race_date,race_id from v2_realtime_racer_condition_snapshots
            where race_date between %s and %s and snapshot_label='historical'
            group by race_date,race_id having count(distinct lane)=6
          ) x group by 1
        ),
        entry6 as (
          select date_trunc('month',r.race_date)::date m,
                 count(*) filter(where q.rows6=6)::int any6,
                 count(*) filter(where q.core6=6)::int core6,
                 count(*) filter(where q.f6=6)::int f6,
                 count(*) filter(where q.l6=6)::int l6,
                 count(*) filter(where q.motor6=6)::int motor6
          from (
            select e.race_id,
                   count(*)::int rows6,
                   count(*) filter(where e.racer_class is not null
                                      and e.national_win_rate is not null
                                      and e.national_place2_rate is not null
                                      and e.local_place2_rate is not null
                                      and e.avg_st is not null)::int core6,
                   count(*) filter(where e.f_count is not null)::int f6,
                   count(*) filter(where e.l_count is not null)::int l6,
                   count(*) filter(where e.motor_place2_rate is not null)::int motor6
            from v2_race_entries e
            join v2_races rr on rr.race_id=e.race_id
            where rr.race_date between %s and %s
            group by e.race_id
          ) q join v2_races r on r.race_id=q.race_id group by 1
        )
        select to_char(m.month_start,'YYYY-MM') month,
               coalesce(base.n,0) base_races,
               coalesce(wx.n,0) historical_weather_races,
               coalesce(ex6.n,0) historical_exhibition_full6,
               coalesce(rc.n,0) historical_race_condition_races,
               coalesce(rcr6.n,0) historical_racer_condition_full6,
               coalesce(entry6.any6,0) canonical_entry_full6,
               coalesce(entry6.core6,0) canonical_v4_base_full6,
               coalesce(entry6.motor6,0) canonical_motor2_full6,
               coalesce(entry6.f6,0) canonical_fcount_full6,
               coalesce(entry6.l6,0) canonical_lcount_full6
        from months m
        left join base on base.m=m.month_start
        left join wx on wx.m=m.month_start
        left join ex6 on ex6.m=m.month_start
        left join rc on rc.m=m.month_start
        left join rcr6 on rcr6.m=m.month_start
        left join entry6 on entry6.m=m.month_start
        order by m.month_start
        """,(START,END,START,END,START,END,START,END,START,END,START,END,START,END))
        rows=[dict(r) for r in c.fetchall()]
        if hist_racelist:
          c.execute("""
            select to_char(date_trunc('month',race_date),'YYYY-MM') month,
                   count(*) filter(where lanes=6)::int reconstructed_full6,
                   count(*) filter(where core=6)::int reconstructed_v4_base_full6,
                   count(*) filter(where fcnt=6)::int reconstructed_fcount_full6,
                   count(*) filter(where lcnt=6)::int reconstructed_lcount_full6,
                   count(*) filter(where motor=6)::int reconstructed_motor2_full6
            from (
              select race_date,race_id,count(*)::int lanes,
                     count(*) filter(where racer_class is not null
                       and national_win_rate is not null
                       and national_place2_rate is not null
                       and local_place2_rate is not null
                       and avg_st is not null)::int core,
                     count(*) filter(where f_count is not null)::int fcnt,
                     count(*) filter(where l_count is not null)::int lcnt,
                     count(*) filter(where motor_place2_rate is not null)::int motor
              from v2_historical_racelist_reconstruction
              where race_date between %s and %s
              group by race_date,race_id
            ) x group by 1 order by 1
          """,(START,END))
          rec={str(r["month"]):dict(r) for r in c.fetchall()}
          for row in rows:
            rr=rec.get(row["month"],{})
            for k in ("reconstructed_full6","reconstructed_v4_base_full6",
                      "reconstructed_fcount_full6","reconstructed_lcount_full6",
                      "reconstructed_motor2_full6"):
              row[k]=int(rr.get(k) or 0)
        else:
          for row in rows:
            for k in ("reconstructed_full6","reconstructed_v4_base_full6",
                      "reconstructed_fcount_full6","reconstructed_lcount_full6",
                      "reconstructed_motor2_full6"):
              row[k]=0
      conn.rollback()

    totals={}
    for key in rows[0].keys():
      if key=="month": continue
      totals[key]=sum(int(r[key]) for r in rows)
    payload={
      "contract":"HISTORICAL_GAP_AUDIT_V1",
      "period":{"start":START,"end":END},
      "read_only":True,
      "result_or_payout_read":False,
      "production_change":False,
      "months":rows,
      "totals":totals,
    }
    print("HIST_GAP_AUDIT="+json.dumps(payload,ensure_ascii=False,sort_keys=True))
    print("HIST_GAP_AUDIT_RESULT=PASS_READ_ONLY")


if __name__=="__main__":
    main()
