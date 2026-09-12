# -*- coding: utf-8 -*-
"""Read-only inventory for Motor2 shadow retention research.

No writes, no cleanup, no model/LINE/Production changes.
"""
from __future__ import annotations

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
    candidate = one(
        """
        with ranked as (
          select id,evaluated_at,
                 row_number() over (
                   partition by race_id,ticket,run_class,window_name
                   order by snapshot_at desc,id desc
                 ) as rn,
                 bool_or(evaluated_at is null) over (
                   partition by race_id,ticket,run_class,window_name
                 ) as key_has_unevaluated
            from v2_v24_motor2_forward_shadow
        )
        select
          count(*) filter (where rn > 1 and not key_has_unevaluated) as hypothetical_removable_rows,
          count(*) filter (where key_has_unevaluated) as rows_in_blocked_keys
        from ranked
        """
    )

    print('STORAGE_RETENTION_INVENTORY_MODE=READ_ONLY_NO_CLEANUP')
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
    print(
        'STORAGE_RETENTION_HYPOTHETICAL='
        f"removable_rows:{int(candidate.get('hypothetical_removable_rows') or 0)} "
        f"rows_in_blocked_keys:{int(candidate.get('rows_in_blocked_keys') or 0)}"
    )
    print('STORAGE_RETENTION_INVENTORY_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
