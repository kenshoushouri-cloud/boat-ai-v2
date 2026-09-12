# -*- coding: utf-8 -*-
"""Read-only inventory for Motor2 shadow retention research.

No writes, no cleanup, no model/LINE/Production changes.
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
    candidate = one(
        """
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
          select race_id,run_class,window_name,snapshot_key,
                 max(snapshot_at) as snapshot_at
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
                 (b.id in (select id from health_protected_ids)) as health_protected,
                 (
                   b.key_has_unevaluated
                   or b.retain_rn=1
                   or b.id in (select id from health_protected_ids)
                 ) as keep
            from base b
        )
        select
          count(*) filter (where not keep) as hypothetical_removable_rows,
          count(*) filter (where keep) as retained_rows,
          count(*) filter (where key_has_unevaluated) as rows_in_blocked_keys,
          count(*) filter (where health_protected) as health_protected_rows,
          count(*) filter (
            where health_protected and retain_rn > 1 and not key_has_unevaluated
          ) as extra_health_rows_preserved
        from marked
        """
    )

    ambiguous_latest_keys = int(ambiguity.get('ambiguous_latest_keys') or 0)
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
        'STORAGE_RETENTION_HYPOTHETICAL='
        f"removable_rows:{int(candidate.get('hypothetical_removable_rows') or 0)} "
        f"retained_rows:{int(candidate.get('retained_rows') or 0)} "
        f"rows_in_blocked_keys:{int(candidate.get('rows_in_blocked_keys') or 0)} "
        f"health_protected_rows:{int(candidate.get('health_protected_rows') or 0)} "
        f"extra_health_rows_preserved:{int(candidate.get('extra_health_rows_preserved') or 0)}"
    )
    if ambiguous_latest_keys:
        raise SystemExit('STORAGE_RETENTION_INVENTORY_RESULT=BLOCK_AMBIGUOUS_LATEST')
    print('STORAGE_RETENTION_INVENTORY_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
