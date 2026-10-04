# -*- coding: utf-8 -*-
"""Read-only logical-footprint audit for one historical archive pilot month.

This script reports row counts and PostgreSQL tuple payload bytes only. It never
exports row contents, writes to the database, uploads data, or changes retention.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os

JST = timezone(timedelta(hours=9))

TABLES = (
    ("v2_odds_trifecta", None),
    ("v2_realtime_odds_snapshots", "historical"),
    ("v2_realtime_weather_snapshots", "historical"),
    ("v2_realtime_exhibition_snapshots", "historical"),
    ("v2_realtime_entry_snapshots", "historical"),
    ("v2_realtime_race_condition_snapshots", "historical"),
    ("v2_realtime_racer_condition_snapshots", "historical"),
)


def _table_exists(cur, table: str) -> bool:
    cur.execute(
        "select exists(select 1 from information_schema.tables where table_schema='public' and table_name=%s)",
        (table,),
    )
    row = cur.fetchone()
    return bool(row and row[0])


def _month_bounds(month_text: str) -> tuple[date, date]:
    start = datetime.strptime(month_text, "%Y-%m").date().replace(day=1)
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    return start, next_month - timedelta(days=1)


def _audit_table(cur, table: str, label: str | None, start: date, end: date) -> tuple[int, int]:
    if not _table_exists(cur, table):
        return 0, 0

    if table == "v2_odds_trifecta":
        rid_start = start.strftime("%Y%m%d")
        rid_end = (end + timedelta(days=1)).strftime("%Y%m%d")
        cur.execute(
            f"""select count(*)::bigint, coalesce(sum(pg_column_size(t)),0)::bigint
                from {table} t
                where race_id >= %s and race_id < %s""",
            (rid_start, rid_end),
        )
    else:
        cur.execute(
            f"""select count(*)::bigint, coalesce(sum(pg_column_size(t)),0)::bigint
                from {table} t
                where race_date >= %s and race_date <= %s and snapshot_label = %s""",
            (start, end, label),
        )
    row = cur.fetchone() or (0, 0)
    return int(row[0] or 0), int(row[1] or 0)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")

    month = os.getenv("ARCHIVE_FOOTPRINT_MONTH", "2026-07").strip()
    start, end = _month_bounds(month)
    min_age_days = int(os.getenv("ARCHIVE_FOOTPRINT_MIN_AGE_DAYS", "30"))
    today = datetime.now(JST).date()
    if end > today - timedelta(days=min_age_days):
        raise RuntimeError("pilot month is too recent for historical archive audit")

    import psycopg

    results: list[tuple[str, str | None, int, int]] = []
    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c statement_timeout=120000 -c timezone=UTC",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()[0]).lower() != "on":
                raise RuntimeError("read-only guard failed")
            for table, label in TABLES:
                rows, payload_bytes = _audit_table(cur, table, label, start, end)
                results.append((table, label, rows, payload_bytes))

    total_rows = sum(x[2] for x in results)
    total_payload = sum(x[3] for x in results)
    print(f"ARCHIVE_FOOTPRINT=READ_ONLY month={month} start={start} end={end}", flush=True)
    for table, label, rows, payload_bytes in results:
        label_text = label or "none"
        print(
            f"table={table} label={label_text} rows={rows} payload_bytes={payload_bytes}",
            flush=True,
        )
    print(f"ARCHIVE_FOOTPRINT_TOTAL rows={total_rows} payload_bytes={total_payload}", flush=True)


if __name__ == "__main__":
    main()
