# -*- coding: utf-8 -*-
"""V5 exhibition provenance/timing audit. Read only."""
from __future__ import annotations
import json, os
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
ARCHIVE_CONTRACT="BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
REUSE_CONTRACT="REALTIME_EXHIBITION_TO_HISTORICAL_V1"

def one(sql, params=()):
    r=fetch_all(sql,params)
    return r[0] if r else {}

def main():
    total=one("""
      select count(*)::int n
      from v2_races r join v2_results rs on rs.race_id=r.race_id
      where r.race_date between %s and %s
        and (
          (exists(select 1 from information_schema.columns where table_schema='public' and table_name='v2_results' and column_name='first_lane')
           and rs.first_lane between 1 and 6)
          or rs.trifecta_ticket is not null
        )
    """,(START,END))
    rows=fetch_all("""
      select coalesce(e.source,'') source,
             coalesce(e.raw->>'source_contract','') source_contract,
             coalesce(e.raw->>'reuse_contract','') reuse_contract,
             coalesce(e.raw->>'snapshot_at_semantics','') snapshot_semantics,
             count(*)::int rows,
             count(distinct e.race_id)::int races,
             count(*) filter(where e.exhibition_time is not null)::int time_rows,
             count(*) filter(where e.exhibition_time_rank between 1 and 6)::int rank_rows
      from v2_realtime_exhibition_snapshots e
      join v2_races r on r.race_id=e.race_id
      where r.race_date between %s and %s and e.snapshot_label='historical'
      group by 1,2,3,4
      order by races desc,rows desc
    """,(START,END))
    race=one("""
      with x as (
        select r.race_id,r.deadline_at,
               count(distinct e.lane) filter(where e.lane between 1 and 6)::int lanes,
               count(distinct e.lane) filter(where e.lane between 1 and 6 and e.exhibition_time is not null)::int time_lanes,
               count(distinct e.lane) filter(where e.lane between 1 and 6 and e.exhibition_time_rank between 1 and 6)::int rank_lanes,
               count(*) filter(where e.raw->>'source_contract'=%s)::int archive_rows,
               count(*) filter(where e.raw->>'reuse_contract'=%s)::int reuse_rows,
               count(*) filter(where e.raw->>'reuse_contract'=%s and r.deadline_at is not null and e.snapshot_at < r.deadline_at)::int reuse_predeadline_rows,
               count(*) filter(where e.raw->>'reuse_contract'=%s and r.deadline_at is not null and e.snapshot_at >= r.deadline_at)::int reuse_late_rows,
               count(*) filter(where e.raw->>'historical_reconstruction'='true')::int reconstruction_rows,
               count(*) filter(where e.raw->>'prospective_evidence'='false')::int nonprospective_rows
        from v2_races r
        left join v2_realtime_exhibition_snapshots e
          on e.race_id=r.race_id and e.snapshot_label='historical'
        where r.race_date between %s and %s
        group by r.race_id,r.deadline_at
      ),
      c as (
        select *,
          case
            when rank_lanes=6 and archive_rows>=6 then 'archive_contract'
            when rank_lanes=6 and reuse_rows>=6 and reuse_predeadline_rows>=6 and reuse_late_rows=0 then 'reused_realtime_predeadline'
            when rank_lanes=6 and reuse_rows>=6 and reuse_late_rows>0 then 'reused_realtime_late'
            when rank_lanes=6 then 'legacy_or_mixed_unknown'
            else 'incomplete_rank'
          end as category
        from x
      )
      select
        count(*)::int target_races,
        count(*) filter(where time_lanes=6)::int complete_time_races,
        count(*) filter(where rank_lanes=6)::int complete_rank_races,
        count(*) filter(where category='archive_contract')::int archive_contract_races,
        count(*) filter(where category='reused_realtime_predeadline')::int reused_predeadline_races,
        count(*) filter(where category='reused_realtime_late')::int reused_late_races,
        count(*) filter(where category='legacy_or_mixed_unknown')::int legacy_or_mixed_unknown_races,
        count(*) filter(where rank_lanes=6 and reconstruction_rows>=6)::int reconstruction_tagged_races,
        count(*) filter(where rank_lanes=6 and nonprospective_rows>=6)::int explicit_nonprospective_races
      from c
    """,(ARCHIVE_CONTRACT,REUSE_CONTRACT,REUSE_CONTRACT,REUSE_CONTRACT,START,END))
    forward=one("""
      select
        count(distinct e.race_id) filter(where e.snapshot_label in ('learning_all','final_ab'))::int realtime_races,
        count(distinct e.race_id) filter(
          where e.snapshot_label in ('learning_all','final_ab')
            and r.deadline_at is not null and e.snapshot_at < r.deadline_at
        )::int realtime_any_predeadline_races,
        count(*) filter(
          where e.snapshot_label in ('learning_all','final_ab')
            and r.deadline_at is not null and e.snapshot_at >= r.deadline_at
        )::int realtime_late_rows
      from v2_realtime_exhibition_snapshots e
      join v2_races r on r.race_id=e.race_id
      where r.race_date between %s and %s
    """,(START,END))
    n=int(race.get("complete_rank_races") or 0)
    safe_hist=int(race.get("archive_contract_races") or 0)+int(race.get("reused_predeadline_races") or 0)
    out={
      "contract":"V5_EXHIBITION_PROVENANCE_TIMING_AUDIT_V1",
      "period":{"start":START,"end":END},
      "historical":{
        **{k:int(v or 0) for k,v in race.items()},
        "usable_truth_contract_races":safe_hist,
        "usable_truth_contract_pct_of_complete_rank":(100.0*safe_hist/n if n else None),
        "note":"archive_contract is retrospective predeadline-assumed truth and is NOT prospective evidence; reused_realtime_predeadline carries actual stored predeadline timestamps"
      },
      "source_groups":[dict(x) for x in rows],
      "realtime_forward_evidence":{k:int(v or 0) for k,v in forward.items()},
      "safety":{"db_write":False,"production_model_change":False}
    }
    print("V5_EXHIBITION_PROVENANCE_AUDIT_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True,default=str))

if __name__=="__main__": main()
