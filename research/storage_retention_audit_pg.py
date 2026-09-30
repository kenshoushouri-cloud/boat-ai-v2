# -*- coding: utf-8 -*-
"""Read-only storage retention audit for Railway Hobby migration planning.

Reads only PostgreSQL size metadata plus row/date counts. It never reads odds
values, result values, payouts, prediction outputs, or other row payloads.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
CUTOFF_DAYS = (30, 60, 90)

# mode:
# - race_id: YYYYMMDD-prefixed race_id, compared lexicographically
# - race_date: explicit date column
# - snapshot_date: explicit snapshot date column
TABLES = (
    ("v2_odds_trifecta", "race_id"),
    ("v2_realtime_odds_snapshots", "race_date"),
    ("v2_v24_motor2_forward_shadow", "race_id"),
    ("v2_result_entries", "race_id"),
    ("v2_realtime_racer_condition_snapshots", "race_date"),
    ("v2_realtime_weather_snapshots", "race_date"),
    ("v2_realtime_race_condition_snapshots", "race_date"),
    ("v2_race_entries", "race_id"),
    ("v2_realtime_exhibition_snapshots", "race_date"),
    ("v2_racer_course_stats_snapshots", "snapshot_date"),
)


def _target_date() -> date:
    raw = (os.getenv("RETENTION_AUDIT_DATE") or "").strip()
    if raw:
        return date.fromisoformat(raw)
    return datetime.now(JST).date()


def _table_exists(cur, table: str) -> bool:
    cur.execute("select to_regclass(%s)::text as regclass", (f"public.{table}",))
    row = cur.fetchone() or {}
    return bool(row.get("regclass"))


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        select exists(
          select 1
          from information_schema.columns
          where table_schema='public' and table_name=%s and column_name=%s
        ) as ok
        """,
        (table, column),
    )
    return bool((cur.fetchone() or {}).get("ok"))


def _relation_bytes(cur, table: str) -> int:
    cur.execute(
        "select pg_total_relation_size(to_regclass(%s))::bigint as bytes",
        (f"public.{table}",),
    )
    return int((cur.fetchone() or {}).get("bytes") or 0)


def _counts(cur, table: str, mode: str, audit_date: date) -> dict:
    cutoffs = {days: audit_date - timedelta(days=days) for days in CUTOFF_DAYS}

    if mode == "race_id":
        field = sql.Identifier("race_id")
        cutoff_values = [cutoffs[d].strftime("%Y%m%d") for d in CUTOFF_DAYS]
    elif mode in ("race_date", "snapshot_date"):
        field = sql.Identifier(mode)
        cutoff_values = [cutoffs[d] for d in CUTOFF_DAYS]
    else:
        raise ValueError(f"unsupported mode: {mode}")

    query = sql.SQL(
        """
        select
          count(*)::bigint as total_rows,
          min({field})::text as min_key,
          max({field})::text as max_key,
          count(*) filter (where {field} < %s)::bigint as older_30,
          count(*) filter (where {field} < %s)::bigint as older_60,
          count(*) filter (where {field} < %s)::bigint as older_90
        from {table}
        """
    ).format(field=field, table=sql.Identifier(table))
    cur.execute(query, cutoff_values)
    row = dict(cur.fetchone() or {})
    row["cutoffs"] = {str(days): cutoffs[days].isoformat() for days in CUTOFF_DAYS}
    return row


def _estimate_reclaim(relation_bytes: int, total_rows: int, older_rows: int) -> int:
    if relation_bytes <= 0 or total_rows <= 0 or older_rows <= 0:
        return 0
    return int(round(relation_bytes * (older_rows / total_rows)))


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    audit_date = _target_date()
    result = {
        "contract": "storage_retention_read_only_audit_v1",
        "audit_date_jst": audit_date.isoformat(),
        "read_only": True,
        "db_write": 0,
        "payload_values_read": 0,
        "cutoff_days": list(CUTOFF_DAYS),
        "tables": [],
        "estimated_projected_database_bytes": {},
    }

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.execute("set transaction read only")
        with conn.cursor() as cur:
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute(
                "select pg_database_size(current_database())::bigint as bytes"
            )
            result["database_bytes"] = int((cur.fetchone() or {}).get("bytes") or 0)

            reclaim_by_days = {days: 0 for days in CUTOFF_DAYS}

            for table, mode in TABLES:
                if not _table_exists(cur, table):
                    result["tables"].append(
                        {"table": table, "status": "missing", "mode": mode}
                    )
                    continue

                if not _column_exists(cur, table, mode):
                    result["tables"].append(
                        {
                            "table": table,
                            "status": "missing_date_key",
                            "mode": mode,
                            "relation_bytes": _relation_bytes(cur, table),
                        }
                    )
                    continue

                relation_bytes = _relation_bytes(cur, table)
                counts = _counts(cur, table, mode, audit_date)
                total_rows = int(counts.get("total_rows") or 0)
                item = {
                    "table": table,
                    "status": "ok",
                    "mode": mode,
                    "relation_bytes": relation_bytes,
                    "total_rows": total_rows,
                    "min_key": counts.get("min_key"),
                    "max_key": counts.get("max_key"),
                    "cutoffs": counts["cutoffs"],
                    "retention": {},
                }

                for days in CUTOFF_DAYS:
                    older = int(counts.get(f"older_{days}") or 0)
                    est = _estimate_reclaim(relation_bytes, total_rows, older)
                    reclaim_by_days[days] += est
                    item["retention"][str(days)] = {
                        "older_rows": older,
                        "hot_rows": max(total_rows - older, 0),
                        "older_pct": round((older / total_rows * 100.0), 2)
                        if total_rows
                        else 0.0,
                        "estimated_reclaim_bytes": est,
                    }

                result["tables"].append(item)

            for days in CUTOFF_DAYS:
                projected = max(
                    int(result["database_bytes"]) - reclaim_by_days[days], 0
                )
                result["estimated_projected_database_bytes"][str(days)] = {
                    "estimated_reclaim_bytes": reclaim_by_days[days],
                    "projected_database_bytes": projected,
                }

    print("STORAGE_RETENTION_AUDIT_READ_ONLY=1", flush=True)
    print("STORAGE_RETENTION_AUDIT_DB_WRITE=0", flush=True)
    print("STORAGE_RETENTION_AUDIT_PAYLOAD_VALUES_READ=0", flush=True)
    print(
        "STORAGE_RETENTION_AUDIT_JSON="
        + json.dumps(result, sort_keys=True, separators=(",", ":"), default=str),
        flush=True,
    )
    print("STORAGE_RETENTION_AUDIT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
