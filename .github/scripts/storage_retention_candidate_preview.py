# -*- coding: utf-8 -*-
"""Read-only preview of hypothetical Motor2 retention candidates.

This reports candidate scope only. It never changes database state.
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
  select s.*,
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
  select b.*, r.deadline_at
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
  select b.*,
         (
           b.key_has_unevaluated
           or b.retain_rn=1
           or b.id in (select id from health_protected_ids)
         ) as keep
    from base b
)
"""


def main() -> None:
    overall = fetch_all(
        CTE + """
        select count(*) as candidate_rows,
               count(distinct race_id) as candidate_races,
               min(race_date) as min_race_date,
               max(race_date) as max_race_date
          from marked
         where not keep
        """
    )[0]
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

    print('STORAGE_RETENTION_CANDIDATE_PREVIEW_MODE=READ_ONLY_NO_CLEANUP')
    print(
        'STORAGE_RETENTION_CANDIDATE_TOTAL='
        f"rows:{int(overall.get('candidate_rows') or 0)} "
        f"races:{int(overall.get('candidate_races') or 0)} "
        f"min_date:{overall.get('min_race_date')} max_date:{overall.get('max_race_date')}"
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
