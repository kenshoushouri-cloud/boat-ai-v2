# -*- coding: utf-8 -*-
"""Read-only label distribution audit for v2_realtime_odds_snapshots."""
from __future__ import annotations

import os


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")

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
                """select
                       coalesce(snapshot_label, '<null>') as snapshot_label,
                       count(*)::bigint as rows,
                       count(distinct race_id)::bigint as races,
                       min(race_date)::text as min_date,
                       max(race_date)::text as max_date,
                       coalesce(sum(pg_column_size(t)),0)::bigint as payload_bytes
                   from v2_realtime_odds_snapshots t
                   group by snapshot_label
                   order by count(*) desc, snapshot_label"""
            )
            rows = cur.fetchall()
            cur.execute(
                """select count(*)::bigint,
                          count(distinct race_id)::bigint,
                          coalesce(sum(pg_column_size(t)),0)::bigint,
                          pg_total_relation_size('v2_realtime_odds_snapshots')::bigint
                   from v2_realtime_odds_snapshots t"""
            )
            total = cur.fetchone()

    print("REALTIME_ODDS_LABEL_FOOTPRINT=READ_ONLY", flush=True)
    for label, count_rows, races, min_date, max_date, payload_bytes in rows:
        print(
            f"label={label} rows={int(count_rows)} races={int(races)} "
            f"min_date={min_date} max_date={max_date} payload_bytes={int(payload_bytes)}",
            flush=True,
        )
    print(
        f"REALTIME_ODDS_TOTAL rows={int(total[0])} races={int(total[1])} "
        f"payload_bytes={int(total[2])} relation_bytes={int(total[3])}",
        flush=True,
    )


if __name__ == '__main__':
    main()
