# -*- coding: utf-8 -*-
"""Read-only audit of the 2026-09-11 Racer Course natural Cron result.

This script is intentionally audit-only. It reads race entries and the official
racer-by-course snapshot table, and never reads outcomes, odds, predictions,
LINE state, coefficients, or thresholds. It performs no writes.
"""
from __future__ import annotations

import os
from datetime import date

import psycopg
from psycopg.rows import dict_row

DB = (os.getenv("DATABASE_URL") or "").strip()
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE", "2026-09-11"))


def _pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")

    print("RACER_COURSE_NATURAL_AUDIT_MODE=read_only_no_results_no_odds_no_predictions", flush=True)
    print("RACER_COURSE_NATURAL_AUDIT_POLICY=no_writes_no_production_no_line_no_coefficients", flush=True)
    print(f"RACER_COURSE_NATURAL_AUDIT_DATE={TARGET_DATE}", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='120s'")

            cur.execute(
                """
                with target_entries as (
                  select e.racer_number
                    from v2_race_entries e
                    join v2_races r on r.race_id=e.race_id
                   where r.race_date=%s and e.racer_number is not null
                ),
                target_racers as (
                  select distinct racer_number from target_entries
                ),
                snap as (
                  select s.*
                    from v2_racer_course_stats_snapshots s
                    join target_racers t on t.racer_number=s.racer_number
                   where s.snapshot_date=%s
                ),
                per_racer as (
                  select t.racer_number,
                         count(s.course) saved_rows,
                         bool_or(
                           s.course is not null and
                           (s.entry_rate is null or s.top3_rate is null or s.avg_st is null)
                         ) has_partial_metric
                    from target_racers t
                    left join snap s on s.racer_number=t.racer_number
                   group by t.racer_number
                )
                select count(*) target_racers,
                       count(*) filter(where saved_rows > 0) db_success_racers,
                       count(*) filter(where saved_rows > 0 and (saved_rows <> 6 or has_partial_metric)) db_partial_racers,
                       count(*) filter(where saved_rows = 0) db_failed_racers,
                       coalesce(sum(saved_rows),0) saved_rows
                  from per_racer
                """,
                (TARGET_DATE, TARGET_DATE),
            )
            racer = dict(cur.fetchone() or {})

            cur.execute(
                """
                select count(*) rows,
                       count(distinct racer_number) racers,
                       min(created_at) min_created_at,
                       max(created_at) max_created_at,
                       count(*) filter(where top3_rate is not null) top3_rows,
                       count(*) filter(where entry_rate is not null) entry_rate_rows,
                       count(*) filter(where avg_st is not null) avg_st_rows,
                       count(*) filter(where entry_rate is null or top3_rate is null or avg_st is null) partial_rows,
                       count(*) filter(where entry_rate is not null and top3_rate is not null and avg_st is not null) all3_rows,
                       count(*) filter(where source='boatrace_official_racer_course') official_source_rows
                  from v2_racer_course_stats_snapshots
                 where snapshot_date=%s
                """,
                (TARGET_DATE,),
            )
            snap = dict(cur.fetchone() or {})

            cur.execute(
                """
                with races as (
                  select race_id, deadline_at
                    from v2_races
                   where race_date=%s
                ),
                matched as (
                  select r.race_id,r.deadline_at,e.lane,e.racer_number,
                         s.entry_rate,s.top3_rate,s.avg_st,s.created_at
                    from races r
                    left join v2_race_entries e on e.race_id=r.race_id
                    left join v2_racer_course_stats_snapshots s
                      on s.snapshot_date=%s
                     and s.racer_number=e.racer_number
                     and s.course=e.lane
                ),
                per_race as (
                  select race_id,
                         count(*) filter(where lane between 1 and 6 and racer_number is not null) entry_rows,
                         count(distinct lane) filter(where lane between 1 and 6 and racer_number is not null) lanes,
                         count(*) filter(where top3_rate between 0 and 100) top3_rows,
                         count(*) filter(
                           where top3_rate between 0 and 100
                             and created_at is not null
                             and deadline_at is not null
                             and created_at < deadline_at
                             and (created_at at time zone 'Asia/Tokyo')::time <= time '08:15:00'
                         ) top3_safe_rows,
                         count(*) filter(
                           where entry_rate between 0 and 100
                             and top3_rate between 0 and 100
                             and avg_st between 0 and 1
                         ) all3_rows,
                         count(*) filter(
                           where entry_rate between 0 and 100
                             and top3_rate between 0 and 100
                             and avg_st between 0 and 1
                             and created_at is not null
                             and deadline_at is not null
                             and created_at < deadline_at
                             and (created_at at time zone 'Asia/Tokyo')::time <= time '08:15:00'
                         ) all3_safe_rows
                    from matched
                   group by race_id
                )
                select count(*) target_races,
                       count(*) filter(where entry_rows=6 and lanes=6) full6_entry_races,
                       count(*) filter(where entry_rows=6 and lanes=6 and top3_rows=6) full6_top3_raw,
                       count(*) filter(where entry_rows=6 and lanes=6 and top3_safe_rows=6) full6_top3_timing_safe,
                       count(*) filter(where entry_rows=6 and lanes=6 and all3_rows=6) old_all3_raw,
                       count(*) filter(where entry_rows=6 and lanes=6 and all3_safe_rows=6) old_all3_timing_safe,
                       count(*) filter(
                         where entry_rows=6 and lanes=6 and top3_safe_rows=6 and all3_safe_rows<6
                       ) partial_rescued_timing_safe,
                       count(*) filter(
                         where entry_rows=6 and lanes=6 and top3_safe_rows<6
                       ) fail_closed_timing_safe
                  from per_race
                """,
                (TARGET_DATE, TARGET_DATE),
            )
            race = dict(cur.fetchone() or {})

    target_racers = int(racer.get("target_racers") or 0)
    success = int(racer.get("db_success_racers") or 0)
    partial = int(racer.get("db_partial_racers") or 0)
    failed = int(racer.get("db_failed_racers") or 0)
    saved = int(racer.get("saved_rows") or 0)
    print(
        "RACER_COURSE_NATURAL_AUDIT_RACERS="
        f"target:{target_racers} db_success:{success} db_partial:{partial} "
        f"db_failed:{failed} saved_rows:{saved} db_coverage_pct:{_pct(success,target_racers):.2f}",
        flush=True,
    )
    print(
        "RACER_COURSE_NATURAL_AUDIT_SNAPSHOTS="
        f"rows:{int(snap.get('rows') or 0)} racers:{int(snap.get('racers') or 0)} "
        f"top3_rows:{int(snap.get('top3_rows') or 0)} entry_rate_rows:{int(snap.get('entry_rate_rows') or 0)} "
        f"avg_st_rows:{int(snap.get('avg_st_rows') or 0)} partial_rows:{int(snap.get('partial_rows') or 0)} "
        f"all3_rows:{int(snap.get('all3_rows') or 0)} official_source_rows:{int(snap.get('official_source_rows') or 0)}",
        flush=True,
    )
    print(
        "RACER_COURSE_NATURAL_AUDIT_CREATED="
        f"min:{snap.get('min_created_at')} max:{snap.get('max_created_at')}",
        flush=True,
    )

    target_races = int(race.get("target_races") or 0)
    full6_entries = int(race.get("full6_entry_races") or 0)
    top3_raw = int(race.get("full6_top3_raw") or 0)
    top3_safe = int(race.get("full6_top3_timing_safe") or 0)
    old_raw = int(race.get("old_all3_raw") or 0)
    old_safe = int(race.get("old_all3_timing_safe") or 0)
    rescued = int(race.get("partial_rescued_timing_safe") or 0)
    fail_closed = int(race.get("fail_closed_timing_safe") or 0)
    print(
        "RACER_COURSE_NATURAL_AUDIT_RACES="
        f"target:{target_races} full6_entries:{full6_entries} full6_top3_raw:{top3_raw} "
        f"full6_top3_timing_safe:{top3_safe} old_all3_raw:{old_raw} "
        f"old_all3_timing_safe:{old_safe} partial_rescued_timing_safe:{rescued} "
        f"fail_closed_timing_safe:{fail_closed}",
        flush=True,
    )
    print(
        "RACER_COURSE_NATURAL_AUDIT_COVERAGE="
        f"top3_safe_pct_of_full6:{_pct(top3_safe,full6_entries):.2f} "
        f"old_all3_safe_pct_of_full6:{_pct(old_safe,full6_entries):.2f} "
        f"gain_points:{_pct(top3_safe,full6_entries)-_pct(old_safe,full6_entries):+.2f}",
        flush=True,
    )
    print("RACER_COURSE_NATURAL_AUDIT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
