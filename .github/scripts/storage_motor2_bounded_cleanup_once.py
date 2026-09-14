# -*- coding: utf-8 -*-
"""One-time bounded Production cleanup for obsolete Motor2 FINAL snapshots.

This script is intentionally fail-closed and is only for the explicitly approved
2026-09-15 first cleanup batch. It recomputes the frozen retention candidate set
inside one REPEATABLE READ transaction and commits only when the exact expected
conservative FINAL/final count + SHA-256 + scope match.

It does not run storage compaction maintenance, alter schema, touch other tables,
change Railway config, change LINE/model/purchase behavior, or create a recurring
retention job.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import os
import sys

import psycopg
from psycopg.rows import dict_row

EXPECTED_ROWS = 44203
EXPECTED_SHA256 = "8d178d854d7b6bfb6a5c6ffdd183e1977f8c6258bd3658c9b0f75fbbf91f203f"
EXPECTED_MIN_DATE = "2026-08-20"
EXPECTED_MAX_DATE = "2026-09-12"
EXPECTED_RACES = 2456
EXPECTED_SNAPSHOT_KEYS = 908

CANDIDATE_SQL = r"""
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
  select b.id,b.race_id,b.ticket,b.run_class,b.window_name,b.snapshot_key,
         b.snapshot_at,b.race_date,b.key_has_unevaluated,b.retain_rn,
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

AMBIGUITY_SQL = r"""
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


def canonical_record(row: dict) -> bytes:
    return (
        "|".join(
            str(row.get(k) or "")
            for k in (
                "id", "race_id", "ticket", "run_class", "window_name",
                "snapshot_key", "snapshot_at", "race_date",
            )
        ) + "\n"
    ).encode("utf-8")


def digest_rows(rows: list[dict]) -> str:
    digest = sha256()
    for row in rows:
        digest.update(canonical_record(row))
    return digest.hexdigest()


def fail(message: str) -> None:
    print(f"MOTOR2_CLEANUP_RESULT=BLOCK {message}", file=sys.stderr)
    raise RuntimeError(message)


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        fail("DATABASE_URL_MISSING")

    print("MOTOR2_CLEANUP_MODE=EXPLICIT_USER_APPROVED_BOUNDED_ONCE")
    print(f"MOTOR2_CLEANUP_EXPECTED_ROWS={EXPECTED_ROWS}")
    print(f"MOTOR2_CLEANUP_EXPECTED_SHA256={EXPECTED_SHA256}")

    with psycopg.connect(db_url, autocommit=False, row_factory=dict_row) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("set transaction isolation level repeatable read")
                cur.execute("set local statement_timeout = '120s'")
                cur.execute("set local lock_timeout = '5s'")

                cur.execute(AMBIGUITY_SQL)
                ambiguous = int(cur.fetchone()["ambiguous_latest_keys"] or 0)
                if ambiguous != 0:
                    fail(f"AMBIGUOUS_LATEST={ambiguous}")

                cur.execute(CANDIDATE_SQL)
                all_rows = [dict(r) for r in cur.fetchall()]
                final_rows = [
                    row for row in all_rows
                    if str(row.get("run_class") or "") == "final"
                    and str(row.get("window_name") or "") == "final"
                ]

                if any(bool(r.get("key_has_unevaluated")) for r in final_rows):
                    fail("UNEVALUATED_PROTECTED_INTERSECTION")
                if any(bool(r.get("health_protected")) for r in final_rows):
                    fail("HEALTH_PROTECTED_INTERSECTION")
                if any(int(r.get("retain_rn") or 0) <= 1 for r in final_rows):
                    fail("LATEST_INTERSECTION")

                count = len(final_rows)
                digest = digest_rows(final_rows)
                dates = sorted({str(r.get("race_date") or "") for r in final_rows})
                races = {str(r.get("race_id") or "") for r in final_rows}
                snapshot_keys = {str(r.get("snapshot_key") or "") for r in final_rows}

                min_date = dates[0] if dates else ""
                max_date = dates[-1] if dates else ""
                print(
                    "MOTOR2_CLEANUP_PREFLIGHT="
                    f"rows:{count} sha256:{digest} min_date:{min_date} max_date:{max_date} "
                    f"races:{len(races)} snapshot_keys:{len(snapshot_keys)} ambiguous:{ambiguous}"
                )

                if count != EXPECTED_ROWS:
                    fail(f"ROW_COUNT_MISMATCH actual={count}")
                if digest != EXPECTED_SHA256:
                    fail(f"DIGEST_MISMATCH actual={digest}")
                if min_date != EXPECTED_MIN_DATE or max_date != EXPECTED_MAX_DATE:
                    fail(f"DATE_RANGE_MISMATCH actual={min_date}..{max_date}")
                if len(races) != EXPECTED_RACES:
                    fail(f"RACE_COUNT_MISMATCH actual={len(races)}")
                if len(snapshot_keys) != EXPECTED_SNAPSHOT_KEYS:
                    fail(f"SNAPSHOT_KEY_COUNT_MISMATCH actual={len(snapshot_keys)}")
                if any(str(r.get("race_date") or "") >= date.today().isoformat() for r in final_rows):
                    fail("CURRENT_OR_FUTURE_DATE_INTERSECTION")

                ids = [int(r["id"]) for r in final_rows]
                cur.execute(
                    """
                    delete from v2_v24_motor2_forward_shadow
                     where id = any(%s)
                       and run_class = 'final'
                       and window_name = 'final'
                    returning id
                    """,
                    (ids,),
                )
                deleted_ids = {int(r["id"]) for r in cur.fetchall()}
                if len(deleted_ids) != EXPECTED_ROWS:
                    fail(f"DELETE_COUNT_MISMATCH actual={len(deleted_ids)}")
                if deleted_ids != set(ids):
                    fail("DELETE_ID_SET_MISMATCH")

                cur.execute(
                    "select count(*) as remaining from v2_v24_motor2_forward_shadow where id = any(%s)",
                    (ids,),
                )
                remaining = int(cur.fetchone()["remaining"] or 0)
                if remaining != 0:
                    fail(f"DELETED_IDS_STILL_PRESENT={remaining}")

            conn.commit()
            print(f"MOTOR2_CLEANUP_DELETED_ROWS={EXPECTED_ROWS}")
            print("MOTOR2_CLEANUP_RESULT=SUCCESS_COMMITTED")
        except Exception:
            conn.rollback()
            print("MOTOR2_CLEANUP_TRANSACTION=ROLLED_BACK", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
