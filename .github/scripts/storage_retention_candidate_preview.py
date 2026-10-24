# -*- coding: utf-8 -*-
"""Read-only preview of hypothetical Motor2 retention candidates.

This reports candidate scope only. It never changes database state.
The conservative cleanup scope intentionally excludes manual/test/live rows and
current-day FINAL rows even when the broader retention contract marks them removable.

The base CTE projects only columns required by this audit so the read-only preview can
stay inside a small temporary-file budget while Production storage is under pressure.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


CTE = """
with base as (
  select s.id,
         s.race_id,
         s.ticket,
         s.run_class,
         s.window_name,
         s.snapshot_key,
         s.snapshot_at,
         s.race_date,
         s.evaluated_at,
         s.result_ticket,
         s.base_prob,
         s.motor2_prob,
         row_number() over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
           order by s.snapshot_at desc,s.id desc
         ) as retain_rn,
         bool_or(s.evaluated_at is null) over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
         ) as key_has_unevaluated
    from v2_v24_motor2_forward_shadow s
),
health_source as (
  select b.id,b.race_id,b.run_class,b.window_name,b.snapshot_key,b.snapshot_at,
         b.result_ticket,r.deadline_at
    from base b
    left join v2_races r on r.race_id=b.race_id
   where b.window_name in ('morning','day','night')
     and b.evaluated_at is not null
     and b.result_ticket is not null
     and b.base_prob is not null
     and b.motor2_prob is not null
),
health_valid_groups as (
  select race_id,run_class,window_name,snapshot_key,max(snapshot_at) as snapshot_at
    from health_source
   group by race_id,run_class,window_name,snapshot_key
  having count(distinct result_ticket)=1
     and max(snapshot_at) is not null
     and min(deadline_at) is not null
     and max(snapshot_at) < min(deadline_at)
),
health_latest_time as (
  select race_id,max(snapshot_at) as snapshot_at
    from health_valid_groups
   group by race_id
),
health_protected_groups as (
  select g.race_id,g.run_class,g.window_name,g.snapshot_key
    from health_valid_groups g
    join health_latest_time t
      on t.race_id=g.race_id and t.snapshot_at=g.snapshot_at
),
health_protected_ids as (
  select h.id
    from health_source h
    join health_protected_groups g
      using (race_id,run_class,window_name,snapshot_key)
),
marked as (
  select b.id,b.race_id,b.run_class,b.window_name,b.snapshot_key,b.race_date,
         (
           b.key_has_unevaluated
           or b.retain_rn=1
           or b.id in (select id from health_protected_ids)
         ) as keep
    from base b
)
"""


def summary(where_sql: str) -> dict:
    return fetch_all(
        CTE + f"""
        select count(*) as candidate_rows,
               count(distinct race_id) as candidate_races,
               count(distinct snapshot_key) as snapshot_keys,
               min(race_date) as min_race_date,
               max(race_date) as max_race_date
          from marked
         where {where_sql}
        """
    )[0]


def main() -> None:
    overall = summary("not keep")
    conservative = summary(
        "not keep and run_class='final' and window_name='final' and race_date < current_date"
    )
    grouped = fetch_all(
        CTE + """
        select run_class,window_name,
               count(*) as candidate_rows,
               count(distinct race_id) as candidate_races,
               count(distinct snapshot_key) as snapshot_keys,
               min(race_date) as min_race_date,
               max(race_date) as max_race_date
          from marked
         where not keep
         group by run_class,window_name
         order by run_class,window_name
        """
    )

    print('STORAGE_RETENTION_CANDIDATE_PREVIEW_MODE=READ_ONLY_LOW_TEMP_NO_CLEANUP')
    print(
        'STORAGE_RETENTION_CANDIDATE_TOTAL='
        f"rows:{int(overall.get('candidate_rows') or 0)} "
        f"races:{int(overall.get('candidate_races') or 0)} "
        f"snapshot_keys:{int(overall.get('snapshot_keys') or 0)} "
        f"min_date:{overall.get('min_race_date')} max_date:{overall.get('max_race_date')}"
    )
    print(
        'STORAGE_RETENTION_CONSERVATIVE_FINAL_ONLY='
        f"rows:{int(conservative.get('candidate_rows') or 0)} "
        f"races:{int(conservative.get('candidate_races') or 0)} "
        f"snapshot_keys:{int(conservative.get('snapshot_keys') or 0)} "
        f"min_date:{conservative.get('min_race_date')} max_date:{conservative.get('max_race_date')}"
    )
    for row in grouped:
        print(
            'STORAGE_RETENTION_CANDIDATE_SCOPE='
            f"run_class:{row.get('run_class')} window:{row.get('window_name')} "
            f"rows:{int(row.get('candidate_rows') or 0)} "
            f"races:{int(row.get('candidate_races') or 0)} "
            f"snapshot_keys:{int(row.get('snapshot_keys') or 0)} "
            f"min_date:{row.get('min_race_date')} max_date:{row.get('max_race_date')}"
        )
    print('STORAGE_RETENTION_CANDIDATE_PREVIEW_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
