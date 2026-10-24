# -*- coding: utf-8 -*-
"""Read-only hot/cold footprint audit for realtime odds labels."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

JST = timezone(timedelta(hours=9))


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    cold_days = int(os.getenv("REALTIME_ODDS_COLD_DAYS", "30"))
    cutoff = datetime.now(JST).date() - timedelta(days=cold_days)

    import psycopg

    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c statement_timeout=120000 -c timezone=UTC",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()[0]).lower() != "on":
                raise RuntimeError("read-only guard failed")
            cur.execute(
                """select coalesce(snapshot_label,'<null>') as label,
                          count(*) filter (where race_date < %s)::bigint as cold_rows,
                          count(distinct race_id) filter (where race_date < %s)::bigint as cold_races,
                          coalesce(sum(pg_column_size(t)) filter (where race_date < %s),0)::bigint as cold_payload_bytes,
                          count(*) filter (where race_date >= %s)::bigint as hot_rows,
                          count(distinct race_id) filter (where race_date >= %s)::bigint as hot_races,
                          coalesce(sum(pg_column_size(t)) filter (where race_date >= %s),0)::bigint as hot_payload_bytes
                   from v2_realtime_odds_snapshots t
                   group by snapshot_label
                   order by cold_rows desc, label""",
                (cutoff, cutoff, cutoff, cutoff, cutoff, cutoff),
            )
            rows = cur.fetchall()

    print(f"REALTIME_ODDS_COLD_FOOTPRINT=READ_ONLY cold_before={cutoff} cold_days={cold_days}", flush=True)
    for label, cold_rows, cold_races, cold_bytes, hot_rows, hot_races, hot_bytes in rows:
        print(
            f"label={label} cold_rows={int(cold_rows)} cold_races={int(cold_races)} "
            f"cold_payload_bytes={int(cold_bytes)} hot_rows={int(hot_rows)} "
            f"hot_races={int(hot_races)} hot_payload_bytes={int(hot_bytes)}",
            flush=True,
        )


if __name__ == '__main__':
    main()
