# -*- coding: utf-8 -*-
"""Low-temp read-only inventory for Motor2 shadow retention research.

No writes, no cleanup, no model/LINE/Production changes.
Heavy retention-candidate/invariance CTEs are intentionally not executed here:
Production disk pressure has already caused pgsql_tmp ENOSPC, and the live audit
runs with a 64 MiB temp-file cap. The frozen candidate digest is re-run only at
a future pre-delete approval gate, not in continuous CI.
"""
from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db_pg import fetch_all


def one(sql: str, params=()):
    rows = fetch_all(sql, params)
    return dict(rows[0]) if rows else {}


def main() -> None:
    size = one(
        """
        select
          pg_total_relation_size('v2_v24_motor2_forward_shadow') as total_bytes,
          pg_relation_size('v2_v24_motor2_forward_shadow') as heap_bytes,
          pg_indexes_size('v2_v24_motor2_forward_shadow') as index_bytes
        """
    )
    counts = one(
        """
        select
          count(*) as rows,
          count(distinct (race_id,ticket,run_class,window_name)) as logical_keys,
          count(distinct (race_id,run_class,window_name,snapshot_key)) as snapshot_groups,
          count(*) filter (where evaluated_at is null) as unevaluated_rows,
          min(race_date) as min_race_date,
          max(race_date) as max_race_date
        from v2_v24_motor2_forward_shadow
        """
    )
    by_window = fetch_all(
        """
        select run_class,window_name,
               count(*) as rows,
               count(distinct snapshot_key) as snapshot_keys,
               count(*) filter (where evaluated_at is null) as unevaluated_rows
          from v2_v24_motor2_forward_shadow
         group by run_class,window_name
         order by run_class,window_name
        """
    )
    growth7 = fetch_all(
        """
        select run_class,window_name,
               count(*)::bigint as rows,
               coalesce(sum(pg_column_size(s)),0)::bigint as logical_row_bytes,
               count(distinct (race_id,run_class,window_name,snapshot_key))::bigint as snapshot_groups,
               count(distinct race_id)::bigint as races,
               count(*) filter (where evaluated_at is null)::bigint as unevaluated_rows
          from v2_v24_motor2_forward_shadow s
         where race_date >= current_date - 7
           and race_date < current_date
         group by run_class,window_name
         order by run_class,window_name
        """
    )
    growth7_total = one(
        """
        select count(*)::bigint as rows,
               coalesce(sum(pg_column_size(s)),0)::bigint as logical_row_bytes,
               count(distinct (race_id,run_class,window_name,snapshot_key))::bigint as snapshot_groups,
               count(distinct race_id)::bigint as races,
               count(*) filter (where evaluated_at is null)::bigint as unevaluated_rows
          from v2_v24_motor2_forward_shadow s
         where race_date >= current_date - 7
           and race_date < current_date
        """
    )
    ambiguity = one(
        """
        with latest as (
          select race_id,ticket,run_class,window_name,max(snapshot_at) as latest_at
            from v2_v24_motor2_forward_shadow
           group by race_id,ticket,run_class,window_name
        ), latest_keys as (
          select s.race_id,s.ticket,s.run_class,s.window_name,
                 count(distinct s.snapshot_key) as snapshot_keys
            from v2_v24_motor2_forward_shadow s
            join latest l
              on l.race_id=s.race_id
             and l.ticket=s.ticket
             and l.run_class=s.run_class
             and l.window_name=s.window_name
             and l.latest_at=s.snapshot_at
           group by s.race_id,s.ticket,s.run_class,s.window_name
        )
        select count(*) filter (where snapshot_keys > 1) as ambiguous_latest_keys
          from latest_keys
        """
    )

    ambiguous_latest_keys = int(ambiguity.get('ambiguous_latest_keys') or 0)
    print('STORAGE_RETENTION_INVENTORY_MODE=READ_ONLY_LOW_TEMP_NO_CLEANUP')
    print(
        'STORAGE_RETENTION_SIZE='
        f"total_bytes:{int(size.get('total_bytes') or 0)} "
        f"heap_bytes:{int(size.get('heap_bytes') or 0)} "
        f"index_bytes:{int(size.get('index_bytes') or 0)}"
    )
    print(
        'STORAGE_RETENTION_COUNTS='
        f"rows:{int(counts.get('rows') or 0)} "
        f"logical_keys:{int(counts.get('logical_keys') or 0)} "
        f"snapshot_groups:{int(counts.get('snapshot_groups') or 0)} "
        f"unevaluated_rows:{int(counts.get('unevaluated_rows') or 0)} "
        f"min_date:{counts.get('min_race_date')} max_date:{counts.get('max_race_date')}"
    )
    for r in by_window:
        print(
            'STORAGE_RETENTION_WINDOW='
            f"run_class:{r.get('run_class')} window:{r.get('window_name')} "
            f"rows:{int(r.get('rows') or 0)} snapshot_keys:{int(r.get('snapshot_keys') or 0)} "
            f"unevaluated_rows:{int(r.get('unevaluated_rows') or 0)}"
        )
    recent_rows = int(growth7_total.get('rows') or 0)
    recent_bytes = int(growth7_total.get('logical_row_bytes') or 0)
    print(
        'STORAGE_RETENTION_RECENT7_TOTAL='
        f"rows:{recent_rows} logical_row_bytes:{recent_bytes} "
        f"snapshot_groups:{int(growth7_total.get('snapshot_groups') or 0)} "
        f"races:{int(growth7_total.get('races') or 0)} "
        f"unevaluated_rows:{int(growth7_total.get('unevaluated_rows') or 0)} "
        f"avg_rows_per_completed_day:{recent_rows / 7.0:.2f} "
        f"avg_logical_bytes_per_completed_day:{recent_bytes / 7.0:.2f}"
    )
    for r in growth7:
        rows7 = int(r.get('rows') or 0)
        bytes7 = int(r.get('logical_row_bytes') or 0)
        print(
            'STORAGE_RETENTION_RECENT7_WINDOW='
            f"run_class:{r.get('run_class')} window:{r.get('window_name')} "
            f"rows:{rows7} logical_row_bytes:{bytes7} "
            f"snapshot_groups:{int(r.get('snapshot_groups') or 0)} "
            f"races:{int(r.get('races') or 0)} "
            f"unevaluated_rows:{int(r.get('unevaluated_rows') or 0)} "
            f"avg_rows_per_completed_day:{rows7 / 7.0:.2f} "
            f"avg_logical_bytes_per_completed_day:{bytes7 / 7.0:.2f}"
        )
    print(f'STORAGE_RETENTION_AMBIGUOUS_LATEST_KEYS={ambiguous_latest_keys}')
    print(
        'STORAGE_RETENTION_HEAVY_CANDIDATE_AUDIT='
        'status:DEFERRED_PRE_DELETE_APPROVAL_GATE '
        'reason:PRODUCTION_TEMP_SPACE_PRESSURE'
    )
    if ambiguous_latest_keys:
        raise SystemExit('STORAGE_RETENTION_INVENTORY_RESULT=BLOCK_AMBIGUOUS_LATEST')
    print('STORAGE_RETENTION_INVENTORY_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
