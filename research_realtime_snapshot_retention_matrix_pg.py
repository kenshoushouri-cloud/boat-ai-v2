# -*- coding: utf-8 -*-
"""Read-only hot/cold planning matrix for non-odds realtime snapshot families.

Logical tuple payload only; never infer physical DELETE reclaim from this output.
"""
from __future__ import annotations

from datetime import date, timedelta
import os

TABLES = (
    "v2_realtime_racer_condition_snapshots",
    "v2_realtime_weather_snapshots",
    "v2_realtime_race_condition_snapshots",
    "v2_realtime_exhibition_snapshots",
    "v2_realtime_entry_snapshots",
)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    as_of = date.fromisoformat(os.getenv("RETENTION_AS_OF_DATE", "2026-09-15"))
    days_list = [int(x) for x in os.getenv("RETENTION_DAYS", "30,60").split(",") if x.strip()]
    if not days_list or min(days_list) < 1 or max(days_list) > 180:
        raise RuntimeError("RETENTION_DAYS must be within 1..180")

    import psycopg
    from psycopg import sql

    results = []
    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c statement_timeout=240000 -c timezone=UTC",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()[0]).lower() != "on":
                raise RuntimeError("read-only guard failed")

            for table in TABLES:
                ident = sql.Identifier(table)
                cur.execute(
                    sql.SQL("select pg_total_relation_size({})::bigint").format(sql.Literal(table))
                )
                relation_bytes = int(cur.fetchone()[0])
                cur.execute(
                    sql.SQL(
                        """select coalesce(snapshot_label,'<null>')::text,
                                  count(*)::bigint,
                                  coalesce(sum(pg_column_size(t)),0)::bigint,
                                  min(race_date)::text,
                                  max(race_date)::text
                           from {} t
                           where race_date <= %s
                           group by snapshot_label
                           order by snapshot_label"""
                    ).format(ident),
                    (as_of,),
                )
                totals = {
                    str(label): (int(rows), int(payload), min_date, max_date)
                    for label, rows, payload, min_date, max_date in cur.fetchall()
                }
                windows = {}
                for days in days_list:
                    start = as_of - timedelta(days=days - 1)
                    cur.execute(
                        sql.SQL(
                            """select coalesce(snapshot_label,'<null>')::text,
                                      count(*)::bigint,
                                      coalesce(sum(pg_column_size(t)),0)::bigint
                               from {} t
                               where race_date between %s and %s
                               group by snapshot_label
                               order by snapshot_label"""
                        ).format(ident),
                        (start, as_of),
                    )
                    windows[days] = {
                        str(label): (int(rows), int(payload))
                        for label, rows, payload in cur.fetchall()
                    }
                results.append((table, relation_bytes, totals, windows))

    print(
        f"REALTIME_SNAPSHOT_RETENTION_MATRIX=READ_ONLY as_of={as_of.isoformat()} "
        f"days={','.join(map(str, days_list))}",
        flush=True,
    )
    for table, relation_bytes, totals, windows in results:
        print(f"SNAPSHOT_TABLE table={table} relation_bytes={relation_bytes}", flush=True)
        for label, (total_rows, total_payload, min_date, max_date) in totals.items():
            print(
                f"SNAPSHOT_TOTAL table={table} label={label} rows={total_rows} "
                f"logical_payload_bytes={total_payload} min_date={min_date} max_date={max_date}",
                flush=True,
            )
            for days in days_list:
                hot_rows, hot_payload = windows[days].get(label, (0, 0))
                print(
                    f"SNAPSHOT_WINDOW table={table} label={label} days={days} "
                    f"hot_rows={hot_rows} hot_logical_payload_bytes={hot_payload} "
                    f"cold_rows={total_rows-hot_rows} cold_logical_payload_bytes={total_payload-hot_payload}",
                    flush=True,
                )
    print("REALTIME_SNAPSHOT_RETENTION_NOTE=logical_payload_only_not_physical_reclaim_no_delete", flush=True)
    print("REALTIME_SNAPSHOT_RETENTION_MATRIX_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
