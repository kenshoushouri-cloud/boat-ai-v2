import os
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return database_url


def adapt_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Jsonb(value)
    return value


def get_conn():
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def fetch_one(query: str, params: tuple | list | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchone()


def fetch_all(query: str, params: tuple | list | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            return cur.fetchall()


def execute(query: str, params: tuple | list | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            count = cur.rowcount
        conn.commit()
    return count


_PHYSICAL_V5_ROUTE_TABLES = {
    # Shared V5/V6 source: selectable only via an explicitly gated route.
    "boat_data.venues": ("boat_data", "venues"),
    "v5_data.venues": ("v5_data", "venues"),
    "v5_data.raw_races": ("v5_data", "raw_races"),
    "v5_data.raw_entries": ("v5_data", "raw_entries"),
    "v5_data.raw_results": ("v5_data", "raw_results"),
    "v5_data.raw_racer_results": ("v5_data", "raw_racer_results"),
    "v5_data.trifecta_odds": ("v5_data", "trifecta_odds"),
    "v5_data.raw_weather_snapshots": ("v5_data", "raw_weather_snapshots"),
    "v5_data.raw_exhibition_snapshots": ("v5_data", "raw_exhibition_snapshots"),
    "v5_data.raw_entry_snapshots": ("v5_data", "raw_entry_snapshots"),
    "v5_data.raw_odds_snapshots": ("v5_data", "raw_odds_snapshots"),
    "v5_data.raw_race_condition_snapshots": ("v5_data", "raw_race_condition_snapshots"),
    "v5_data.raw_racer_condition_snapshots": ("v5_data", "raw_racer_condition_snapshots"),
}


def _table_identifier(table: str):
    """Safely quote fixed staged V5 and V5/V6 shared physical relation names.

    Legacy plain names preserve their original one-part quoting. Never
    interpret arbitrary dotted user input as an SQL identifier path.
    """
    if table in _PHYSICAL_V5_ROUTE_TABLES:
        return sql.Identifier(*_PHYSICAL_V5_ROUTE_TABLES[table])
    if "." in table:
        raise ValueError("Unsupported schema-qualified table")
    return sql.Identifier(table)


def _insert_one(
    cur,
    table: str,
    row: dict,
    conflict_cols: list[str] | None = None,
    update_cols: list[str] | None = None,
) -> None:
    if not row:
        raise ValueError("row is empty")

    cols = list(row.keys())
    values = [adapt_value(row[c]) for c in cols]

    insert_sql = sql.SQL(
        "insert into {table} ({cols}) values ({values})"
    ).format(
        table=_table_identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in cols),
    )

    if conflict_cols is None:
        cur.execute(insert_sql, values)
        return

    conflict_sql = sql.SQL(" on conflict ({conflict_cols}) ").format(
        conflict_cols=sql.SQL(", ").join(
            sql.Identifier(c) for c in conflict_cols
        )
    )

    if update_cols is None:
        effective_update_cols = [
            c for c in cols if c not in conflict_cols
        ]
    else:
        effective_update_cols = update_cols

    if effective_update_cols:
        update_sql = sql.SQL("do update set {updates}").format(
            updates=sql.SQL(", ").join(
                sql.SQL("{} = excluded.{}").format(
                    sql.Identifier(c),
                    sql.Identifier(c),
                )
                for c in effective_update_cols
            )
        )
    else:
        update_sql = sql.SQL("do nothing")

    cur.execute(insert_sql + conflict_sql + update_sql, values)


def upsert_rows(
    table: str,
    rows: list[dict],
    conflict_cols: list[str],
    update_cols: list[str] | None = None,
) -> int:
    if not rows:
        return 0

    processed = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for row in rows:
                _insert_one(
                    cur=cur,
                    table=table,
                    row=row,
                    conflict_cols=conflict_cols,
                    update_cols=update_cols,
                )
                processed += 1

        conn.commit()

    return processed


def replace_rows_atomic(
    table: str,
    rows: list[dict],
    delete_where: dict[str, Any],
    expected_count: int | None = None,
) -> int:
    if not rows:
        raise ValueError("replace_rows_atomic: rows is empty")

    if not delete_where:
        raise ValueError(
            "replace_rows_atomic: delete_where is required"
        )

    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(
            "replace_rows_atomic: unexpected row count "
            f"expected={expected_count} actual={len(rows)}"
        )

    first_col_set = set(rows[0].keys())
    for index, row in enumerate(rows):
        if set(row.keys()) != first_col_set:
            raise ValueError(
                "replace_rows_atomic: inconsistent columns "
                f"row_index={index}"
            )

    where_cols = list(delete_where.keys())
    where_values = [
        adapt_value(delete_where[column]) for column in where_cols
    ]

    delete_sql = sql.SQL(
        "delete from {table} where {conditions}"
    ).format(
        table=_table_identifier(table),
        conditions=sql.SQL(" and ").join(
            sql.SQL("{} = {}").format(
                sql.Identifier(column),
                sql.Placeholder(),
            )
            for column in where_cols
        ),
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(delete_sql, where_values)

            for row in rows:
                _insert_one(
                    cur=cur,
                    table=table,
                    row=row,
                    conflict_cols=None,
                    update_cols=None,
                )

        conn.commit()

    return len(rows)