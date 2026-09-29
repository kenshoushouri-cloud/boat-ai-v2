# -*- coding: utf-8 -*-
"""Historical point-in-time data inventory (READ ONLY).

Purpose
-------
Measure what can be used or reconstructed for historical research under one
strict rule:

    only information that was knowable before the target race deadline is valid.

This inventory does NOT backfill Production tables and does NOT tune any model.
It only classifies historical inputs into:
- STORED_POINT_IN_TIME: already stored with target-date semantics;
- RECOMPUTABLE_STRICT_PRIOR: can be rebuilt using data strictly before target date;
- CURRENT_ONLY_NOT_BACKFILLABLE: current-state source cannot safely represent history;
- MISSING.

Important
---------
- No INSERT/UPDATE/DELETE/DDL.
- No odds reads.
- No target-race outcome is used as a feature.
- Opponent/recent-form feasibility may inspect historical result coverage only to
  determine whether a strictly-prior reconstruction is possible.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_START = "2025-07-01"
DEFAULT_END = "2026-09-29"


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        """select exists(
             select 1 from information_schema.tables
              where table_schema='public' and table_name=%s
           ) ok""",
        (table,),
    )
    return bool(cur.fetchone()["ok"])


def _columns(cur, table: str) -> set[str]:
    cur.execute(
        """select column_name
             from information_schema.columns
            where table_schema='public' and table_name=%s""",
        (table,),
    )
    return {str(r["column_name"]) for r in cur.fetchall()}


def _month_rows(cur, start: date, end: date) -> list[dict[str, Any]]:
    cur.execute(
        """
        select to_char(race_date,'YYYY-MM') month_key, count(*)::int races
          from v2_races
         where race_date between %s and %s
         group by 1 order by 1
        """,
        (start, end),
    )
    return [dict(r) for r in cur.fetchall()]


def _race_counts(cur, start: date, end: date) -> dict[str, int]:
    cur.execute(
        """
        with e as (
          select e.race_id,
                 count(*) filter(where e.lane between 1 and 6) n,
                 count(*) filter(
                   where e.lane between 1 and 6
                     and e.racer_class between 1 and 4
                     and e.national_win_rate is not null
                     and e.national_place2_rate is not null
                     and e.local_place2_rate is not null
                     and e.avg_st is not null
                 ) base_n
            from v2_race_entries e
            join v2_races r using(race_id)
           where r.race_date between %s and %s
           group by e.race_id
        )
        select
          count(*)::int races,
          count(*) filter(where n=6)::int full6_entries,
          count(*) filter(where base_n=6)::int base_full6
        from e
        """,
        (start, end),
    )
    return dict(cur.fetchone() or {})


def _f_count(cur, start: date, end: date, entry_cols: set[str]) -> dict[str, Any]:
    if "f_count" not in entry_cols:
        return {
            "status": "MISSING",
            "reason": "v2_race_entries.f_count column absent",
            "rows_nonnull": 0,
            "full6_races": 0,
        }
    cur.execute(
        """
        with x as (
          select e.race_id,
                 count(*) filter(where e.lane between 1 and 6 and e.f_count is not null) n
            from v2_race_entries e
            join v2_races r using(race_id)
           where r.race_date between %s and %s
           group by e.race_id
        )
        select
          (select count(*)::int
             from v2_race_entries e join v2_races r using(race_id)
            where r.race_date between %s and %s and e.f_count is not null) rows_nonnull,
          count(*) filter(where n=6)::int full6_races
        from x
        """,
        (start, end, start, end),
    )
    d = dict(cur.fetchone() or {})
    d.update({
        "status": "STORED_POINT_IN_TIME",
        "basis": "race-card entry value stored on target race row",
        "target_outcome_required": False,
    })
    return d


def _recent_form(cur, start: date, end: date, entry_cols: set[str]) -> dict[str, Any]:
    stored = {
        "rows_nonempty": 0,
        "full6_races": 0,
    }
    if "recent_form" in entry_cols:
        cur.execute(
            """
            with x as (
              select e.race_id,
                     count(*) filter(
                       where e.recent_form is not null
                         and btrim(e.recent_form::text) not in ('','[]','{}','null')
                     ) n
                from v2_race_entries e
                join v2_races r using(race_id)
               where r.race_date between %s and %s
               group by e.race_id
            )
            select
              (select count(*)::int
                 from v2_race_entries e join v2_races r using(race_id)
                where r.race_date between %s and %s
                  and e.recent_form is not null
                  and btrim(e.recent_form::text) not in ('','[]','{}','null')
              ) rows_nonempty,
              count(*) filter(where n=6)::int full6_races
            from x
            """,
            (start, end, start, end),
        )
        stored = dict(cur.fetchone() or {})

    # A new point-in-time recent-form dataset can be reconstructed only from
    # finishes strictly before target_date. This is coverage feasibility, not
    # feature definition or model testing.
    can_recompute = False
    if _table_exists(cur, "v2_result_entries") and "racer_number" in entry_cols:
        result_cols = _columns(cur, "v2_result_entries")
        can_recompute = "racer_number" in result_cols and "finish_position" in result_cols

    return {
        **stored,
        "stored_status": "STORED_POINT_IN_TIME" if int(stored.get("full6_races") or 0) > 0 else "MISSING",
        "reconstruction_status": "RECOMPUTABLE_STRICT_PRIOR" if can_recompute else "MISSING",
        "reconstruction_rule": "only races with historical race_date < target race_date",
        "same_day_target_results_allowed": False,
        "target_outcome_required": False,
        "feature_definition_frozen": False,
    }


def _historical_snapshot_coverage(
    cur,
    *,
    table: str,
    start: date,
    end: date,
    require_six: bool,
    value_predicate: str,
) -> dict[str, Any]:
    if not _table_exists(cur, table):
        return {"status": "MISSING", "races": 0, "rows": 0}
    cols = _columns(cur, table)
    needed = {"race_id", "race_date", "snapshot_label"}
    if not needed.issubset(cols):
        return {"status": "MISSING", "races": 0, "rows": 0, "reason": "required columns absent"}

    cur.execute(
        f"""
        with x as (
          select s.race_id, count(*) filter(where {value_predicate}) n
            from {table} s
            join v2_races r using(race_id)
           where r.race_date between %s and %s
             and s.snapshot_label='historical'
           group by s.race_id
        )
        select
          (select count(*)::int
             from {table} s join v2_races r using(race_id)
            where r.race_date between %s and %s and s.snapshot_label='historical') rows,
          count(*) filter(where n >= %s)::int races
        from x
        """,
        (start, end, start, end, 6 if require_six else 1),
    )
    d = dict(cur.fetchone() or {})
    d.update({
        "status": "STORED_POINT_IN_TIME",
        "semantic_basis": "official target-race beforeinfo snapshot_label=historical",
        "capture_timestamp_is_retrieval_time_not_event_time": True,
        "target_outcome_required": False,
    })
    return d


def _course(cur, start: date, end: date, entry_cols: set[str]) -> dict[str, Any]:
    table = "v2_racer_course_stats_snapshots"
    if not _table_exists(cur, table) or "racer_number" not in entry_cols:
        return {
            "status": "CURRENT_ONLY_NOT_BACKFILLABLE",
            "exact_date_full6_races": 0,
            "reason": "current official racer-course page cannot safely stand in for historical values",
        }
    cols = _columns(cur, table)
    required = {"racer_number", "snapshot_date", "course", "top3_rate"}
    if not required.issubset(cols):
        return {
            "status": "CURRENT_ONLY_NOT_BACKFILLABLE",
            "exact_date_full6_races": 0,
            "reason": "exact-date course snapshot schema incomplete",
        }

    timing_clause = ""
    if "created_at" in cols:
        timing_clause = " and (s.created_at is null or s.created_at < r.deadline_at)"
    cur.execute(
        f"""
        with x as (
          select r.race_id,
                 count(*) filter(where s.top3_rate is not null) n
            from v2_races r
            join v2_race_entries e on e.race_id=r.race_id
            left join {table} s
              on s.racer_number=e.racer_number
             and s.snapshot_date=r.race_date
             and s.course=e.lane
             {timing_clause}
           where r.race_date between %s and %s
           group by r.race_id
        )
        select count(*) filter(where n=6)::int exact_date_full6_races
          from x
        """,
        (start, end),
    )
    n = int((cur.fetchone() or {}).get("exact_date_full6_races") or 0)
    return {
        "status": "STORED_POINT_IN_TIME" if n > 0 else "CURRENT_ONLY_NOT_BACKFILLABLE",
        "exact_date_full6_races": n,
        "current_page_backfill_allowed": False,
        "reason": (
            "exact-date stored snapshots may be used; current racer-course page must not be applied backward"
        ),
    }


def _opponent(cur, start: date, end: date, entry_cols: set[str]) -> dict[str, Any]:
    stored = 0
    table = "v2_opponent_pressure_shadow_v2"
    if _table_exists(cur, table):
        cols = _columns(cur, table)
        if {"race_date", "train_end"}.issubset(cols):
            cur.execute(
                f"""
                select count(*)::int n
                  from {table}
                 where race_date between %s and %s
                   and train_end < race_date
                """,
                (start, end),
            )
            stored = int((cur.fetchone() or {}).get("n") or 0)

    # The frozen Opponent Pressure algorithm uses only target card class/lane
    # plus training results with race_date < target date. This is therefore
    # historically recomputable without target outcome leakage.
    can_recompute = (
        {"racer_class", "lane"}.issubset(entry_cols)
        and _table_exists(cur, "v2_result_entries")
    )
    return {
        "stored_strict_prior_rows": stored,
        "stored_status": "STORED_POINT_IN_TIME" if stored > 0 else "MISSING",
        "reconstruction_status": "RECOMPUTABLE_STRICT_PRIOR" if can_recompute else "MISSING",
        "train_cutoff_rule": "training race_date < target race_date",
        "target_outcome_required": False,
        "coefficient_search_allowed": False,
    }


def _monthly_entry_coverage(cur, start: date, end: date, entry_cols: set[str]) -> list[dict[str, Any]]:
    f_expr = (
        "count(*) filter(where e.f_count is not null)"
        if "f_count" in entry_cols else "0::bigint"
    )
    recent_expr = (
        """count(*) filter(
             where e.recent_form is not null
               and btrim(e.recent_form::text) not in ('','[]','{}','null')
           )"""
        if "recent_form" in entry_cols else "0::bigint"
    )
    cur.execute(
        f"""
        select to_char(r.race_date,'YYYY-MM') month_key,
               count(distinct r.race_id)::int races,
               count(*)::int entry_rows,
               {f_expr}::int f_count_rows,
               {recent_expr}::int recent_form_rows
          from v2_races r
          join v2_race_entries e using(race_id)
         where r.race_date between %s and %s
         group by 1 order by 1
        """,
        (start, end),
    )
    return [dict(r) for r in cur.fetchall()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=DEFAULT_START)
    ap.add_argument("--end-date", default=DEFAULT_END)
    args = ap.parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    # Force read-only at connection and transaction level.
    opts = (os.getenv("PGOPTIONS") or "").strip()
    ro = "-c default_transaction_read_only=on"
    if ro not in opts:
        os.environ["PGOPTIONS"] = f"{opts} {ro}".strip()

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            entry_cols = _columns(cur, "v2_race_entries")
            payload = {
                "contract": "HISTORICAL_POINT_IN_TIME_INVENTORY_V1",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "ground_truth_rule": "strictly_available_before_target_race_deadline",
                "target_race_outcome_as_feature_allowed": False,
                "current_value_substitution_allowed": False,
                "database_write": False,
                "odds_read": False,
                "production_change": False,
                "purchase_action": False,
                "race_months": _month_rows(cur, start, end),
                "base_entry_coverage": _race_counts(cur, start, end),
                "f_count": _f_count(cur, start, end, entry_cols),
                "recent_form": _recent_form(cur, start, end, entry_cols),
                "exhibition": _historical_snapshot_coverage(
                    cur,
                    table="v2_realtime_exhibition_snapshots",
                    start=start,
                    end=end,
                    require_six=True,
                    value_predicate="s.exhibition_time is not null or s.start_timing is not null",
                ),
                "weather_water": _historical_snapshot_coverage(
                    cur,
                    table="v2_realtime_weather_snapshots",
                    start=start,
                    end=end,
                    require_six=False,
                    value_predicate=(
                        "s.weather is not null or s.wind_speed_m is not null "
                        "or s.wave_height_cm is not null or s.temperature_c is not null "
                        "or s.water_temperature_c is not null"
                    ),
                ),
                "course": _course(cur, start, end, entry_cols),
                "opponent": _opponent(cur, start, end, entry_cols),
                "monthly_entry_coverage": _monthly_entry_coverage(cur, start, end, entry_cols),
            }
        conn.rollback()

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
