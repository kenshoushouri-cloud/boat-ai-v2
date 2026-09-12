# -*- coding: utf-8 -*-
"""Read-only preflight for timing-safe value research.

Checks whether frozen Racer Course Forward races have a complete 120-ticket
realtime odds snapshot at or before the race decision deadline. The script emits
aggregate coverage only; it does not persist ticket rows and performs no database
mutation.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

START_DATE = date.fromisoformat(os.getenv("VALUE_PREFLIGHT_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_PREFLIGHT_END", "2026-09-12"))
OUTPUT = Path(os.getenv("VALUE_PREFLIGHT_OUTPUT", "value-timing-safe-odds-preflight.json"))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def table_columns(conn: psycopg.Connection[Any], table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
              from information_schema.columns
             where table_schema='public' and table_name=%s
            """,
            (table,),
        )
        return {str(r["column_name"]) for r in cur.fetchall()}


def count_forward(conn: psycopg.Connection[Any]) -> tuple[int, list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id, min(race_date) as race_date, min(deadline_at) as deadline_at
              from v2_racer_course_top3_forward_shadow
             where race_date between %s and %s
               and deadline_at is not null
             group by race_id
             order by race_id
            """,
            (START_DATE, END_DATE),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return len(rows), rows


def any_predeadline_count(conn: psycopg.Connection[Any]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            with c as (
              select race_id, min(deadline_at) as deadline_at
                from v2_racer_course_top3_forward_shadow
               where race_date between %s and %s
                 and deadline_at is not null
               group by race_id
            )
            select count(distinct c.race_id)::bigint as n
              from c
              join v2_realtime_odds_snapshots o on o.race_id=c.race_id
             where o.snapshot_at <= c.deadline_at
            """,
            (START_DATE, END_DATE),
        )
        return int(cur.fetchone()["n"] or 0)


def latest_complete_snapshots(
    conn: psycopg.Connection[Any], odds_columns: set[str]
) -> list[dict[str, Any]]:
    label_expr = "coalesce(o.snapshot_label,'')" if "snapshot_label" in odds_columns else "''"
    query = f"""
        with c as (
          select race_id, min(race_date) as race_date, min(deadline_at) as deadline_at
            from v2_racer_course_top3_forward_shadow
           where race_date between %s and %s
             and deadline_at is not null
           group by race_id
        ), grouped as (
          select c.race_id,c.race_date,c.deadline_at,o.snapshot_at,
                 {label_expr} as snapshot_label,
                 count(*)::bigint as row_count,
                 count(distinct o.ticket)::bigint as ticket_count,
                 count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count
            from c
            join v2_realtime_odds_snapshots o on o.race_id=c.race_id
           where o.snapshot_at <= c.deadline_at
           group by c.race_id,c.race_date,c.deadline_at,o.snapshot_at,{label_expr}
        ), valid as (
          select *
            from grouped
           where row_count=120
             and ticket_count=120
             and positive_odds_count=120
        )
        select distinct on (race_id)
               race_id,race_date,deadline_at,snapshot_at,snapshot_label,
               row_count,ticket_count,positive_odds_count
          from valid
         order by race_id,snapshot_at desc,snapshot_label
    """
    with conn.cursor() as cur:
        cur.execute(query, (START_DATE, END_DATE))
        return [dict(r) for r in cur.fetchall()]


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_TIMING_ODDS_PREFLIGHT_MODE=read_only", flush=True)
    print(f"VALUE_TIMING_ODDS_PREFLIGHT_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_TIMING_ODDS_PREFLIGHT_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local idle_in_transaction_session_timeout='30s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")

        odds_columns = table_columns(conn, "v2_realtime_odds_snapshots")
        course_columns = table_columns(conn, "v2_racer_course_top3_forward_shadow")
        required_odds = {"race_id", "ticket", "odds", "snapshot_at"}
        required_course = {"race_id", "race_date", "deadline_at"}
        missing_odds = sorted(required_odds - odds_columns)
        missing_course = sorted(required_course - course_columns)
        if missing_odds or missing_course:
            raise RuntimeError(
                f"required columns missing odds={missing_odds} course={missing_course}"
            )

        forward_count, forward_rows = count_forward(conn)
        any_count = any_predeadline_count(conn)
        complete_rows = latest_complete_snapshots(conn, odds_columns)
        conn.rollback()

    minutes: list[float] = []
    labels: Counter[str] = Counter()
    complete_by_date: Counter[str] = Counter()
    for row in complete_rows:
        deadline = row.get("deadline_at")
        snapshot = row.get("snapshot_at")
        if isinstance(deadline, datetime) and isinstance(snapshot, datetime):
            minutes.append((deadline - snapshot).total_seconds() / 60.0)
        labels[str(row.get("snapshot_label") or "<none>")] += 1
        complete_by_date[str(row.get("race_date"))] += 1

    forward_by_date: Counter[str] = Counter(str(r.get("race_date")) for r in forward_rows)
    complete_count = len(complete_rows)
    coverage_pct = (complete_count / forward_count * 100.0) if forward_count else 0.0
    any_pct = (any_count / forward_count * 100.0) if forward_count else 0.0

    summary = {
        "contract": "value_timing_safe_odds_preflight_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "schema": {
            "odds_required_columns_present": not missing_odds,
            "course_required_columns_present": not missing_course,
            "snapshot_label_present": "snapshot_label" in odds_columns,
            "odds_columns": sorted(odds_columns),
        },
        "coverage": {
            "forward_races": forward_count,
            "races_with_any_predeadline_odds": any_count,
            "races_with_complete_120_predeadline_snapshot": complete_count,
            "any_predeadline_pct": round(any_pct, 4),
            "complete_120_pct": round(coverage_pct, 4),
            "forward_by_date": dict(sorted(forward_by_date.items())),
            "complete_by_date": dict(sorted(complete_by_date.items())),
            "complete_snapshot_labels": dict(sorted(labels.items())),
        },
        "minutes_snapshot_to_deadline": {
            "n": len(minutes),
            "min": min(minutes) if minutes else None,
            "p25": percentile(minutes, 0.25),
            "median": percentile(minutes, 0.50),
            "p75": percentile(minutes, 0.75),
            "p95": percentile(minutes, 0.95),
            "max": max(minutes) if minutes else None,
        },
        "formal_export_preflight": (
            "READY_PARTIAL_TIMING_SAFE_SAMPLE" if complete_count > 0 else "FAIL_NO_COMPLETE_PREDEADLINE_120"
        ),
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"VALUE_TIMING_ODDS_FORWARD_RACES={forward_count}", flush=True)
    print(f"VALUE_TIMING_ODDS_ANY_PREDEADLINE_RACES={any_count}", flush=True)
    print(f"VALUE_TIMING_ODDS_COMPLETE_120_RACES={complete_count}", flush=True)
    print(f"VALUE_TIMING_ODDS_COMPLETE_120_PCT={coverage_pct:.4f}", flush=True)
    print(f"VALUE_TIMING_ODDS_LABELS={json.dumps(dict(sorted(labels.items())), sort_keys=True)}", flush=True)
    print(f"VALUE_TIMING_ODDS_MINUTES={json.dumps(summary['minutes_snapshot_to_deadline'], sort_keys=True)}", flush=True)
    print(f"VALUE_TIMING_ODDS_FORMAL_EXPORT_PREFLIGHT={summary['formal_export_preflight']}", flush=True)
    print("VALUE_TIMING_ODDS_PREFLIGHT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"VALUE_TIMING_ODDS_PREFLIGHT_ERROR={type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:700]}",
            flush=True,
        )
        raise
