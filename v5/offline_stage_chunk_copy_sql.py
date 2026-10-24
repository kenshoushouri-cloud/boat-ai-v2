"""Parameterized PostgreSQL keyset-stage copy SQL: OFFLINE generation only.

The resulting SQL is NOT executed by this module. Safe execution still
requires verified stage schema, approved write scope, independent restoration
and a controlled final full-key reconciliation. Streaming copy is not CDC.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from v5.offline_stage_batch_plan import TARGETS

IDENT = re.compile(r"[a-z_][a-z_0-9]*\Z")


def ident(name: str) -> str:
    if not isinstance(name, str) or not IDENT.fullmatch(name):
        raise ValueError("STOP: unsafe SQL identifier")
    return '"' + name + '"'


def relation(name: str) -> str:
    parts = name.split(".")
    if len(parts) != 2:
        raise ValueError("STOP: unqualified SQL relation")
    return ".".join(ident(part) for part in parts)


@dataclass(frozen=True)
class StageShape:
    source: str
    staged: str
    columns: tuple[str, ...]
    pk: tuple[str, ...]
    stage_is_physical: bool
    schema_same: bool
    primary_key_same: bool
    stage_not_live_writer: bool
    no_shared_serial_defaults: bool


@dataclass(frozen=True)
class CopyWindow:
    select_keys_sql: str
    select_keys_params: tuple
    insert_rows_sql: str
    insert_rows_params: tuple
    boundary_keys: tuple[str, ...]
    mode: str = "SQL_GENERATION_ONLY_NOT_APPLIED"


def validate_shape(shape: StageShape) -> None:
    if not isinstance(shape, StageShape):
        raise ValueError("STOP: missing source/stage catalog proof")
    if shape.source not in TARGETS:
        raise ValueError("STOP: source outside canonical allowlist")
    expected, wave = TARGETS[shape.source]
    if wave == 0 or shape.staged != expected:
        raise ValueError("STOP: existing venues stage or target conflict")
    if not all((
        shape.stage_is_physical is True,
        shape.schema_same is True,
        shape.primary_key_same is True,
        shape.stage_not_live_writer is True,
        shape.no_shared_serial_defaults is True,
    )):
        raise ValueError("STOP: missing physical stage compatibility evidence")
    cols = shape.columns
    pk = shape.pk
    if (not isinstance(cols, tuple) or not isinstance(pk, tuple)
            or not cols or not pk or len(pk)>4
            or len(set(cols)) != len(cols) or len(set(pk)) != len(pk)
            or not set(pk).issubset(set(cols))
            or any(not isinstance(c, str) or not IDENT.fullmatch(c)
                   for c in (*cols, *pk))):
        raise ValueError("STOP: missing/ambiguous complete ordered primary key")


def make_key_select(shape: StageShape, after: tuple | None,
                    limit: int) -> tuple[str, tuple]:
    """Build the next bounded source PK query BEFORE knowing its final key."""
    validate_shape(shape)
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("STOP: invalid bounded copy size")
    n = len(shape.pk)
    if after is not None and (
        not isinstance(after, tuple) or len(after) != n or
        any(v is None for v in after)
    ):
        raise ValueError("STOP: invalid full PK cursor")
    key_cols = ", ".join(ident(k) for k in shape.pk)
    clause = (" WHERE (" + key_cols + ") > (" +
              ", ".join(["%s"] * n) + ")") if after is not None else ""
    return (
        f"SELECT {key_cols} FROM {relation(shape.source)}{clause} "
        f"ORDER BY {key_cols} LIMIT %s",
        tuple(after or ()) + (limit,),
    )


def make_window(shape: StageShape, after: tuple | None, limit: int,
                last_key: tuple) -> CopyWindow:
    """Caller gets 'last_key' from a source keyset SELECT in same transaction.

    Never trust a date range or partial-key cursor for completeness.
    The live writer may change copied rows; final whole-key reconciliation
    after verified quiescence is mandatory.
    """
    validate_shape(shape)
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("STOP: invalid bounded copy size")
    n = len(shape.pk)
    if not isinstance(last_key, tuple) or len(last_key) != n or any(v is None for v in last_key):
        raise ValueError("STOP: invalid final PK watermark")
    if after is not None and (
        not isinstance(after, tuple) or len(after) != n or
        any(v is None for v in after) or after >= last_key
    ):
        raise ValueError("STOP: cursor must advance by full ordered PK")
    src, dst = relation(shape.source), relation(shape.staged)
    key_cols = ", ".join(ident(k) for k in shape.pk)
    all_cols = ", ".join(ident(k) for k in shape.columns)
    expr = "(" + key_cols + ")"
    params = tuple(after or ())
    boundary = " WHERE " + expr + " > (" + ", ".join(["%s"]*n) + ")" if after is not None else ""
    upper = expr + " <= (" + ", ".join(["%s"]*n) + ")"
    select_sql, select_params = make_key_select(shape, after, limit)
    insert_predicate = (boundary + " AND " if after is not None else " WHERE ") + upper
    insert_sql = (
        f"INSERT INTO {dst} ({all_cols}) "
        f"SELECT {all_cols} FROM {src}{insert_predicate} "
        f"ON CONFLICT ({key_cols}) DO NOTHING"
    )
    return CopyWindow(
        select_keys_sql=select_sql,
        select_keys_params=select_params,
        insert_rows_sql=insert_sql,
        insert_rows_params=params+last_key,
        boundary_keys=shape.pk,
    )
