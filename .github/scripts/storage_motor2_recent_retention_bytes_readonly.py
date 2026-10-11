# -*- coding: utf-8 -*-
"""Read-only recent-byte audit for conservative Motor2 retention candidates.

Scope is deliberately narrow: completed dates in the last seven calendar days,
run_class=final, window_name=final. In this scope the PRE-health protection rule
cannot apply because it only protects morning/day/night groups. Therefore the
frozen retention contract reduces exactly to:
- keep every logical key if any row is unevaluated;
- otherwise keep the latest (snapshot_at,id) row for the key.

No mutation is performed. Logical tuple bytes are a comparison metric only and
are not guaranteed physical Railway-volume reclaim.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


CTE = """
with scoped as (
  select s.id,
         s.race_id,
         s.ticket,
         s.race_date,
         s.snapshot_at,
         s.evaluated_at,
         pg_column_size(s)::bigint as row_bytes,
         row_number() over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
           order by s.snapshot_at desc,s.id desc
         ) as retain_rn,
         bool_or(s.evaluated_at is null) over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
         ) as key_has_unevaluated
    from v2_v24_motor2_forward_shadow s
   where s.run_class='final'
     and s.window_name='final'
     and s.race_date >= current_date - 7
     and s.race_date < current_date
),
marked as (
  select *, (key_has_unevaluated or retain_rn=1) as keep
    from scoped
)
"""


def main() -> None:
    total = fetch_all(
        CTE + """
        select count(*)::bigint as rows,
               count(distinct race_id)::bigint as races,
               coalesce(sum(row_bytes),0)::bigint as logical_bytes,
               count(*) filter (where not keep)::bigint as candidate_rows,
               count(distinct race_id) filter (where not keep)::bigint as candidate_races,
               coalesce(sum(row_bytes) filter (where not keep),0)::bigint as candidate_logical_bytes,
               count(*) filter (where key_has_unevaluated)::bigint as unevaluated_protected_rows,
               min(race_date) as min_date,
               max(race_date) as max_date
          from marked
        """
    )[0]
    daily = fetch_all(
        CTE + """
        select race_date,
               count(*)::bigint as rows,
               coalesce(sum(row_bytes),0)::bigint as logical_bytes,
               count(*) filter (where not keep)::bigint as candidate_rows,
               coalesce(sum(row_bytes) filter (where not keep),0)::bigint as candidate_logical_bytes
          from marked
         group by race_date
         order by race_date
        """
    )

    rows = int(total.get('rows') or 0)
    logical = int(total.get('logical_bytes') or 0)
    candidate_rows = int(total.get('candidate_rows') or 0)
    candidate_bytes = int(total.get('candidate_logical_bytes') or 0)
    print('STORAGE_MOTOR2_RECENT_RETENTION_MODE=READ_ONLY_NO_MUTATION')
    print(
        'STORAGE_MOTOR2_RECENT_RETENTION_TOTAL='
        f"rows:{rows} races:{int(total.get('races') or 0)} logical_bytes:{logical} "
        f"candidate_rows:{candidate_rows} candidate_races:{int(total.get('candidate_races') or 0)} "
        f"candidate_logical_bytes:{candidate_bytes} "
        f"candidate_row_pct:{(candidate_rows*100.0/rows if rows else 0.0):.4f} "
        f"candidate_logical_pct:{(candidate_bytes*100.0/logical if logical else 0.0):.4f} "
        f"avg_candidate_rows_per_calendar_day:{candidate_rows/7.0:.2f} "
        f"avg_candidate_logical_bytes_per_calendar_day:{candidate_bytes/7.0:.2f} "
        f"unevaluated_protected_rows:{int(total.get('unevaluated_protected_rows') or 0)} "
        f"min_date:{total.get('min_date')} max_date:{total.get('max_date')}"
    )
    for row in daily:
        print(
            'STORAGE_MOTOR2_RECENT_RETENTION_DAY='
            f"date:{row.get('race_date')} rows:{int(row.get('rows') or 0)} "
            f"logical_bytes:{int(row.get('logical_bytes') or 0)} "
            f"candidate_rows:{int(row.get('candidate_rows') or 0)} "
            f"candidate_logical_bytes:{int(row.get('candidate_logical_bytes') or 0)}"
        )
    print('STORAGE_MOTOR2_RECENT_RETENTION_INTERPRETATION=LOGICAL_ONLY_NOT_PHYSICAL_RECLAIM')
    print('STORAGE_MOTOR2_RECENT_RETENTION_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
