#!/usr/bin/env python3
"""2026-10-26 six-family realtime source-vs-stage audit, strictly read-only.

Report date-scoped counts and claimed predeadline snapshot timestamps.
Counts/time labels alone are NOT proof of actual predeadline capture.
No source/stage writes; no collector, timer, BUY or migration.
"""
from __future__ import annotations

import os
import sys
import psycopg
from psycopg import sql

PAIRS = (
    ("v2_realtime_entry_snapshots", "entry_snapshots"),
    ("v2_realtime_exhibition_snapshots", "exhibition_snapshots"),
    ("v2_realtime_odds_snapshots", "odds_snapshots"),
    ("v2_realtime_weather_snapshots", "weather_snapshots"),
    ("v2_realtime_race_condition_snapshots", "race_condition_snapshots"),
    ("v2_realtime_racer_condition_snapshots", "racer_condition_snapshots"),
)
LOW, HIGH = "20261026_", "20261027_"

def inspect(cur, schema, table):
    fullname = f"{schema}.{table}"
    cur.execute("SELECT c.relkind FROM pg_class c WHERE c.oid=to_regclass(%s)",
                (fullname,))
    rec = cur.fetchone()
    if not rec or rec[0] not in ("r", "p"):
        raise RuntimeError("HOLD_MISSING_PHYSICAL_" + fullname)
    relation = sql.Identifier(schema, table)
    cur.execute(sql.SQL("""
        SELECT COUNT(*) AS rows,
               COUNT(DISTINCT s.race_id) AS races,
               COUNT(*) FILTER (WHERE s.snapshot_at IS NULL) AS no_timestamp,
               COUNT(*) FILTER (WHERE r.deadline_at IS NULL) AS no_cutoff,
               COUNT(*) FILTER (
                    WHERE r.deadline_at IS NOT NULL
                      AND s.snapshot_at < r.deadline_at::timestamptz
               ) AS labelled_before_cutoff,
               COUNT(*) FILTER (
                    WHERE r.deadline_at IS NOT NULL
                      AND s.snapshot_at >= r.deadline_at::timestamptz
               ) AS labelled_at_or_after_cutoff
          FROM {} AS s
          LEFT JOIN public.v2_races AS r ON r.race_id=s.race_id
         WHERE s.race_id >= %s AND s.race_id < %s
    """).format(relation), (LOW, HIGH))
    return dict(zip(("rows","races","no_timestamp","no_cutoff",
                     "labelled_before_cutoff","labelled_at_or_after_cutoff"),
                    cur.fetchone()))

def main():
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_ONLY_LOCAL_CONOHA_DATABASE")
    print("V5_OCT26_REALTIME_SOURCE_STAGE_AUDIT_BEGIN_READ_ONLY", flush=True)
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='12000ms'")
                cur.execute("SET LOCAL lock_timeout='500ms'")
                cur.execute("SET LOCAL work_mem='4MB'")
                for src, dest in PAIRS:
                    old = inspect(cur, "public", src)
                    new = inspect(cur, "boat_data_stage", dest)
                    print("FAMILY|" + dest
                          + "|source_rows=" + str(old["rows"])
                          + "|stage_rows=" + str(new["rows"])
                          + "|source_races=" + str(old["races"])
                          + "|stage_races=" + str(new["races"])
                          + "|source_label_predeadline=" + str(old["labelled_before_cutoff"])
                          + "|stage_label_predeadline=" + str(new["labelled_before_cutoff"])
                          + "|source_label_after_or_at=" + str(old["labelled_at_or_after_cutoff"])
                          + "|stage_label_after_or_at=" + str(new["labelled_at_or_after_cutoff"])
                          + "|source_unknown_cutoff=" + str(old["no_cutoff"])
                          + "|stage_unknown_cutoff=" + str(new["no_cutoff"])
                          + "|source_missing_timestamp=" + str(old["no_timestamp"])
                          + "|stage_missing_timestamp=" + str(new["no_timestamp"]),
                          flush=True)
        conn.rollback()
    print("V5_OCT26_REALTIME_AUDIT_COMPLETE_NO_WRITES_NO_CUTOVER_NO_BUY",
          flush=True)
    print("CAUTION_SNAPSHOT_AT_BEFORE_CUTOFF_IS_LABEL_ONLY_NOT_INDEPENDENT_CAPTURE_PROOF",
          flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("V5_OCT26_REALTIME_AUDIT_HOLD "+type(exc).__name__+":"
              +str(exc).splitlines()[0][:140], flush=True)
        sys.exit(2)
