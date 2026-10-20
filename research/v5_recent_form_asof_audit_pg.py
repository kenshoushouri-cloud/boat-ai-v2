# -*- coding: utf-8 -*-
"""Read-only one-day V5 recent-form as-of coverage audit on local ConoHa DB.

This is NOT a historical pre-deadline source certificate or a forward
prediction. Never writes recent_form to v2_race_entries, never alters model,
odds, bets, subscriptions, or notifications. Requires local PostgreSQL socket.

Example (Termius on ConoHa):
 sudo -u postgres env DATABASE_URL=postgresql:///railway \
   /opt/boat-ai-v5-venv/bin/python -m research.v5_recent_form_asof_audit_pg \
   --date 2026-10-20
"""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime, time, timedelta, timezone

JST = timezone(timedelta(hours=9))

# One bounded query, restricted to the target day's racers. Excludes same-day
# K results and K records ingested at/after the start of the target day.
# Five rows are ordered by true race chronology, not fetch time.
COVERAGE_SQL = """
WITH target AS MATERIALIZED (
  SELECT e.race_id, e.lane, e.racer_number, e.recent_form
  FROM public.v2_race_entries e
  JOIN public.v2_races r ON r.race_id = e.race_id
  WHERE r.race_date = %s::date AND e.racer_number IS NOT NULL
),
racers AS MATERIALIZED (
  SELECT DISTINCT racer_number FROM target
),
prior_k AS (
  SELECT h.racer_number, h.race_id,
         ROW_NUMBER() OVER (
           PARTITION BY h.racer_number
           ORDER BY r.race_date DESC,
                    r.deadline_at DESC NULLS LAST,
                    r.race_no DESC,
                    h.race_id DESC,
                    h.lane DESC
         ) AS history_rank
  FROM public.v2_result_entries h
  JOIN racers t ON t.racer_number = h.racer_number
  JOIN public.v2_races r ON r.race_id = h.race_id
  WHERE r.race_date >= DATE '2025-07-01'
    AND r.race_date < %s::date
    AND h.source = 'official_k_file'
    AND h.fetched_at IS NOT NULL
    AND h.fetched_at < %s::timestamptz
    AND h.finish_position BETWEEN 1 AND 6
    AND h.is_flying IS NOT TRUE
    AND h.is_late IS NOT TRUE
),
five AS (
  SELECT racer_number, COUNT(*) AS n
  FROM prior_k WHERE history_rank <= 5
  GROUP BY racer_number
)
SELECT
  COUNT(*)::integer AS target_entries,
  COUNT(DISTINCT e.racer_number)::integer AS target_racers,
  COUNT(*) FILTER (
    WHERE e.recent_form IS NULL OR e.recent_form = '[]'::jsonb
  )::integer AS empty_entries,
  COUNT(*) FILTER (
    WHERE COALESCE(f.n,0) >= 5
  )::integer AS entries_with_asof5,
  COUNT(*) FILTER (
    WHERE COALESCE(f.n,0) < 5
  )::integer AS entries_under_asof5,
  COUNT(DISTINCT e.racer_number) FILTER (
    WHERE COALESCE(f.n,0) >= 5
  )::integer AS racers_with_asof5,
  COUNT(*) FILTER (
    WHERE (e.recent_form IS NULL OR e.recent_form = '[]'::jsonb)
      AND COALESCE(f.n,0) >= 5
  )::integer AS missing_entries_reconstructable
FROM target e LEFT JOIN five f ON f.racer_number = e.racer_number
"""


def checked_date(value: str) -> date:
    day = date.fromisoformat(value)
    if not date(2025, 7, 1) <= day <= datetime.now(JST).date():
        raise ValueError("target date outside supported historical range")
    return day


def local_connection_url(value: str) -> str:
    from psycopg.conninfo import conninfo_to_dict
    if not value:
        raise ValueError("DATABASE_URL is required")
    cfg = conninfo_to_dict(value)
    if cfg.get("dbname") != "railway":
        raise ValueError("local railway database required")
    if cfg.get("host") not in (None, "", "/var/run/postgresql"):
        raise ValueError("only local PostgreSQL Unix socket is allowed")
    if cfg.get("hostaddr"):
        raise ValueError("remote PostgreSQL is prohibited")
    return value


def summary_text(row: dict[str, int], day: date) -> str:
    names = (
        "target_entries", "target_racers", "empty_entries",
        "entries_with_asof5", "entries_under_asof5",
        "racers_with_asof5", "missing_entries_reconstructable",
    )
    return "\n".join(
        [f"V5_RECENT_FORM_ASOF_DATE={day.isoformat()}",
         "V5_RECENT_FORM_DB_WRITE=0",
         "V5_RECENT_FORM_FORWARD_ELIGIBLE=0",
         "V5_RECENT_FORM_HISTORY=official_k_file_before_midnight_only"]
        + [f"{name.upper()}={row[name]}" for name in names]
        + ["V5_RECENT_FORM_ASOF_AUDIT_DONE"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD in JST")
    args = parser.parse_args(argv)
    try:
        day = checked_date(args.date)
        url = local_connection_url(os.getenv("DATABASE_URL", ""))
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    import psycopg
    from psycopg.rows import dict_row
    midnight = datetime.combine(day, time.min, tzinfo=JST)
    # Explicit database read-only transaction even if inherited env contains
    # backfill opt-in flags. Time and memory are bounded for the 2GB VM.
    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '20s'")
            cur.execute("SET LOCAL work_mem = '16MB'")
            cur.execute(COVERAGE_SQL, (day, day, midnight))
            result = cur.fetchone()
        conn.rollback()
    print(summary_text(dict(result), day))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
