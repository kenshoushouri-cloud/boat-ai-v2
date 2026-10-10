# -*- coding: utf-8 -*-
"""Read-only preflight for timing-safe value research.

Checks whether frozen Racer Course Forward races have a coherent complete
120-ticket realtime-odds label whose every ticket row was captured at or before
the decision deadline. In the current collector, ``snapshot_at`` is assigned per
ticket while the stable snapshot identity is ``snapshot_label``; therefore a
coherent snapshot is validated by label, ticket completeness, deadline safety,
and a bounded timestamp spread rather than timestamp equality.

The script emits aggregate coverage only. It does not persist ticket rows and
performs no database mutation.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

START_DATE = date.fromisoformat(os.getenv("VALUE_PREFLIGHT_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_PREFLIGHT_END", "2026-09-12"))
MAX_LABEL_SPREAD_SECONDS = float(os.getenv("VALUE_PREFLIGHT_MAX_LABEL_SPREAD_SECONDS", "60"))
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


def complete_label_diagnostics(conn: psycopg.Connection[Any]) -> dict[str, int]:
    """Count progressively stricter label-level completeness gates."""
    with conn.cursor() as cur:
        cur.execute(
            """
            with c as (
              select race_id, min(deadline_at) as deadline_at
                from v2_racer_course_top3_forward_shadow
               where race_date between %s and %s
                 and deadline_at is not null
               group by race_id
            ), g as (
              select c.race_id,c.deadline_at,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from c
                join v2_realtime_odds_snapshots o on o.race_id=c.race_id
               where o.snapshot_label is not null
               group by c.race_id,c.deadline_at,o.snapshot_label
            )
            select
              count(distinct race_id) filter (
                where row_count=120 and ticket_count=120 and positive_odds_count=120
              )::bigint as complete_any_time,
              count(distinct race_id) filter (
                where row_count=120 and ticket_count=120 and positive_odds_count=120
                  and last_snapshot_at <= deadline_at
              )::bigint as complete_all_predeadline,
              count(distinct race_id) filter (
                where row_count=120 and ticket_count=120 and positive_odds_count=120
                  and last_snapshot_at <= deadline_at
                  and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
              )::bigint as complete_predeadline_coherent
            from g
            """,
            (START_DATE, END_DATE, MAX_LABEL_SPREAD_SECONDS),
        )
        row = cur.fetchone()
        return {
            "complete_any_time": int(row["complete_any_time"] or 0),
            "complete_all_predeadline": int(row["complete_all_predeadline"] or 0),
            "complete_predeadline_coherent": int(row["complete_predeadline_coherent"] or 0),
        }


def latest_complete_labels(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    """Latest coherent 120-ticket label fully captured before each deadline."""
    with conn.cursor() as cur:
        cur.execute(
            """
            with c as (
              select race_id, min(race_date) as race_date, min(deadline_at) as deadline_at
                from v2_racer_course_top3_forward_shadow
               where race_date between %s and %s
                 and deadline_at is not null
               group by race_id
            ), grouped as (
              select c.race_id,c.race_date,c.deadline_at,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from c
                join v2_realtime_odds_snapshots o on o.race_id=c.race_id
               where o.snapshot_label is not null
               group by c.race_id,c.race_date,c.deadline_at,o.snapshot_label
            ), valid as (
              select *, extract(epoch from (last_snapshot_at-first_snapshot_at)) as spread_seconds
                from grouped
               where row_count=120
                 and ticket_count=120
                 and positive_odds_count=120
                 and last_snapshot_at <= deadline_at
                 and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
            )
            select distinct on (race_id)
                   race_id,race_date,deadline_at,snapshot_label,
                   first_snapshot_at,last_snapshot_at,spread_seconds,
                   row_count,ticket_count,positive_odds_count
              from valid
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (START_DATE, END_DATE, MAX_LABEL_SPREAD_SECONDS),
        )
        return [dict(r) for r in cur.fetchall()]


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_TIMING_ODDS_PREFLIGHT_MODE=read_only", flush=True)
    print(f"VALUE_TIMING_ODDS_PREFLIGHT_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(f"VALUE_TIMING_ODDS_PREFLIGHT_MAX_LABEL_SPREAD_SECONDS={MAX_LABEL_SPREAD_SECONDS:g}", flush=True)
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
        required_odds = {"race_id", "ticket", "odds", "snapshot_at", "snapshot_label"}
        required_course = {"race_id", "race_date", "deadline_at"}
        missing_odds = sorted(required_odds - odds_columns)
        missing_course = sorted(required_course - course_columns)
        if missing_odds or missing_course:
            raise RuntimeError(
                f"required columns missing odds={missing_odds} course={missing_course}"
            )

        forward_count, forward_rows = count_forward(conn)
        any_count = any_predeadline_count(conn)
        diagnostics = complete_label_diagnostics(conn)
        complete_rows = latest_complete_labels(conn)
        conn.rollback()

    minutes: list[float] = []
    spreads: list[float] = []
    labels: Counter[str] = Counter()
    complete_by_date: Counter[str] = Counter()
    for row in complete_rows:
        deadline = row.get("deadline_at")
        last_snapshot = row.get("last_snapshot_at")
        if isinstance(deadline, datetime) and isinstance(last_snapshot, datetime):
            minutes.append((deadline - last_snapshot).total_seconds() / 60.0)
        spreads.append(float(row.get("spread_seconds") or 0.0))
        labels[str(row.get("snapshot_label") or "<none>")] += 1
        complete_by_date[str(row.get("race_date"))] += 1

    forward_by_date: Counter[str] = Counter(str(r.get("race_date")) for r in forward_rows)
    complete_count = len(complete_rows)
    coverage_pct = (complete_count / forward_count * 100.0) if forward_count else 0.0
    any_pct = (any_count / forward_count * 100.0) if forward_count else 0.0

    summary = {
        "contract": "value_timing_safe_odds_preflight_v2_label_coherent",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "coherence": {"max_label_spread_seconds": MAX_LABEL_SPREAD_SECONDS},
        "schema": {
            "odds_required_columns_present": not missing_odds,
            "course_required_columns_present": not missing_course,
            "odds_columns": sorted(odds_columns),
        },
        "coverage": {
            "forward_races": forward_count,
            "races_with_any_predeadline_odds": any_count,
            "races_with_complete_120_predeadline_coherent_label": complete_count,
            "any_predeadline_pct": round(any_pct, 4),
            "complete_120_pct": round(coverage_pct, 4),
            "label_gate_diagnostics": diagnostics,
            "forward_by_date": dict(sorted(forward_by_date.items())),
            "complete_by_date": dict(sorted(complete_by_date.items())),
            "complete_snapshot_labels": dict(sorted(labels.items())),
        },
        "minutes_last_ticket_to_deadline": {
            "n": len(minutes),
            "min": min(minutes) if minutes else None,
            "p25": percentile(minutes, 0.25),
            "median": percentile(minutes, 0.50),
            "p75": percentile(minutes, 0.75),
            "p95": percentile(minutes, 0.95),
            "max": max(minutes) if minutes else None,
        },
        "label_spread_seconds": {
            "n": len(spreads),
            "min": min(spreads) if spreads else None,
            "median": percentile(spreads, 0.50),
            "p95": percentile(spreads, 0.95),
            "max": max(spreads) if spreads else None,
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
    print(f"VALUE_TIMING_ODDS_LABEL_GATE_DIAGNOSTICS={json.dumps(diagnostics, sort_keys=True)}", flush=True)
    print(f"VALUE_TIMING_ODDS_COMPLETE_120_RACES={complete_count}", flush=True)
    print(f"VALUE_TIMING_ODDS_COMPLETE_120_PCT={coverage_pct:.4f}", flush=True)
    print(f"VALUE_TIMING_ODDS_LABELS={json.dumps(dict(sorted(labels.items())), sort_keys=True)}", flush=True)
    print(f"VALUE_TIMING_ODDS_MINUTES={json.dumps(summary['minutes_last_ticket_to_deadline'], sort_keys=True)}", flush=True)
    print(f"VALUE_TIMING_ODDS_LABEL_SPREAD={json.dumps(summary['label_spread_seconds'], sort_keys=True)}", flush=True)
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
