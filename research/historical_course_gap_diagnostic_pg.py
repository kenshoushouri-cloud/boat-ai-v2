# -*- coding: utf-8 -*-
"""Read-only diagnostic for historical applied-term Course proxy gaps."""
from __future__ import annotations

import json
import os
from collections import defaultdict

import psycopg
from psycopg.rows import dict_row

SOURCE = "boatrace_official_k_applied_term_proxy"
START_DATE = "2025-07-01"
END_DATE = "2026-09-30"

SQL = r"""
with races as (
  select race_id,race_date,
         case
           when race_date between date '2025-07-01' and date '2025-12-31' then date '2025-04-30'
           when race_date between date '2026-01-01' and date '2026-06-30' then date '2025-10-31'
           when race_date between date '2026-07-01' and date '2026-09-30' then date '2026-04-30'
         end as snapshot_date,
         case
           when race_date between date '2025-07-01' and date '2025-12-31' then '2025H2'
           when race_date between date '2026-01-01' and date '2026-06-30' then '2026H1'
           when race_date between date '2026-07-01' and date '2026-09-30' then '2026H2'
         end as term
    from v2_races
   where race_date between %s and %s
),
proxy_any as (
  select racer_number,snapshot_date,
         count(*) filter(where top3_rate between 0 and 100) as valid_rows
    from v2_racer_course_stats_snapshots
   where source=%s
     and snapshot_date in (date '2025-04-30',date '2025-10-31',date '2026-04-30')
   group by racer_number,snapshot_date
),
entry_status as (
  select r.race_id,r.race_date,r.term,r.snapshot_date,e.lane,e.racer_number,
         coalesce((x.top3_rate between 0 and 100),false) as exact_ok,
         coalesce(a.valid_rows,0) as racer_proxy_rows
    from races r
    join v2_race_entries e on e.race_id=r.race_id and e.lane between 1 and 6
    left join v2_racer_course_stats_snapshots x
      on x.racer_number=e.racer_number
     and x.snapshot_date=r.snapshot_date
     and x.course=e.lane
     and x.source=%s
    left join proxy_any a
      on a.racer_number=e.racer_number
     and a.snapshot_date=r.snapshot_date
),
race_status as (
  select race_id,race_date,term,
         count(*) as entry_rows,
         count(*) filter(where exact_ok) as exact_ok_entries,
         count(*) filter(where not exact_ok) as missing_entries,
         count(*) filter(where not exact_ok and racer_number is null) as missing_racer_number_entries,
         count(*) filter(where not exact_ok and racer_number is not null and racer_proxy_rows>0) as zero_target_course_prior_entries,
         count(*) filter(where not exact_ok and racer_number is not null and racer_proxy_rows=0) as no_term_racer_proxy_entries
    from entry_status
   group by race_id,race_date,term
)
select * from race_status
order by race_date,race_id
"""


def _summarize(rows):
    def fresh():
        return {
            "races": 0,
            "course_ready": 0,
            "course_gap": 0,
            "missing_entries": 0,
            "zero_target_course_prior_entries": 0,
            "no_term_racer_proxy_entries": 0,
            "missing_racer_number_entries": 0,
            "gap_races_zero_target_course": 0,
            "gap_races_no_term_racer": 0,
            "gap_races_missing_racer_number": 0,
        }

    totals = fresh()
    by_term = defaultdict(fresh)
    by_month = defaultdict(fresh)

    for row in rows:
        month = str(row["race_date"])[:7]
        groups = (totals, by_term[str(row["term"])], by_month[month])
        ready = int(row["entry_rows"]) == 6 and int(row["exact_ok_entries"]) == 6
        for g in groups:
            g["races"] += 1
            g["course_ready"] += int(ready)
            g["course_gap"] += int(not ready)
            g["missing_entries"] += int(row["missing_entries"])
            g["zero_target_course_prior_entries"] += int(row["zero_target_course_prior_entries"])
            g["no_term_racer_proxy_entries"] += int(row["no_term_racer_proxy_entries"])
            g["missing_racer_number_entries"] += int(row["missing_racer_number_entries"])
            g["gap_races_zero_target_course"] += int(int(row["zero_target_course_prior_entries"]) > 0)
            g["gap_races_no_term_racer"] += int(int(row["no_term_racer_proxy_entries"]) > 0)
            g["gap_races_missing_racer_number"] += int(int(row["missing_racer_number_entries"]) > 0)

    for g in [totals, *by_term.values(), *by_month.values()]:
        g["course_ready_pct"] = round(100.0 * g["course_ready"] / max(1, g["races"]), 2)

    return totals, dict(by_term), dict(by_month)


def audit():
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute(SQL, (START_DATE, END_DATE, SOURCE, SOURCE))
            rows = [dict(x) for x in cur.fetchall()]
            cur.execute(
                """
                select snapshot_date,
                       count(*) as rows,
                       count(distinct racer_number) as racers,
                       count(*) filter(where top3_rate between 0 and 100) as valid_rows
                  from v2_racer_course_stats_snapshots
                 where source=%s
                   and snapshot_date in (date '2025-04-30',date '2025-10-31',date '2026-04-30')
                 group by snapshot_date
                 order by snapshot_date
                """,
                (SOURCE,),
            )
            inventory = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    totals, by_term, by_month = _summarize(rows)
    return {
        "contract": "HISTORICAL_COURSE_GAP_DIAGNOSTIC_V1",
        "period": [START_DATE, END_DATE],
        "source": SOURCE,
        "inventory": inventory,
        "totals": totals,
        "terms": by_term,
        "months": by_month,
        "interpretation": {
            "zero_target_course_prior_entries": (
                "racer has same-term proxy data but no exact target-course row; "
                "the frozen seed emits rows only for courses with >=1 prior start, "
                "so this is not fillable without changing the proxy contract"
            ),
            "no_term_racer_proxy_entries": (
                "racer has no same-term proxy row; source recheck is required before "
                "calling this safely fillable"
            ),
            "missing_racer_number_entries": (
                "target entry itself lacks racer_number; Course proxy cannot be joined"
            ),
        },
        "safety": {
            "transaction_read_only": True,
            "outcome_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "production_change": False,
        },
    }


def main():
    payload = audit()
    print("COURSE_GAP_INVENTORY=" + json.dumps(payload["inventory"], default=str, sort_keys=True))
    for term, row in sorted(payload["terms"].items()):
        print("COURSE_GAP_TERM=" + json.dumps({"term": term, **row}, sort_keys=True))
    print("COURSE_GAP_TOTALS=" + json.dumps(payload["totals"], sort_keys=True))
    print("COURSE_GAP_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
