# -*- coding: utf-8 -*-
"""Read-only monthly historical data gap audit."""
from __future__ import annotations

import json
import os
from calendar import monthrange
from datetime import date

import psycopg
from psycopg.rows import dict_row

START=date(2025,7,1)
END=date(2026,9,29)


def month_windows():
    cur=START.replace(day=1)
    while cur<=END:
        last=date(cur.year,cur.month,monthrange(cur.year,cur.month)[1])
        yield cur,max(cur,START),min(last,END)
        cur=date(cur.year+1,1,1) if cur.month==12 else date(cur.year,cur.month+1,1)


def scalar(cur,sql,params):
    cur.execute(sql,params)
    row=cur.fetchone()
    return int(next(iter(row.values())) or 0)


def table_exists(cur,name):
    cur.execute("""select exists(
      select 1 from information_schema.tables
      where table_schema='public' and table_name=%s
    ) as ok""",(name,))
    return bool(cur.fetchone()["ok"])


def full6(cur,table,a,b):
    return scalar(cur,f"""select count(*) as n from (
      select race_id from {table}
      where race_date between %s and %s and snapshot_label='historical'
      group by race_id having count(distinct lane)=6
    ) x""",(a,b))


def main():
    with psycopg.connect(os.environ["DATABASE_URL"],row_factory=dict_row,autocommit=False) as conn:
      with conn.cursor() as c:
        c.execute("set transaction read only")
        c.execute("set local statement_timeout='120s'")
        has_reconstruction=table_exists(c,"v2_historical_racelist_reconstruction")
        rows=[]
        for month_start,a,b in month_windows():
            row={"month":month_start.strftime("%Y-%m")}
            row["base_races"]=scalar(c,
              "select count(distinct race_id) as n from v2_races where race_date between %s and %s",(a,b))
            row["historical_weather_races"]=scalar(c,
              """select count(distinct race_id) as n from v2_realtime_weather_snapshots
                 where race_date between %s and %s and snapshot_label='historical'""",(a,b))
            row["historical_exhibition_full6"]=full6(c,"v2_realtime_exhibition_snapshots",a,b)
            row["historical_race_condition_races"]=scalar(c,
              """select count(distinct race_id) as n from v2_realtime_race_condition_snapshots
                 where race_date between %s and %s and snapshot_label='historical'""",(a,b))
            row["historical_racer_condition_full6"]=full6(c,"v2_realtime_racer_condition_snapshots",a,b)

            c.execute("""
              select
                count(*) filter(where rows6=6)::int as canonical_entry_full6,
                count(*) filter(where core6=6)::int as canonical_v4_base_full6,
                count(*) filter(where motor6=6)::int as canonical_motor2_full6,
                count(*) filter(where f6=6)::int as canonical_fcount_full6,
                count(*) filter(where l6=6)::int as canonical_lcount_full6
              from (
                select r.race_id,
                       count(*)::int rows6,
                       count(*) filter(where e.racer_class is not null
                         and e.national_win_rate is not null
                         and e.national_place2_rate is not null
                         and e.local_place2_rate is not null
                         and e.avg_st is not null)::int core6,
                       count(*) filter(where e.motor_place2_rate is not null)::int motor6,
                       count(*) filter(where e.f_count is not null)::int f6,
                       count(*) filter(where e.l_count is not null)::int l6
                from v2_races r
                join v2_race_entries e on e.race_id=r.race_id
                where r.race_date between %s and %s
                group by r.race_id
              ) q
            """,(a,b))
            row.update({k:int(v or 0) for k,v in dict(c.fetchone()).items()})

            if has_reconstruction:
                c.execute("""
                  select
                    count(*) filter(where rows6=6)::int as reconstructed_full6,
                    count(*) filter(where core6=6)::int as reconstructed_v4_base_full6,
                    count(*) filter(where motor6=6)::int as reconstructed_motor2_full6,
                    count(*) filter(where f6=6)::int as reconstructed_fcount_full6,
                    count(*) filter(where l6=6)::int as reconstructed_lcount_full6
                  from (
                    select race_id,
                           count(*)::int rows6,
                           count(*) filter(where racer_class is not null
                             and national_win_rate is not null
                             and national_place2_rate is not null
                             and local_place2_rate is not null
                             and avg_st is not null)::int core6,
                           count(*) filter(where motor_place2_rate is not null)::int motor6,
                           count(*) filter(where f_count is not null)::int f6,
                           count(*) filter(where l_count is not null)::int l6
                    from v2_historical_racelist_reconstruction
                    where race_date between %s and %s
                    group by race_id
                  ) q
                """,(a,b))
                row.update({k:int(v or 0) for k,v in dict(c.fetchone()).items()})
            else:
                for k in (
                  "reconstructed_full6","reconstructed_v4_base_full6",
                  "reconstructed_motor2_full6","reconstructed_fcount_full6",
                  "reconstructed_lcount_full6",
                ):
                    row[k]=0

            row["missing_weather"]=max(0,row["base_races"]-row["historical_weather_races"])
            row["missing_exhibition_full6"]=max(0,row["base_races"]-row["historical_exhibition_full6"])
            row["missing_v4_base_full6"]=max(0,row["base_races"]-max(
                row["canonical_v4_base_full6"],row["reconstructed_v4_base_full6"]))
            rows.append(row)
      conn.rollback()

    totals={k:sum(int(r[k]) for r in rows) for k in rows[0] if k!="month"}
    payload={
      "contract":"HISTORICAL_GAP_AUDIT_V2",
      "period":{"start":START.isoformat(),"end":END.isoformat()},
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
