# -*- coding: utf-8 -*-
"""V5 B14 remaining collected pre-race field coverage audit. Read only."""
from __future__ import annotations
import json, os
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
LABEL="historical"

def scalar(sql, params=()):
    rows=fetch_all(sql, params)
    return rows[0] if rows else {}

def pct(a,b):
    return 100.0*a/b if b else 0.0

def main():
    base=scalar("""
      select count(*)::int target_races
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where r.race_date between %s and %s
        and coalesce(rs.result_status,'official')='official'
    """,(START,END))
    target=int(base["target_races"])

    racer_fields=[
      "weight_kg","adjustment_weight_kg","previous_race_no","previous_course",
      "previous_st","previous_finish"
    ]
    racer={}
    for f in racer_fields:
        row=scalar(f"""
          with x as (
            select s.race_id,
                   count(*) filter (where s.{f} is not null)::int filled
            from v2_realtime_racer_condition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s
              and s.snapshot_label=%s
            group by s.race_id
          )
          select count(*) filter (where filled>=1)::int any_races,
                 count(*) filter (where filled=6)::int complete6_races
          from x
        """,(START,END,LABEL))
        racer[f]={
          "any_races":int(row.get("any_races") or 0),
          "complete6_races":int(row.get("complete6_races") or 0),
          "complete6_pct":pct(int(row.get("complete6_races") or 0),target)
        }

    racer_events={}
    for f in ["is_new_propeller"]:
        row=scalar(f"""
          with x as (
            select s.race_id,
                   count(*) filter (where s.{f} is not null)::int nonnull,
                   count(*) filter (where s.{f} is true)::int true_count
            from v2_realtime_racer_condition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s and s.snapshot_label=%s
            group by s.race_id
          )
          select count(*) filter (where nonnull=6)::int complete6_races,
                 coalesce(sum(true_count),0)::int true_lane_events
          from x
        """,(START,END,LABEL))
        racer_events[f]={
          "complete6_races":int(row.get("complete6_races") or 0),
          "complete6_pct":pct(int(row.get("complete6_races") or 0),target),
          "true_lane_events":int(row.get("true_lane_events") or 0)
        }

    row=scalar("""
      with x as (
        select s.race_id,
               count(*) filter (
                 where s.parts_replacements is not null
                   and jsonb_typeof(s.parts_replacements)='array'
               )::int nonnull,
               count(*) filter (
                 where s.parts_replacements is not null
                   and jsonb_typeof(s.parts_replacements)='array'
                   and jsonb_array_length(s.parts_replacements)>0
               )::int nonempty
        from v2_realtime_racer_condition_snapshots s
        join v2_races r on r.race_id=s.race_id
        where r.race_date between %s and %s and s.snapshot_label=%s
        group by s.race_id
      )
      select count(*) filter (where nonnull=6)::int complete6_races,
             coalesce(sum(nonempty),0)::int nonempty_lane_events
      from x
    """,(START,END,LABEL))
    racer_events["parts_replacements"]={
      "complete6_races":int(row.get("complete6_races") or 0),
      "complete6_pct":pct(int(row.get("complete6_races") or 0),target),
      "nonempty_lane_events":int(row.get("nonempty_lane_events") or 0)
    }

    race_fields={}
    for f in ["is_stabilizer_used","is_fixed_entry","race_distance_m","has_new_propeller","parts_replacement_count"]:
        row=scalar(f"""
          select count(*) filter (where s.{f} is not null)::int nonnull_races
          from v2_realtime_race_condition_snapshots s
          join v2_races r on r.race_id=s.race_id
          where r.race_date between %s and %s and s.snapshot_label=%s
        """,(START,END,LABEL))
        n=int(row.get("nonnull_races") or 0)
        race_fields[f]={"nonnull_races":n,"coverage_pct":pct(n,target)}

    race_events={}
    for f in ["is_stabilizer_used","is_fixed_entry","has_new_propeller"]:
        row=scalar(f"""
          select count(*) filter (where s.{f} is true)::int true_races
          from v2_realtime_race_condition_snapshots s
          join v2_races r on r.race_id=s.race_id
          where r.race_date between %s and %s and s.snapshot_label=%s
        """,(START,END,LABEL))
        race_events[f]=int(row.get("true_races") or 0)
    row=scalar("""
      select count(*) filter (where coalesce(s.parts_replacement_count,0)>0)::int positive_races,
             count(*) filter (where s.race_distance_m is not null and s.race_distance_m<>1800)::int non1800_races
      from v2_realtime_race_condition_snapshots s
      join v2_races r on r.race_id=s.race_id
      where r.race_date between %s and %s and s.snapshot_label=%s
    """,(START,END,LABEL))
    race_events["parts_replacement_count_positive"]=int(row.get("positive_races") or 0)
    race_events["race_distance_non1800"]=int(row.get("non1800_races") or 0)

    exhibition={}
    for f in ["exhibition_time","start_timing","original_tilt","tilt_change"]:
        row=scalar(f"""
          with x as (
            select s.race_id, count(*) filter (where s.{f} is not null)::int filled
            from v2_realtime_exhibition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s and s.snapshot_label=%s
            group by s.race_id
          )
          select count(*) filter (where filled=6)::int complete6_races
          from x
        """,(START,END,LABEL))
        n=int(row.get("complete6_races") or 0)
        exhibition[f]={"complete6_races":n,"complete6_pct":pct(n,target)}

    out={
      "contract":"V5_B14_REMAINING_FIELD_COVERAGE_AUDIT_V1",
      "period":{"start":START,"end":END},
      "target_completed_races":target,
      "racer_condition":racer,
      "racer_condition_events":racer_events,
      "race_condition":race_fields,
      "race_condition_events":race_events,
      "exhibition_remaining":exhibition,
      "safety":{"db_write":False,"production_model_change":False}
    }
    print("V5_B14_REMAINING_COVERAGE_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True))

if __name__=="__main__": main()
