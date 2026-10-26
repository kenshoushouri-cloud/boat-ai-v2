#!/usr/bin/env python3
"""Bounded Oct26-only missing stage entries recovery (source current-state).

PREVIEW default. Apply requires V5_OCT26_ENTRIES_REPAIR_APPROVED=YES.
Never deletes/updates rows, touches timers, writes public tables, or backdates
first-capture evidence. Does NOT replace 13-family overnight reconciliation.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo

DAY = "20261026"
SOURCE = "public.v2_race_entries"
TARGET = "boat_data_stage.entries"
LOCK = 2026102503
JST = ZoneInfo("Asia/Tokyo")


def run(*, apply: bool = False) -> dict:
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_CONOHA_LOCAL_DATABASE_ONLY")
    if apply and os.environ.get("V5_OCT26_ENTRIES_REPAIR_APPROVED") != "YES":
        raise RuntimeError("HOLD_EXPLICIT_RECOVERY_APPROVAL_REQUIRED")
    if apply and 3 <= datetime.now(JST).hour < 6:
        raise RuntimeError("HOLD_STAGE11_RECONCILIATION_WINDOW")
    import psycopg
    from psycopg import sql

    result = {}
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                cur.execute("SET LOCAL statement_timeout='8000ms'")
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SET LOCAL work_mem='4MB'")
                if apply:
                    cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK,))
                    if not cur.fetchone()[0]:
                        raise RuntimeError("HOLD_STAGE_ADVISORY_LOCK_BUSY")
                for name in (SOURCE, TARGET):
                    cur.execute("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (name,))
                    rec = cur.fetchone()
                    if not rec or rec[0] not in ("r", "p"):
                        raise RuntimeError("HOLD_TARGET_NOT_PHYSICAL_" + name)
                cur.execute("""SELECT count(*) FROM pg_index i
                    WHERE i.indrelid=to_regclass(%s) AND i.indisunique
                      AND i.indisvalid AND i.indpred IS NULL""", (TARGET,))
                if cur.fetchone()[0] == 0:
                    raise RuntimeError("HOLD_MISSING_STAGE_UNIQUE_INDEX")
                cols = []
                for name in (SOURCE, TARGET):
                    cur.execute("""SELECT attname, attgenerated
                        FROM pg_attribute WHERE attrelid=to_regclass(%s)
                          AND attnum>0 AND NOT attisdropped
                        ORDER BY attnum""", (name,))
                    cols.append(cur.fetchall())
                names_src, names_dst = (set(x[0] for x in group) for group in cols)
                if names_src != names_dst:
                    raise RuntimeError("HOLD_SOURCE_STAGE_COLUMN_SET_DIFF")
                if any(x[1] for group in cols for x in group):
                    raise RuntimeError("HOLD_GENERATED_COLUMNS_UNSUPPORTED")
                # Do not assume current data was captured before the race deadline.
                cur.execute("""WITH missing AS MATERIALIZED (
                    SELECT race_id FROM boat_data_stage.races
                    WHERE race_date=DATE '2026-10-26'
                      AND NOT EXISTS(SELECT 1 FROM boat_data_stage.entries e
                                     WHERE e.race_id=boat_data_stage.races.race_id)
                ), validity AS (
                  SELECT m.race_id, count(s.race_id) AS n,
                         count(DISTINCT s.lane) AS lanes,
                         count(DISTINCT s.racer_number) AS racers,
                         min(s.lane) AS min_lane, max(s.lane) AS max_lane
                  FROM missing m LEFT JOIN public.v2_race_entries s
                    ON s.race_id=m.race_id
                  GROUP BY m.race_id
                ) SELECT count(*) AS missing_races,
                         count(*) FILTER (WHERE n=6 AND lanes=6 AND racers=6 AND min_lane=1 AND max_lane=6) AS valid,
                         coalesce(sum(n),0) AS rows
                    FROM validity""")
                missing, valid, source_rows = cur.fetchone()
                result = {"missing_races": missing, "valid_source_races": valid,
                          "source_rows": source_rows, "mode": "PREVIEW"}
                if missing == 0:
                    return {**result, "status": "NO_MISSING_STAGE_ENTRIES"}
                if valid != missing or source_rows != missing * 6:
                    raise RuntimeError("HOLD_OCT26_SOURCE_INCOMPLETE")
                # Scheduled checkpoint had exactly 144 missing races. Never widen
                # this one-off repair if the underlying state has changed.
                if missing > 144:
                    raise RuntimeError("HOLD_OUTSIDE_APPROVED_144_RACE_SCOPE")
                if not apply:
                    return {**result, "status": "PREVIEW_ONLY_NO_WRITES"}
                # Repeatable-read snapshot prevents a mismatch between the
                # guarded check and the inserted source rows.
                # No conflict overwrites. Any collision rolls back the batch.
                columns = [x[0] for x in cols[1]]
                ident = sql.SQL(", ").join(sql.Identifier(x) for x in columns)
                cur.execute(sql.SQL("""WITH missing AS MATERIALIZED (
                   SELECT r.race_id FROM boat_data_stage.races r
                   WHERE r.race_date=DATE '2026-10-26'
                     AND NOT EXISTS(SELECT 1 FROM boat_data_stage.entries e
                                    WHERE e.race_id=r.race_id)
                ) INSERT INTO boat_data_stage.entries ({cols})
                    SELECT {cols_select} FROM public.v2_race_entries src
                    JOIN missing m ON src.race_id=m.race_id
                    ON CONFLICT DO NOTHING""").format(
                      cols=ident,
                      cols_select=sql.SQL(", ").join(
                          sql.SQL("src.{}").format(sql.Identifier(col))
                          for col in columns)
                    ))
                inserted = cur.rowcount
                if inserted != missing * 6:
                    raise RuntimeError("HOLD_INSERT_COUNT_MISMATCH_ROLLBACK")
                cur.execute("""SELECT count(*) FROM boat_data_stage.entries e
                    JOIN boat_data_stage.races r ON r.race_id=e.race_id
                    WHERE r.race_date=DATE '2026-10-26'""")
                result.update({"inserted": inserted, "stage_date_rows": cur.fetchone()[0],
                               "mode": "APPLY", "status": "COMMITTED"})
        # Connection context commits only if no exceptions.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = run(apply=args.apply)
        print("V5_OCT26_ENTRY_RECOVERY_RESULT=" + str(result), flush=True)
        print("NO_PREDEADLINE_CAPTURE_PROOF_NO_BUY", flush=True)
    except Exception as e:
        print("V5_OCT26_RECOVERY_HOLD " + type(e).__name__ + ":" +
              str(e).splitlines()[0][:140], flush=True)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
