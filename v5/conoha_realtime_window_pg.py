"""ConoHa V5: bounded, deadline-aware forward collection scheduler.

Read-only preview by default. --apply needs V5_ENABLE_LIVE_COLLECTOR=YES.
Uses EXISTING official v21 safe collector, not model/bets/LINE.
Designed to be called under /run/lock/boat-v5-collector.lock (external flock).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
RID_PATTERN = re.compile(r"20\d{6}_(?:0[1-9]|1\d|2[0-4])_(?:0[1-9]|1[0-2])\Z")


def eligible(row: dict, now: datetime, *, min_minutes: int = 9,
             max_minutes: int = 24) -> bool:
    """Use server-observed cutoff only; no result/odds/finish-based selection."""
    rid, deadline = row.get("race_id"), row.get("deadline_at")
    if not isinstance(rid, str) or RID_PATTERN.fullmatch(rid) is None:
        return False
    if not isinstance(deadline, datetime) or deadline.tzinfo is None:
        return False
    if rid[:8] != now.astimezone(JST).strftime("%Y%m%d"):
        return False
    remaining = (deadline - now).total_seconds()
    if not min_minutes * 60 <= remaining <= max_minutes * 60:
        return False
    return int(row.get("exh_lanes") or 0) < 6 or int(row.get("odds_tickets") or 0) < 120


def _snapshot_relation(name: str):
    """Return a safely quoted known snapshot table, not arbitrary SQL input."""
    from psycopg import sql
    from v5_realtime_table_routes import resolve_realtime_table

    resolved = resolve_realtime_table(name)
    if "." in resolved:
        schema, relation = resolved.split(".", 1)
    else:
        schema, relation = "public", resolved
    return sql.Identifier(schema, relation)


def build_candidates_query():
    """Use the same snapshot sources as the guarded realtime writer.

    Core race metadata still references public.v2_races; physical core
    race cutover has its own unresolved reader/writer dependency gates.
    """
    from psycopg import sql
    from v5_core_read_routes import core_relation

    return sql.SQL("""SELECT r.race_id,
                          r.deadline_at::timestamptz AS deadline_at,
                          (SELECT COALESCE(MAX(s.n),0)
                           FROM (SELECT COUNT(DISTINCT e.lane) AS n
                                 FROM {} e
                                 WHERE e.race_id = r.race_id
                                   AND e.exhibition_time IS NOT NULL
                                   AND e.snapshot_at < r.deadline_at::timestamptz
                                 GROUP BY e.snapshot_label) s)
                            AS exh_lanes,
                          (SELECT COALESCE(MAX(s.n),0)
                           FROM (SELECT COUNT(DISTINCT o.ticket) AS n
                                 FROM {} o
                                 WHERE o.race_id = r.race_id AND o.odds > 0
                                   AND o.snapshot_at < r.deadline_at::timestamptz
                                 GROUP BY o.snapshot_label) s)
                            AS odds_tickets
                   FROM {} r
                   WHERE r.race_date = %s
                     AND r.deadline_at IS NOT NULL
                     AND r.deadline_at::timestamptz BETWEEN %s AND %s
                   ORDER BY r.deadline_at::timestamptz, r.race_id
                   LIMIT 100""").format(
        _snapshot_relation("v2_realtime_exhibition_snapshots"),
        _snapshot_relation("v2_realtime_odds_snapshots"),
        core_relation("v2_races"),
    )


def load_candidates(now: datetime, *, min_minutes: int = 9) -> list[dict]:
    from db_pg import get_conn

    # Resolve both route switches BEFORE opening the database connection.
    query = build_candidates_query()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (now.astimezone(JST).date(), now + timedelta(minutes=min_minutes),
                 now + timedelta(minutes=24)),
            )
            return list(cur.fetchall())


def collect_one(rid: str, *, at: datetime, child_timeout: int = 75) -> int:
    if RID_PATTERN.fullmatch(rid) is None:
        raise ValueError("invalid race_id")
    # Per-invocation labels preserve earlier snapshots; no shared fixed-label overwrites.
    label = "conoha_forward_" + at.astimezone(JST).strftime("%Y%m%d_%H%M%S")
    env = dict(os.environ)
    env.update({
        "TARGET_DATE": at.astimezone(JST).strftime("%Y-%m-%d"),
        "TARGET_RACE_ID": rid,
        "SNAPSHOT_LABEL": label,
        "COLLECT_SCOPE": "all",
        "TARGET_ID_SCOPE": "none",
        "V5_STRICT_PREDEADLINE": "1",
        "V5_DEADLINE_GUARD_SEC": "180",
        "HTTP_TIMEOUT": "20",
        "RETRY_MAX": "0",
        "REALTIME_SLEEP_SEC": "0.5",
        "TARGET_RACE_IDS_FILE": "/tmp/v5_forward_target_" + rid + ".txt",
        "COLLECTION_RACE_IDS_FILE": "/tmp/v5_forward_collection_" + rid + ".txt",
    })
    result = subprocess.run(
        [sys.executable, str(ROOT / "v21_realtime_collector_pg_safe.py")],
        cwd=ROOT, env=env, check=False, timeout=child_timeout,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="perform official HTTP and write snapshots")
    ap.add_argument("--max-races", type=int, default=2, help="per-run cap (1..3)")
    ap.add_argument("--late-retry", action="store_true",
                    help="opt in to bounded missing-data retries at 5..9 min; off by default")
    args = ap.parse_args(argv)
    if not 1 <= args.max_races <= 3:
        ap.error("--max-races must be 1..3")
    if not os.environ.get("DATABASE_URL"):
        ap.error("DATABASE_URL required; ConoHa local PostgreSQL only")
    if args.apply and os.environ.get("V5_ENABLE_LIVE_COLLECTOR") != "YES":
        ap.error("apply requires V5_ENABLE_LIVE_COLLECTOR=YES")

    now = datetime.now(JST)
    min_minutes = 5 if args.late_retry else 9
    candidates = [r for r in load_candidates(now, min_minutes=min_minutes)
                  if eligible(r, now, min_minutes=min_minutes)]
    targets = candidates[:args.max_races]
    print(f"V5_FORWARD_WINDOW_MODE={'APPLY' if args.apply else 'PREVIEW'}", flush=True)
    print(f"V5_FORWARD_WINDOW_NOW={now.isoformat()}", flush=True)
    print(f"V5_FORWARD_WINDOW_CANDIDATES={len(candidates)}", flush=True)
    print(f"V5_FORWARD_WINDOW_MIN_MINUTES={min_minutes}", flush=True)
    for row in targets:
        print(f"V5_FORWARD_TARGET={row['race_id']} cutoff={row['deadline_at']} "
              f"exh={row['exh_lanes']} odds={row['odds_tickets']}", flush=True)
    if not args.apply:
        print("V5_FORWARD_NO_HTTP_NO_WRITES=1", flush=True)
        return 0

    failed = 0
    for row in targets:
        # Revalidate the cutoff after every potentially slow HTTP collection.
        current = datetime.now(JST)
        if not eligible(row, current, min_minutes=min_minutes):
            print(f"V5_FORWARD_SKIP_STALE={row['race_id']}", flush=True)
            continue
        try:
            code = collect_one(row["race_id"], at=current)
            print(f"V5_FORWARD_COLLECTOR_RC={row['race_id']}:{code}", flush=True)
            failed += int(code != 0)
        except subprocess.TimeoutExpired:
            print(f"V5_FORWARD_TIMEOUT={row['race_id']}", flush=True)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
