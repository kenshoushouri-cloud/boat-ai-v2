#!/usr/bin/env python3
"""Read-only retention sizing audit for Hobby migration planning.

No DML/DDL. The connection is forced read-only. Estimates only the two
largest odds tables and leaves every other relation unchanged, so the
projected database sizes are intentionally conservative.
"""
from __future__ import annotations

import os
from datetime import timedelta

import psycopg2
from psycopg2.extras import RealDictCursor


TABLES = (
    "v2_odds_trifecta",
    "v2_realtime_odds_snapshots",
)
WINDOWS = (30, 60, 90)


def mib(value: int | float) -> float:
    return float(value) / 1024 / 1024


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")

    conn = psycopg2.connect(url, connect_timeout=15, application_name="hobby_retention_readonly_audit")
    conn.set_session(readonly=True, autocommit=False)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("set local statement_timeout='45s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("select current_setting('transaction_read_only') as ro")
            ro = str((cur.fetchone() or {}).get("ro") or "").lower()
            if ro != "on":
                raise SystemExit(f"read-only guard failed: transaction_read_only={ro!r}")

            cur.execute("select pg_database_size(current_database())::bigint as bytes")
            db_bytes = int((cur.fetchone() or {}).get("bytes") or 0)

            cur.execute("select max(race_date) as max_date from v2_races")
            anchor = (cur.fetchone() or {}).get("max_date")
            if anchor is None:
                raise SystemExit("v2_races max(race_date) unavailable")

            stats = {}
            for table in TABLES:
                cur.execute(
                    """
                    select
                      pg_total_relation_size(%s::regclass)::bigint as relation_bytes,
                      coalesce(s.n_live_tup, c.reltuples, 0)::bigint as estimated_live_rows,
                      coalesce(s.n_dead_tup, 0)::bigint as estimated_dead_rows
                    from pg_class c
                    left join pg_stat_user_tables s on s.relid=c.oid
                    where c.oid=%s::regclass
                    """,
                    (table, table),
                )
                row = dict(cur.fetchone() or {})
                if not row:
                    raise SystemExit(f"table metadata unavailable: {table}")
                stats[table] = {
                    "relation_bytes": int(row["relation_bytes"] or 0),
                    "estimated_live_rows": max(1, int(row["estimated_live_rows"] or 0)),
                    "estimated_dead_rows": int(row["estimated_dead_rows"] or 0),
                    "hot_rows": {},
                }

            for days in WINDOWS:
                cutoff = anchor - timedelta(days=days - 1)

                cur.execute(
                    """
                    select count(*)::bigint as n
                    from v2_odds_trifecta o
                    join v2_races r on r.race_id=o.race_id
                    where r.race_date >= %s and r.race_date <= %s
                    """,
                    (cutoff, anchor),
                )
                stats["v2_odds_trifecta"]["hot_rows"][days] = int((cur.fetchone() or {}).get("n") or 0)

                cur.execute(
                    """
                    select count(*)::bigint as n
                    from v2_realtime_odds_snapshots o
                    where o.race_date >= %s and o.race_date <= %s
                    """,
                    (cutoff, anchor),
                )
                stats["v2_realtime_odds_snapshots"]["hot_rows"][days] = int((cur.fetchone() or {}).get("n") or 0)

            print("HOBBY_RETENTION_AUDIT_READ_ONLY=1")
            print(f"HOBBY_RETENTION_ANCHOR_DATE={anchor.isoformat()}")
            print(f"HOBBY_RETENTION_DB_MIB={mib(db_bytes):.1f}")

            selected_bytes = sum(x["relation_bytes"] for x in stats.values())
            fixed_other_bytes = max(0, db_bytes - selected_bytes)

            for table, data in stats.items():
                print(
                    "HOBBY_RETENTION_TABLE="
                    f"{table} relation_mib={mib(data['relation_bytes']):.1f} "
                    f"estimated_live_rows={data['estimated_live_rows']} "
                    f"estimated_dead_rows={data['estimated_dead_rows']}"
                )

            for days in WINDOWS:
                estimated_hot_selected = 0.0
                parts = []
                for table, data in stats.items():
                    ratio = min(
                        1.0,
                        data["hot_rows"][days] / max(1, data["estimated_live_rows"]),
                    )
                    estimated_bytes = data["relation_bytes"] * ratio
                    estimated_hot_selected += estimated_bytes
                    parts.append(
                        f"{table}:hot_rows={data['hot_rows'][days]},"
                        f"ratio={ratio:.4f},est_mib={mib(estimated_bytes):.1f}"
                    )

                projected = fixed_other_bytes + estimated_hot_selected
                savings = max(0.0, db_bytes - projected)
                print(
                    f"HOBBY_RETENTION_WINDOW_DAYS={days} "
                    f"PROJECTED_DB_MIB={mib(projected):.1f} "
                    f"ESTIMATED_SAVINGS_MIB={mib(savings):.1f} "
                    + " ".join(parts)
                )

            print("HOBBY_RETENTION_MUTATION=0")
            print("HOBBY_RETENTION_RESULT=PASS_READ_ONLY_ESTIMATE")
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
