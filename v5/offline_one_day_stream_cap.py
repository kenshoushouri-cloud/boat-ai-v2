"""V5 one-day streaming retrieval cap. Pure offline consumption by default.

Caller supplies Q1/Q2 and separately Q3 iterator factories. No database connection,
SQL execution, bets or real ROI claims. A server-side cursor with fetch-size 1
is necessary for bounded client-side fetching. This measures decoded payload,
NOT actual TCP wire bytes and cannot stop an already-returned oversized row.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from v5.offline_catalog_smoke_gate import (
    FirstDaySmoke, check_smoke_measurements, first_day_smoke_contract,
)

SQL_BLOB_SHA = "9c3ecd56ed64d8b5f6590fd711d62c2d74eac37c"
MAX_SINGLE_ROW_BYTES = 64_000
FEATURE_QUERIES = ("Q1", "Q2")
RESULT_QUERY = "Q3"


class StreamStopped(ValueError):
    """Hard HOLD: caller must abandon the one-day batch; never trim or resume."""


@dataclass(frozen=True)
class FeatureStream:
    day: date
    inventory: tuple[Mapping, ...]
    lanes: tuple[Mapping, ...]
    decoded_bytes: int
    research_only: bool = field(default=True, init=False)
    inventory_authenticated: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


@dataclass(frozen=True)
class SealedStream:
    features: FeatureStream
    results: tuple[Mapping, ...]
    decoded_bytes: int
    # Even complete rows are retrospective/caller-supplied, not proof of BUY.
    actual_roi_verified: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _encode(row: Mapping) -> int:
    """Portable client-side byte accounting; does NOT measure TCP overhead."""
    try:
        encoded = json.dumps(dict(row), ensure_ascii=False, sort_keys=True,
                             default=lambda v: v.isoformat()
                             if type(v) in (date, datetime) else str(v),
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise StreamStopped("ROW_ENCODING_UNSAFE") from exc
    return len(encoded)


def _fetch_capped(factory: Callable[[str], Iterable[Mapping]], label: str,
                  maximum: int, available_bytes: int) -> tuple[tuple[Mapping, ...], int]:
    """Consume one row at a time and close stream on any cap/error."""
    if type(maximum) is not int or type(available_bytes) is not int or available_bytes < 0:
        raise StreamStopped("INVALID_CAP")
    source = iter(factory(label))
    rows, consumed = [], 0
    end_marker = object()
    try:
        while True:
            row = next(source, end_marker)
            if row is end_marker:
                break
            if not isinstance(row, Mapping):
                raise StreamStopped("UNEXPECTED_ROW_TYPE")
            if len(rows) >= maximum:
                raise StreamStopped(label + "_ROW_LIMIT_EXCEEDED")
            nbytes = _encode(row)
            if nbytes > MAX_SINGLE_ROW_BYTES:
                raise StreamStopped(label + "_ONE_ROW_TOO_LARGE")
            if consumed + nbytes > available_bytes:
                raise StreamStopped(label + "_DECODED_BYTES_LIMIT_EXCEEDED")
            rows.append(dict(row))
            consumed += nbytes
    finally:
        close = getattr(source, "close", None)
        if callable(close):
            close()
    return tuple(rows), consumed


def read_one_day_features(day: date, factory: Callable[[str], Iterable[Mapping]],
                          contract: FirstDaySmoke | None = None) -> FeatureStream:
    """Features only; Q3 isn't touched. NEVER infer missing inventory is a holiday."""
    contract = first_day_smoke_contract(day) if contract is None else contract
    if (type(contract) is not FirstDaySmoke or type(day) is not date
            or day != contract.day or contract.max_window_days != 1):
        raise StreamStopped("ONE_DAY_CONTRACT_REQUIRED")
    inventory, n1 = _fetch_capped(factory, "Q1", contract.max_inventory_rows,
                                  contract.max_total_bytes)
    if not inventory:
        raise StreamStopped("EMPTY_INVENTORY_UNKNOWN_NOT_HOLIDAY")
    lanes, n2 = _fetch_capped(factory, "Q2", contract.max_lane_rows,
                              contract.max_total_bytes-n1)
    if len(lanes) != 6*len(inventory):
        raise StreamStopped("Q2_RAW_ROW_COUNT_MISMATCH_DO_NOT_TRIM")
    return FeatureStream(day, inventory, lanes, n1+n2)


def read_one_day_postrace(features: FeatureStream,
                          factory: Callable[[str], Iterable[Mapping]],
                          *, selection_sealed: bool = False,
                          contract: FirstDaySmoke | None = None) -> SealedStream:
    """Postrace Q3 is inaccessible until caller explicitly seals decisions.

    selection_sealed is a user assertion, NOT an authentication of historical
    predeadline purchase, and never authorizes actual ROI or BUY.
    """
    if type(features) is not FeatureStream or selection_sealed is not True:
        raise StreamStopped("FROZEN_SELECTION_REQUIRED_BEFORE_Q3")
    contract = first_day_smoke_contract(features.day) if contract is None else contract
    if type(contract) is not FirstDaySmoke or contract.day != features.day:
        raise StreamStopped("ONE_DAY_CONTRACT_REQUIRED")
    results, n3 = _fetch_capped(factory, RESULT_QUERY, contract.max_result_rows,
                               contract.max_total_bytes-features.decoded_bytes)
    status, _ = check_smoke_measurements(contract, len(features.inventory),
                                         len(features.lanes), len(results),
                                         features.decoded_bytes+n3)
    if status != "SMOKE_COUNTS_WITHIN_CAP_UNVERIFIED":
        raise StreamStopped("Q3_RAW_ROW_COUNT_MISMATCH_DO_NOT_TRIM")
    return SealedStream(features, results, features.decoded_bytes+n3)


def reviewed_select_statements(path: Path) -> dict[str, str]:
    """Inspect the unchanged reviewed 7-day SQL text without ever running it."""
    data = Path(path).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual != SQL_BLOB_SHA:
        raise StreamStopped("UNREVIEWED_SOURCE_SQL")
    source = data.decode("utf-8")
    result = {}
    for label, nextlabel in (("Q1", "Q2"), ("Q2", "Q3"), ("Q3", None)):
        start = source.find("-- " + label + ":")
        end = source.find("-- " + nextlabel + ":", start + 1) if nextlabel else len(source)
        if start < 0 or end < 0:
            raise StreamStopped("SQL_SECTION_MISSING")
        block = source[start:end]
        # Strip comment lines, retaining only one reviewed WITH/SELECT statement.
        sql = "\n".join(line for line in block.splitlines()
                        if line.strip() and not line.lstrip().startswith("--")).strip()
        if not sql.startswith("WITH p AS (") or not sql.endswith(";") or sql.count(";") != 1:
            raise StreamStopped("SOURCE_SQL_NOT_ONE_SELECT")
        result[label] = sql
    return result


def iter_server_cursor(conn, sql: str, params: Mapping, *, explicit_manual_read=False):
    """Future *manual* caller: one FETCH per row, no LIST/fetchall/implicit DB.

    Use only in an already active READ ONLY transaction after a real catalog,
    index and DB-identity check. No direct DB call in this module by default.
    """
    if explicit_manual_read is not True:
        raise StreamStopped("DB_FETCH_DISABLED_BY_DEFAULT")
    with conn.cursor(name="v5_first_day_readonly") as cur:
        cur.itersize = 1
        cur.execute(sql, dict(params))
        while True:
            row = cur.fetchone()
            if row is None:
                break
            yield row
