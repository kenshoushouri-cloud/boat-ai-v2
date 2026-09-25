# -*- coding: utf-8 -*-
"""Read-only online-retention scenario audit for large Boat odds tables.

Research-only. This script never exports row contents and never mutates PostgreSQL.
It measures exact row counts and logical tuple payload bytes for candidate hot windows.
Physical Railway volume reclaim is intentionally not inferred from these numbers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from typing import Iterable

JST = timezone(timedelta(hours=9))


def _as_of_date() -> date:
    raw = os.getenv("RETENTION_AS_OF_DATE", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return datetime.now(JST).date()


def _days() -> list[int]:
    raw = os.getenv("RETENTION_DAYS", "7,14,30,60")
    vals = sorted({int(x.strip()) for x in raw.split(",") if x.strip()})
    if not vals or vals[0] < 1 or vals[-1] > 180:
        raise RuntimeError("RETENTION_DAYS must contain values in 1..180")
    return vals


def _prefix(d: date) -> str:
    return d.strftime("%Y%m%d")


def _fmt(label: str, pairs: Iterable[tuple[str, object]]) -> None:
    print(label + " " + " ".join(f"{k}={v}" for k, v in pairs), flush=True)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")

    as_of = _as_of_date()
    days_list = _days()
    end_prefix = _prefix(as_of + timedelta(days=1))

    import psycopg

    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c statement_timeout=240000 -c timezone=UTC",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()[0]).lower() != "on":
                raise RuntimeError("read-only guard failed")

            # Base odds total: exact logical payload. This is a full read-only scan.
            cur.execute(
                """select count(*)::bigint,
                          coalesce(sum(pg_column_size(t)),0)::bigint,
                          pg_total_relation_size('v2_odds_trifecta')::bigint
                   from v2_odds_trifecta t"""
            )
            base_total_rows, base_total_payload, base_relation_bytes = map(int, cur.fetchone())

            base_windows: dict[int, tuple[int, int]] = {}
            for days in days_list:
                start = as_of - timedelta(days=days - 1)
                cur.execute(
                    """select count(*)::bigint,
                              coalesce(sum(pg_column_size(t)),0)::bigint
                       from v2_odds_trifecta t
                       where race_id >= %s and race_id < %s""",
                    (_prefix(start), end_prefix),
                )
                base_windows[days] = tuple(map(int, cur.fetchone()))

            # Realtime odds totals by label and exact hot windows.
            cur.execute(
                """select coalesce(snapshot_label,'<null>') as label,
                          count(*)::bigint,
                          coalesce(sum(pg_column_size(t)),0)::bigint
                   from v2_realtime_odds_snapshots t
                   where race_date <= %s
                   group by snapshot_label
                   order by label""",
                (as_of,),
            )
            realtime_totals = {
                str(label): (int(rows), int(payload))
                for label, rows, payload in cur.fetchall()
            }
            cur.execute("select pg_total_relation_size('v2_realtime_odds_snapshots')::bigint")
            realtime_relation_bytes = int(cur.fetchone()[0])

            realtime_windows: dict[int, dict[str, tuple[int, int]]] = {}
            for days in days_list:
                start = as_of - timedelta(days=days - 1)
                cur.execute(
                    """select coalesce(snapshot_label,'<null>') as label,
                              count(*)::bigint,
                              coalesce(sum(pg_column_size(t)),0)::bigint
                       from v2_realtime_odds_snapshots t
                       where race_date between %s and %s
                       group by snapshot_label
                       order by label""",
                    (start, as_of),
                )
                realtime_windows[days] = {
                    str(label): (int(rows), int(payload))
                    for label, rows, payload in cur.fetchall()
                }

    print(
        f"ONLINE_RETENTION_SCENARIOS=READ_ONLY as_of={as_of.isoformat()} "
        f"days={','.join(map(str, days_list))}",
        flush=True,
    )
    _fmt(
        "BASE_TOTAL",
        [
            ("rows", base_total_rows),
            ("logical_payload_bytes", base_total_payload),
            ("relation_bytes", base_relation_bytes),
        ],
    )
    for days in days_list:
        hot_rows, hot_payload = base_windows[days]
        _fmt(
            "BASE_WINDOW",
            [
                ("days", days),
                ("hot_rows", hot_rows),
                ("hot_logical_payload_bytes", hot_payload),
                ("cold_rows", base_total_rows - hot_rows),
                ("cold_logical_payload_bytes", base_total_payload - hot_payload),
            ],
        )

    _fmt("REALTIME_RELATION", [("relation_bytes", realtime_relation_bytes)])
    for label, (total_rows, total_payload) in realtime_totals.items():
        _fmt(
            "REALTIME_TOTAL",
            [("label", label), ("rows", total_rows), ("logical_payload_bytes", total_payload)],
        )
        for days in days_list:
            hot_rows, hot_payload = realtime_windows[days].get(label, (0, 0))
            _fmt(
                "REALTIME_WINDOW",
                [
                    ("label", label),
                    ("days", days),
                    ("hot_rows", hot_rows),
                    ("hot_logical_payload_bytes", hot_payload),
                    ("cold_rows", total_rows - hot_rows),
                    ("cold_logical_payload_bytes", total_payload - hot_payload),
                ],
            )

    print(
        "ONLINE_RETENTION_NOTE=logical_payload_only_not_physical_reclaim_no_delete_no_export",
        flush=True,
    )


if __name__ == "__main__":
    main()
