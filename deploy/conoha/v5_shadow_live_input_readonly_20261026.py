#!/usr/bin/env python3
"""V5 same-day paper/shadow INPUT watcher, PostgreSQL read-only.

Reads EXISTING 13 boat_data VIEWs that track active collectors.
It DOES NOT call official websites, collect again, write any DB row,
make forecast/bets, promote a model, switch routes or stop legacy jobs.
A successful run proves only V5 can consume its live source, NOT that
real-model inference or historical ROI has been validated.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))

READ_SQL = """
WITH next_races AS MATERIALIZED (
  SELECT r.race_id, r.deadline_at::timestamptz AS deadline
  FROM boat_data.races r
  WHERE r.race_date=%s
    AND r.deadline_at::timestamptz > %s::timestamptz
    AND r.deadline_at::timestamptz <= %s::timestamptz
  ORDER BY r.deadline_at::timestamptz, r.race_id
  LIMIT 6
)
SELECT r.race_id,
  to_char(r.deadline AT TIME ZONE 'Asia/Tokyo','HH24:MI') AS cutoff_jst,
  COALESCE(e.lanes,0) AS entry_lanes,
  COALESCE(e.racers,0) AS racer_ids,
  COALESCE(x.exh_lanes,0) AS exhibition_lanes,
  COALESCE(o.odds_tickets,0) AS odds_tickets
FROM next_races r
LEFT JOIN LATERAL (
  SELECT count(DISTINCT lane)::int AS lanes,
    count(DISTINCT racer_number) FILTER (WHERE racer_number IS NOT NULL)::int AS racers
  FROM boat_data.entries
  WHERE race_id=r.race_id AND lane BETWEEN 1 AND 6
) e ON true
LEFT JOIN LATERAL (
  SELECT max(n)::int AS exh_lanes FROM (
    SELECT count(DISTINCT lane)::int AS n
    FROM boat_data.exhibition_snapshots
    WHERE race_id=r.race_id
      AND lane BETWEEN 1 AND 6 AND exhibition_time IS NOT NULL
      AND snapshot_at<r.deadline AND snapshot_at<=%s::timestamptz
    GROUP BY snapshot_label
  ) snapshots
) x ON true
LEFT JOIN LATERAL (
  SELECT max(n)::int AS odds_tickets FROM (
    SELECT count(DISTINCT ticket)::int AS n
    FROM boat_data.odds_snapshots
    WHERE race_id=r.race_id AND odds>0
      AND snapshot_at<r.deadline AND snapshot_at<=%s::timestamptz
    GROUP BY snapshot_label
  ) snapshots
) o ON true
ORDER BY r.deadline, r.race_id
"""


def main():
    if os.environ.get("DATABASE_URL") != "postgresql:///railway":
        raise RuntimeError("HOLD_WRONG_DB_ENDPOINT")
    if os.environ.get("V5_SHADOW_READONLY") != "YES":
        raise RuntimeError("HOLD_SHADOW_READONLY_FLAG_REQUIRED")
    now = datetime.now(JST)
    today = now.date()
    print("V5_SHADOW_READONLY_START", now.isoformat(timespec="seconds"),
          "BUY=OFF NO_HTTP NO_DB_WRITES NO_CUTOVER", flush=True)
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5,
                         autocommit=True, row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cur.execute("SET LOCAL TIME ZONE 'Asia/Tokyo'")
                cur.execute("SET LOCAL statement_timeout='11000ms'")
                cur.execute("SET LOCAL lock_timeout='750ms'")
                cur.execute("SET LOCAL work_mem='4MB'")
                cur.execute("SELECT current_database() AS db, current_user AS pg_role")
                who = cur.fetchone()
                if (who["db"], who["pg_role"]) != ("railway", "postgres"):
                    raise RuntimeError("HOLD_ROLE_OR_DATABASE")
                cur.execute(
                    "SELECT count(*) AS n FROM pg_class c "
                    "JOIN pg_namespace ns ON ns.oid=c.relnamespace "
                    "WHERE ns.nspname='boat_data' AND c.relkind='v' "
                    "AND c.relname IN ('races','entries',"
                    "'exhibition_snapshots','odds_snapshots')"
                )
                if cur.fetchone()["n"] != 4:
                    raise RuntimeError("HOLD_REQUIRED_LIVE_VIEWS_ABSENT")
                cur.execute(
                    "SELECT count(*) AS n FROM boat_data.races "
                    "WHERE race_date=%s", (today,)
                )
                race_count = cur.fetchone()["n"]
                print("V5_LIVE_ORIGINAL_TODAY_RACES", race_count, flush=True)
                cur.execute(
                    READ_SQL,
                    (today, now, now + timedelta(hours=4), now, now)
                )
                candidates = cur.fetchall()
                good = 0
                for row in candidates:
                    ready = (
                        row["entry_lanes"] == 6 and row["racer_ids"] == 6 and
                        row["exhibition_lanes"] == 6 and row["odds_tickets"] >= 120
                    )
                    good += ready
                    print("V5_SHADOW_INPUT", row["race_id"],
                          "cutoff_jst="+str(row["cutoff_jst"]),
                          "entries="+str(row["entry_lanes"]),
                          "racers="+str(row["racer_ids"]),
                          "exhibition="+str(row["exhibition_lanes"]),
                          "odds="+str(row["odds_tickets"]),
                          "status="+("INPUT_SHAPE_PASS_NOT_MODEL" if ready else "WAIT_INPUT"),
                          flush=True)
    print("V5_SHADOW_READONLY_PASS", "sampled="+str(len(candidates)),
          "structurally_ready="+str(good),
          "LIVE_SOURCE_ONLY=YES", "NO_MODEL_SCORING=YES",
          "NO_BUY=YES", "NO_DB_WRITES=YES", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = exc.sqlstate if isinstance(exc, psycopg.Error) else str(exc).split("\n")[0][:120]
        print("V5_SHADOW_READONLY_HOLD", msg, "BUY=OFF NO_DB_WRITES", flush=True)
        sys.exit(2)
