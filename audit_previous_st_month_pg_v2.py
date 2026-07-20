# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from contextlib import closing
import psycopg
from psycopg.rows import dict_row

DATABASE_URL=os.getenv("DATABASE_URL","").strip()
START_DATE=os.getenv("AUDIT_START_DATE","2026-06-01").strip()
END_DATE=os.getenv("AUDIT_END_DATE","2026-06-30").strip()
SNAPSHOT_LABEL=os.getenv("SNAPSHOT_LABEL","final_ab").strip() or "final_ab"

def pct(a,b):
    if b is None or float(b) == 0.0:
        return 0.0
    return round(float(a) * 100.0 / float(b), 2)

def main():
    print("✅ audit_previous_st_month_pg_v2.py VERSION 2026-07-20 decimal-fix-v2", flush=True)
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    print(f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL}", flush=True)
    print("READ_ONLY=True", flush=True)

    with closing(psycopg.connect(DATABASE_URL,row_factory=dict_row)) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only;")

            print("\n=== DATABASE SIZE ===", flush=True)
            cur.execute("""
                select current_database() database_name,
                       pg_database_size(current_database()) database_bytes,
                       pg_size_pretty(pg_database_size(current_database())) database_size;
            """)
            print(dict(cur.fetchone()), flush=True)

            print("\n=== TARGET TABLE SIZES ===", flush=True)
            cur.execute("""
                select c.relname table_name,
                       pg_total_relation_size(c.oid) total_bytes,
                       pg_size_pretty(pg_total_relation_size(c.oid)) total_size,
                       pg_size_pretty(pg_relation_size(c.oid)) table_size,
                       pg_size_pretty(pg_indexes_size(c.oid)) index_size
                from pg_class c
                join pg_namespace n on n.oid=c.relnamespace
                where n.nspname='public'
                  and c.relname in (
                    'v2_realtime_race_condition_snapshots',
                    'v2_realtime_racer_condition_snapshots',
                    'v2_races','v2_race_entries'
                  )
                order by pg_total_relation_size(c.oid) desc;
            """)
            for r in cur.fetchall():
                print(dict(r), flush=True)

            print("\n=== OVERALL COVERAGE ===", flush=True)
            cur.execute("""
                with target as (
                    select race_id from v2_races
                    where race_date >= %s and race_date <= %s
                ),
                agg as (
                    select s.race_id,
                           count(distinct s.lane) snapshot_lanes,
                           count(distinct s.lane) filter(where s.previous_st is not null) previous_st_lanes,
                           count(*) snapshot_rows
                    from v2_realtime_racer_condition_snapshots s
                    join target t on t.race_id=s.race_id
                    where s.snapshot_label=%s
                    group by s.race_id
                )
                select
                    (select count(*) from target) target_races,
                    count(a.race_id) snapshot_races,
                    count(*) filter(where a.snapshot_lanes=6) snapshot_6lane_races,
                    count(*) filter(where a.snapshot_lanes between 1 and 5) snapshot_partial_races,
                    (select count(*) from target)-count(a.race_id) snapshot_zero_races,
                    coalesce(sum(a.snapshot_rows),0) snapshot_rows,
                    coalesce(sum(a.previous_st_lanes),0) previous_st_nonnull,
                    count(*) filter(where a.previous_st_lanes=6) previous_st_6lane_races,
                    count(*) filter(where a.previous_st_lanes between 1 and 5) previous_st_partial_races,
                    count(*) filter(where a.previous_st_lanes=0) previous_st_zero_races
                from agg a;
            """,(START_DATE,END_DATE,SNAPSHOT_LABEL))
            o=dict(cur.fetchone())
            o["snapshot_race_coverage_pct"]=pct(o["snapshot_races"],o["target_races"])
            o["snapshot_6lane_coverage_pct"]=pct(o["snapshot_6lane_races"],o["target_races"])
            o["previous_st_fill_pct_of_snapshot_rows"]=pct(o["previous_st_nonnull"],o["snapshot_rows"])
            print(o, flush=True)

            print("\n=== FIELD NONNULL COUNTS ===", flush=True)
            cur.execute("""
                select count(*) rows,
                       count(previous_st) previous_st_nonnull,
                       count(previous_finish) previous_finish_nonnull,
                       count(previous_course) previous_course_nonnull,
                       count(previous_race_no) previous_race_no_nonnull,
                       count(weight_kg) weight_nonnull,
                       count(adjustment_weight_kg) adjustment_weight_nonnull
                from v2_realtime_racer_condition_snapshots s
                join v2_races r on r.race_id=s.race_id
                where r.race_date >= %s and r.race_date <= %s
                  and s.snapshot_label=%s;
            """,(START_DATE,END_DATE,SNAPSHOT_LABEL))
            print(dict(cur.fetchone()), flush=True)

            print("\n=== MISSING / PARTIAL SNAPSHOT RACES ===", flush=True)
            cur.execute("""
                with agg as (
                    select s.race_id,
                           count(distinct s.lane) snapshot_lanes,
                           count(distinct s.lane) filter(where s.previous_st is not null) previous_st_lanes
                    from v2_realtime_racer_condition_snapshots s
                    where s.snapshot_label=%s
                    group by s.race_id
                )
                select r.race_date,r.race_id,coalesce(r.venue_id,r.venue_code) venue_id,r.race_no,
                       coalesce(a.snapshot_lanes,0) snapshot_lanes,
                       coalesce(a.previous_st_lanes,0) previous_st_lanes
                from v2_races r
                left join agg a on a.race_id=r.race_id
                where r.race_date >= %s and r.race_date <= %s
                  and coalesce(a.snapshot_lanes,0)<6
                order by r.race_date,venue_id,r.race_no
                limit 200;
            """,(SNAPSHOT_LABEL,START_DATE,END_DATE))
            rows=cur.fetchall()
            if not rows:
                print("none", flush=True)
            for r in rows:
                print(dict(r), flush=True)

            print("\n=== DUPLICATES ===", flush=True)
            cur.execute("""
                with d as (
                    select s.race_id,s.snapshot_label,s.lane,count(*) cnt
                    from v2_realtime_racer_condition_snapshots s
                    join v2_races r using(race_id)
                    where r.race_date >= %s and r.race_date <= %s
                      and s.snapshot_label=%s
                    group by s.race_id,s.snapshot_label,s.lane
                    having count(*)>1
                )
                select count(*) duplicate_groups,
                       coalesce(sum(cnt-1),0) extra_rows,
                       max(cnt) max_rows_per_key
                from d;
            """,(START_DATE,END_DATE,SNAPSHOT_LABEL))
            print(dict(cur.fetchone()), flush=True)

            print("\n=== SOURCE / LABEL COUNTS ===", flush=True)
            cur.execute("""
                select snapshot_label,coalesce(source,'(null)') source,count(*) rows
                from v2_realtime_racer_condition_snapshots s
                join v2_races r using(race_id)
                where r.race_date >= %s and r.race_date <= %s
                group by snapshot_label,coalesce(source,'(null)')
                order by rows desc;
            """,(START_DATE,END_DATE))
            for r in cur.fetchall():
                print(dict(r), flush=True)

    print("\n=== AUDIT FINISHED ===", flush=True)

if __name__=="__main__":
    main()