# -*- coding: utf-8 -*-
"""Read-only proof that protected Motor2 report selections survive hypothetical retention.

The script does not delete or mutate data. It constructs the proposed retained set in
CTEs and compares protected latest-row/group identities against the current full table.
Raw/history diagnostics are allowed to shrink and are reported separately.
"""
from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db_pg import fetch_all


def one(sql: str) -> dict:
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


BASE_CTE = """
with base as (
  select s.*,
         bool_or(s.evaluated_at is null) over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
         ) as key_has_unevaluated,
         row_number() over (
           partition by s.race_id,s.ticket,s.run_class,s.window_name
           order by s.snapshot_at desc,s.id desc
         ) as retain_rn
    from v2_v24_motor2_forward_shadow s
),
retained as (
  select * from base where key_has_unevaluated or retain_rn=1
)
"""


def performance_compare() -> dict:
    return one(BASE_CTE + """
, full_pick as (
  select id from (
    select id,
           row_number() over (
             partition by race_id,ticket,run_class,window_name
             order by snapshot_at desc,id desc
           ) as rn
      from base
     where evaluated_at is not null
       and result_ticket is not null
       and payout_yen > 0
  ) x where rn=1
), retained_pick as (
  select id from (
    select id,
           row_number() over (
             partition by race_id,ticket,run_class,window_name
             order by snapshot_at desc,id desc
           ) as rn
      from retained
     where evaluated_at is not null
       and result_ticket is not null
       and payout_yen > 0
  ) x where rn=1
), delta as (
  (select id from full_pick except select id from retained_pick)
  union all
  (select id from retained_pick except select id from full_pick)
)
select
  (select count(*) from full_pick) as full_rows,
  (select count(*) from retained_pick) as retained_rows,
  (select count(*) from delta) as diff_rows
""")


def robustness_compare(window_predicate: str) -> dict:
    return one(BASE_CTE + f"""
, full_pick as (
  select id from (
    select id,
           row_number() over (
             partition by race_id,ticket
             order by snapshot_at desc,id desc
           ) as rn
      from base
     where evaluated_at is not null
       and result_ticket is not null
       and payout_yen > 0
       and {window_predicate}
  ) x where rn=1
), retained_pick as (
  select id from (
    select id,
           row_number() over (
             partition by race_id,ticket
             order by snapshot_at desc,id desc
           ) as rn
      from retained
     where evaluated_at is not null
       and result_ticket is not null
       and payout_yen > 0
       and {window_predicate}
  ) x where rn=1
), delta as (
  (select id from full_pick except select id from retained_pick)
  union all
  (select id from retained_pick except select id from full_pick)
)
select
  (select count(*) from full_pick) as full_rows,
  (select count(*) from retained_pick) as retained_rows,
  (select count(*) from delta) as diff_rows
""")


def health_compare() -> dict:
    return one(BASE_CTE + """
, full_health_rows as (
  select b.*, r.deadline_at
    from base b
    left join v2_races r on r.race_id=b.race_id
   where b.window_name in ('morning','day','night')
     and b.evaluated_at is not null
     and b.result_ticket is not null
     and b.base_prob is not null
     and b.motor2_prob is not null
), retained_health_rows as (
  select b.*, r.deadline_at
    from retained b
    left join v2_races r on r.race_id=b.race_id
   where b.window_name in ('morning','day','night')
     and b.evaluated_at is not null
     and b.result_ticket is not null
     and b.base_prob is not null
     and b.motor2_prob is not null
), full_groups as (
  select race_id,run_class,window_name,snapshot_key,
         max(snapshot_at) as snapshot_at
    from full_health_rows
   group by race_id,run_class,window_name,snapshot_key
  having count(distinct result_ticket)=1
     and max(snapshot_at) is not null
     and min(deadline_at) is not null
     and max(snapshot_at) < min(deadline_at)
), retained_groups as (
  select race_id,run_class,window_name,snapshot_key,
         max(snapshot_at) as snapshot_at
    from retained_health_rows
   group by race_id,run_class,window_name,snapshot_key
  having count(distinct result_ticket)=1
     and max(snapshot_at) is not null
     and min(deadline_at) is not null
     and max(snapshot_at) < min(deadline_at)
), full_selected_group as (
  select race_id,run_class,window_name,snapshot_key from (
    select g.*,
           row_number() over (
             partition by race_id
             order by snapshot_at desc,run_class desc,window_name desc,snapshot_key desc
           ) as rn
      from full_groups g
  ) x where rn=1
), retained_selected_group as (
  select race_id,run_class,window_name,snapshot_key from (
    select g.*,
           row_number() over (
             partition by race_id
             order by snapshot_at desc,run_class desc,window_name desc,snapshot_key desc
           ) as rn
      from retained_groups g
  ) x where rn=1
), full_selected_rows as (
  select h.id
    from full_health_rows h
    join full_selected_group g using (race_id,run_class,window_name,snapshot_key)
), retained_selected_rows as (
  select h.id
    from retained_health_rows h
    join retained_selected_group g using (race_id,run_class,window_name,snapshot_key)
), group_delta as (
  (select * from full_selected_group except select * from retained_selected_group)
  union all
  (select * from retained_selected_group except select * from full_selected_group)
), row_delta as (
  (select id from full_selected_rows except select id from retained_selected_rows)
  union all
  (select id from retained_selected_rows except select id from full_selected_rows)
)
select
  (select count(*) from full_selected_group) as full_races,
  (select count(*) from retained_selected_group) as retained_races,
  (select count(*) from group_delta) as group_diff,
  (select count(*) from full_selected_rows) as full_sparse_rows,
  (select count(*) from retained_selected_rows) as retained_sparse_rows,
  (select count(*) from row_delta) as row_diff
""")


def diagnostic_change() -> dict:
    return one(BASE_CTE + """
, full_pre_groups as (
  select race_id,run_class,window_name,snapshot_key
    from base
   where window_name in ('morning','day','night')
     and evaluated_at is not null
   group by race_id,run_class,window_name,snapshot_key
), retained_pre_groups as (
  select race_id,run_class,window_name,snapshot_key
    from retained
   where window_name in ('morning','day','night')
     and evaluated_at is not null
   group by race_id,run_class,window_name,snapshot_key
)
select
  (select count(*) from base) as raw_rows_full,
  (select count(*) from retained) as raw_rows_retained,
  (select count(*) from full_pre_groups) as pre_snapshot_groups_full,
  (select count(*) from retained_pre_groups) as pre_snapshot_groups_retained
""")


def i(row: dict, key: str) -> int:
    return int(row.get(key) or 0)


def main() -> None:
    perf = performance_compare()
    robust_pre = robustness_compare("window_name in ('morning','day','night')")
    robust_final = robustness_compare("window_name='final'")
    health = health_compare()
    diag = diagnostic_change()

    print('STORAGE_RETENTION_INVARIANCE_MODE=READ_ONLY_HYPOTHETICAL_NO_CLEANUP')
    print(
        'STORAGE_RETENTION_PERFORMANCE='
        f"full:{i(perf,'full_rows')} retained:{i(perf,'retained_rows')} diff:{i(perf,'diff_rows')}"
    )
    print(
        'STORAGE_RETENTION_ROBUSTNESS_PRE='
        f"full:{i(robust_pre,'full_rows')} retained:{i(robust_pre,'retained_rows')} diff:{i(robust_pre,'diff_rows')}"
    )
    print(
        'STORAGE_RETENTION_ROBUSTNESS_FINAL='
        f"full:{i(robust_final,'full_rows')} retained:{i(robust_final,'retained_rows')} diff:{i(robust_final,'diff_rows')}"
    )
    print(
        'STORAGE_RETENTION_HEALTH_LATEST_PRE='
        f"full_races:{i(health,'full_races')} retained_races:{i(health,'retained_races')} "
        f"group_diff:{i(health,'group_diff')} full_sparse_rows:{i(health,'full_sparse_rows')} "
        f"retained_sparse_rows:{i(health,'retained_sparse_rows')} row_diff:{i(health,'row_diff')}"
    )
    print(
        'STORAGE_RETENTION_ALLOWED_DIAGNOSTIC_CHANGE='
        f"raw_rows_full:{i(diag,'raw_rows_full')} raw_rows_retained:{i(diag,'raw_rows_retained')} "
        f"pre_snapshot_groups_full:{i(diag,'pre_snapshot_groups_full')} "
        f"pre_snapshot_groups_retained:{i(diag,'pre_snapshot_groups_retained')}"
    )

    protected_diffs = (
        i(perf, 'diff_rows')
        + i(robust_pre, 'diff_rows')
        + i(robust_final, 'diff_rows')
        + i(health, 'group_diff')
        + i(health, 'row_diff')
    )
    if protected_diffs:
        raise SystemExit(f'STORAGE_RETENTION_INVARIANCE_RESULT=FAIL protected_diffs:{protected_diffs}')
    print('STORAGE_RETENTION_INVARIANCE_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
