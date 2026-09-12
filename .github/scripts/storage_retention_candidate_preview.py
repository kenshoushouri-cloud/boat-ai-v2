# -*- coding: utf-8 -*-
"""Read-only preview of hypothetical Motor2 retention candidates.

This reports candidate scope only. It never changes database state.
The conservative cleanup scope intentionally excludes manual/test/live rows and
current-day FINAL rows even when the broader retention contract marks them removable.

The base CTE projects only columns required by this audit so the read-only preview can
stay inside a small temporary-file budget while Production storage is under pressure.
Logical candidate bytes are computed only after candidate IDs are resolved; they are a
comparison metric and are not a promise of physical Railway-volume reclaim.
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
    rows = fetch_all(
        CTE + f"""
        select count(*)::bigint as candidate_rows,
               count(distinct m.race_id)::bigint as candidate_races,
               count(distinct m.snapshot_key)::bigint as snapshot_keys,
               min(m.race_date) as min_race_date,
               max(m.race_date) as max_race_date,
               coalesce(sum(pg_column_size(s)),0)::bigint as logical_bytes
          from marked m
          join v2_v24_motor2_forward_shadow s on s.id=m.id
         where {where_sql}
        """
    )
    return dict(rows[0]) if rows else {}


def main() -> None:
    overall = summary("not m.keep")
    conservative = summary(
        "not m.keep and m.run_class='final' and m.window_name='final' and m.race_date < current_date"
    )
    recent7 = summary(
        "not m.keep and m.run_class='final' and m.window_name='final' "
        "and m.race_date >= current_date - 7 and m.race_date < current_date"
    )
    grouped = fetch_all(
        CTE + """
        select m.run_class,m.window_name,
               count(*)::bigint as candidate_rows,
               count(distinct m.race_id)::bigint as candidate_races,
               count(distinct m.snapshot_key)::bigint as snapshot_keys,
               min(m.race_date) as min_race_date,
               max(m.race_date) as max_race_date,
               coalesce(sum(pg_column_size(s)),0)::bigint as logical_bytes
          from marked m
          join v2_v24_motor2_forward_shadow s on s.id=m.id
         where not m.keep
         group by m.run_class,m.window_name
         order by m.run_class,m.window_name
        """
    )
    daily = fetch_all(
        CTE + """
        select m.race_date,
               count(*)::bigint as candidate_rows,
               coalesce(sum(pg_column_size(s)),0)::bigint as logical_bytes
          from marked m
          join v2_v24_motor2_forward_shadow s on s.id=m.id
         where not m.keep
           and m.run_class='final'
           and m.window_name='final'
           and m.race_date >= current_date - 7
           and m.race_date < current_date
         group by m.race_date
         order by m.race_date
        """
    )

    print('STORAGE_RETENTION_CANDIDATE_PREVIEW_MODE=READ_ONLY_LOW_TEMP_NO_CLEANUP')
    print(
        'STORAGE_RETENTION_CANDIDATE_TOTAL='
        f"rows:{int(overall.get('candidate_rows') or 0)} "
        f"races:{int(overall.get('candidate_races') or 0)} "
        f"snapshot_keys:{int(overall.get('snapshot_keys') or 0)} "
        f"logical_bytes:{int(overall.get('logical_bytes') or 0)} "
        f"min_date:{overall.get('min_race_date')} max_date:{overall.get('max_race_date')}"
    )
    print(
        'STORAGE_RETENTION_CONSERVATIVE_FINAL_ONLY='
        f"rows:{int(conservative.get('candidate_rows') or 0)} "
        f"races:{int(conservative.get('candidate_races') or 0)} "
        f"snapshot_keys:{int(conservative.get('snapshot_keys') or 0)} "
        f"logical_bytes:{int(conservative.get('logical_bytes') or 0)} "
        f"min_date:{conservative.get('min_race_date')} max_date:{conservative.get('max_race_date')}"
    )
    recent_rows = int(recent7.get('candidate_rows') or 0)
    recent_bytes = int(recent7.get('logical_bytes') or 0)
    print(
        'STORAGE_RETENTION_CONSERVATIVE_RECENT7='
        f"rows:{recent_rows} races:{int(recent7.get('candidate_races') or 0)} "
        f"snapshot_keys:{int(recent7.get('snapshot_keys') or 0)} "
        f"logical_bytes:{recent_bytes} "
        f"avg_rows_per_calendar_day:{recent_rows/7.0:.2f} "
        f"avg_logical_bytes_per_calendar_day:{recent_bytes/7.0:.2f} "
        f"min_date:{recent7.get('min_race_date')} max_date:{recent7.get('max_race_date')}"
    )
    for row in grouped:
        print(
            'STORAGE_RETENTION_CANDIDATE_SCOPE='
            f"run_class:{row.get('run_class')} window:{row.get('window_name')} "
            f"rows:{int(row.get('candidate_rows') or 0)} "
            f"races:{int(row.get('candidate_races') or 0)} "
            f"snapshot_keys:{int(row.get('snapshot_keys') or 0)} "
            f"logical_bytes:{int(row.get('logical_bytes') or 0)} "
            f"min_date:{row.get('min_race_date')} max_date:{row.get('max_race_date')}"
        )
    for row in daily:
        print(
            'STORAGE_RETENTION_CONSERVATIVE_DAY='
            f"date:{row.get('race_date')} rows:{int(row.get('candidate_rows') or 0)} "
            f"logical_bytes:{int(row.get('logical_bytes') or 0)}"
        )
    print('STORAGE_RETENTION_CANDIDATE_BYTES_INTERPRETATION=LOGICAL_ONLY_NOT_PHYSICAL_RECLAIM')
    print('STORAGE_RETENTION_CANDIDATE_PREVIEW_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
