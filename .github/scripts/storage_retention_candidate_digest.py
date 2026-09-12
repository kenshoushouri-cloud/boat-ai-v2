# -*- coding: utf-8 -*-
"""Read-only deterministic digest for hypothetical Motor2 cleanup candidates.

This script never deletes or mutates rows. It reproduces the protected retention
contract, materializes only candidate metadata in the client, and prints a stable
SHA-256 digest plus breakdowns for later SQL review.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db_pg import fetch_all


CANDIDATE_SQL = """
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
select id,race_id,ticket,run_class,window_name,snapshot_key,snapshot_at,race_date,
       key_has_unevaluated,health_protected,retain_rn
  from marked
 where not keep
 order by id
"""

AMBIGUITY_SQL = """
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
select count(*) as ambiguous_latest_keys
  from latest_keys
 where snapshot_keys > 1
"""


def main() -> None:
    ambiguity_rows = fetch_all(AMBIGUITY_SQL)
    ambiguous = int(ambiguity_rows[0].get('ambiguous_latest_keys') or 0) if ambiguity_rows else 0
    if ambiguous:
        raise SystemExit(
            f'STORAGE_RETENTION_CANDIDATE_DIGEST_RESULT=BLOCK_AMBIGUOUS_LATEST count:{ambiguous}'
        )

    rows = [dict(r) for r in fetch_all(CANDIDATE_SQL)]
    digest = sha256()
    by_window: Counter[tuple[str, str]] = Counter()
    by_date: Counter[str] = Counter()

    for row in rows:
        if row.get('key_has_unevaluated') or row.get('health_protected'):
            raise SystemExit('STORAGE_RETENTION_CANDIDATE_DIGEST_RESULT=FAIL_PROTECTED_INTERSECTION')
        if int(row.get('retain_rn') or 0) <= 1:
            raise SystemExit('STORAGE_RETENTION_CANDIDATE_DIGEST_RESULT=FAIL_LATEST_INTERSECTION')
        record = '|'.join(
            str(row.get(k) or '')
            for k in (
                'id','race_id','ticket','run_class','window_name',
                'snapshot_key','snapshot_at','race_date'
            )
        )
        digest.update(record.encode('utf-8'))
        digest.update(b'\n')
        by_window[(str(row.get('run_class') or ''), str(row.get('window_name') or ''))] += 1
        by_date[str(row.get('race_date') or '')] += 1

    print('STORAGE_RETENTION_CANDIDATE_DIGEST_MODE=READ_ONLY_NO_DELETE')
    print(
        'STORAGE_RETENTION_CANDIDATE_SET='
        f"rows:{len(rows)} sha256:{digest.hexdigest()} "
        f"min_id:{rows[0]['id'] if rows else '-'} max_id:{rows[-1]['id'] if rows else '-'}"
    )
    for (run_class, window_name), count in sorted(by_window.items()):
        print(
            'STORAGE_RETENTION_CANDIDATE_WINDOW='
            f"run_class:{run_class} window:{window_name} rows:{count}"
        )
    for race_date, count in sorted(by_date.items()):
        print(f'STORAGE_RETENTION_CANDIDATE_DATE=date:{race_date} rows:{count}')
    print('STORAGE_RETENTION_CANDIDATE_PROTECTED_INTERSECTION=0')
    print('STORAGE_RETENTION_CANDIDATE_AMBIGUOUS_LATEST=0')
    print('STORAGE_RETENTION_CANDIDATE_DIGEST_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
