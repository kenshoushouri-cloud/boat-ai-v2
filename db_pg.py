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


def upsert_rows(
    table: str,
    rows: list[dict],
    conflict_cols: list[str],
    update_cols: list[str] | None = None,
) -> int:
    if not rows:
        return 0

    inserted = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cols = list(row.keys())
                values = [adapt_value(row[c]) for c in cols]

                if update_cols is None:
                    effective_update_cols = [c for c in cols if c not in conflict_cols]
                else:
                    effective_update_cols = update_cols

                insert_sql = sql.SQL("insert into {table} ({cols}) values ({values})").format(
                    table=sql.Identifier(table),
                    cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
                    values=sql.SQL(", ").join(sql.Placeholder() for _ in cols),
                )

                conflict_sql = sql.SQL(" on conflict ({conflict_cols}) ").format(
                    conflict_cols=sql.SQL(", ").join(sql.Identifier(c) for c in conflict_cols)
                )

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
                inserted += 1

        conn.commit()

    return inserted