"""Pure offline V5 PostgreSQL catalogue and first-day smoke guard.

Parse the *exact* three psql SELECT result sets from
ops/v5_seven_day_archive_db_preflight_readonly.sql.  A caller-supplied result
is not independently authenticated as a live Railway DB observation.
No DB, shell, network, models, betting or schema mutations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# PostgreSQL type names (udt_name) from information_schema.columns.
REQUIRED: dict[str, dict[str, frozenset[str]]] = {
    "v2_races": {
        "race_id": frozenset(("text", "varchar")),
        "race_date": frozenset(("date",)),
        "deadline_at": frozenset(("timestamptz",)),
    },
    "v2_race_entries": {
        "race_id": frozenset(("text", "varchar")),
        "lane": frozenset(("int2", "int4", "int8")),
        "racer_number": frozenset(("int2", "int4", "int8")),
        "racer_class": frozenset(("text", "varchar")),
        "recent_form": frozenset(("jsonb",)),
    },
    "v2_realtime_exhibition_snapshots": {
        "race_id": frozenset(("text", "varchar")),
        "lane": frozenset(("int2", "int4", "int8")),
        "snapshot_label": frozenset(("text", "varchar")),
        "source": frozenset(("text", "varchar")),
        "snapshot_at": frozenset(("timestamptz",)),
        "exhibition_time_rank": frozenset(("int2", "int4", "int8")),
        "raw": frozenset(("jsonb",)),
    },
    "v2_results": {
        "race_id": frozenset(("text", "varchar")),
        "result_status": frozenset(("text", "varchar")),
        "race_status": frozenset(("text", "varchar")),
        "trifecta_ticket": frozenset(("text", "varchar")),
        "trifecta_payout_yen": frozenset(("int4", "int8", "numeric")),
    },
}
INDEX_PREFIX = {
    "v2_races": ("race_date",),
    "v2_race_entries": ("race_id", "lane"),
    "v2_realtime_exhibition_snapshots": ("race_id", "snapshot_label", "lane"),
    "v2_results": ("race_id",),
}
HEADERS = (
    "table_name|column_name|data_type|udt_name|is_nullable|audit_verdict",
    "table_name|index_prefix|usable_prefix_index_present|observed_index_names",
    "database_name|connected_role|transaction_read_only|statement_timeout|"
    "races_select|entries_select|exhibition_select|results_select",
)
COUNTS = (20, 4, 1)
MAX_CATALOG_BYTES = 12_000  # The existing manual launcher truncates at 12,000.


@dataclass(frozen=True)
class CatalogJudgement:
    status: str
    reasons: tuple[str, ...]
    checked_columns: int
    checked_indexes: int
    # Caller text (or even a successful SELECT) does not certify DB identity.
    independently_authenticated_source: bool = field(default=False, init=False)
    live_schema_verified: bool = field(default=False, init=False)
    smoke_authorized: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def _sections(output: str) -> tuple[list[list[str]], ...]:
    if (type(output) is not str or not output or len(output.encode("utf-8")) > MAX_CATALOG_BYTES
            or "\x00" in output or "\r" in output):
        raise ValueError("CATALOG_OUTPUT_INVALID_OR_TRUNCATED")
    lines = [line for line in output.split("\n") if line != ""]
    sections = []
    offset = 0
    for header, expected in zip(HEADERS, COUNTS):
        if offset >= len(lines) or lines[offset] != header:
            raise ValueError("CATALOG_SECTION_HEADER_INVALID")
        offset += 1
        section = []
        while offset < len(lines) and not re.fullmatch(r"\([0-9]+ rows?\)", lines[offset]):
            section.append(lines[offset])
            offset += 1
        if offset >= len(lines):
            raise ValueError("CATALOG_ROW_FOOTER_MISSING")
        declared = int(re.fullmatch(r"\(([0-9]+) rows?\)", lines[offset]).group(1))
        if len(section) != expected or declared != expected:
            raise ValueError("CATALOG_SECTION_SIZE_MISMATCH")
        sections.append(section)
        offset += 1
    if offset != len(lines):
        raise ValueError("CATALOG_UNEXPECTED_TRAILING_ROWS")
    return tuple(sections)


def audit_catalog_psql_output(output: str) -> CatalogJudgement:
    """Never turn copied text into an independently trusted DB assertion."""
    try:
        columns_raw, indexes_raw, connection_raw = _sections(output)
    except ValueError as exc:
        return CatalogJudgement("HOLD_CATALOG_FORMAT", (str(exc),), 0, 0)
    reasons = []
    columns = {}
    for line in columns_raw:
        parts = line.split("|")
        if len(parts) != 6:
            reasons.append("COLUMN_FIELD_COUNT_INVALID")
            continue
        table, column, _dtype, udt, _nullable, verdict = parts
        key = (table, column)
        if key in columns:
            reasons.append("DUPLICATE_COLUMN_RECORD")
        columns[key] = (udt, verdict)
    expected = {(table, col) for table, colset in REQUIRED.items() for col in colset}
    if set(columns) != expected:
        reasons.append("COLUMN_POPULATION_INCOMPLETE_OR_UNKNOWN")
    for table, by_column in REQUIRED.items():
        for column, types in by_column.items():
            val = columns.get((table, column))
            if val is not None and (val[0] not in types or val[1] != "PRESENT_TYPE_REVIEW"):
                reasons.append("MISSING_OR_UNSAFE_COLUMN_TYPE:" + table + "." + column)

    indexes = {}
    for line in indexes_raw:
        parts = line.split("|")
        if len(parts) != 4:
            reasons.append("INDEX_FIELD_COUNT_INVALID")
            continue
        table, prefix, usable, _names = parts
        if table in indexes:
            reasons.append("DUPLICATE_INDEX_RECORD")
        indexes[table] = (prefix, usable)
    if set(indexes) != set(INDEX_PREFIX):
        reasons.append("INDEX_POPULATION_INCOMPLETE_OR_UNKNOWN")
    for table, expected_prefix in INDEX_PREFIX.items():
        expected_pg = "{" + ",".join(expected_prefix) + "}"
        if indexes.get(table) != (expected_pg, "t"):
            reasons.append("INDEX_LEFT_PREFIX_UNVERIFIED:" + table)

    parts = connection_raw[0].split("|")
    if len(parts) != 8:
        reasons.append("CONNECTION_FIELDS_INVALID")
    else:
        dbname, role, readonly, timeout, *access = parts
        if not dbname or not role:
            reasons.append("DATABASE_OR_ROLE_MISSING")
        if readonly != "on":
            reasons.append("TRANSACTION_NOT_READ_ONLY")
        if timeout not in ("2s", "2000ms"):
            reasons.append("STATEMENT_TIMEOUT_NOT_2S")
        if any(v != "t" for v in access):
            reasons.append("REQUIRED_SELECT_PRIVILEGE_MISSING")
    # A copied psql transcript alone cannot prove db identity, role has no
    # writes, row counts, trustworthy race calendar, or real capture timestamps.
    return CatalogJudgement(
        "CATALOG_SHAPE_OK_SOURCE_NOT_AUTHENTICATED" if not reasons else "HOLD_CATALOG_CONTRACT",
        tuple(sorted(set(reasons))), len(columns), len(indexes),
    )


@dataclass(frozen=True)
class FirstDaySmoke:
    day: date
    max_inventory_rows: int = 400
    max_lane_rows: int = 2400
    max_result_rows: int = 400
    max_total_bytes: int = 4_000_000
    max_window_days: int = field(default=1, init=False)
    database_read_authorized: bool = field(default=False, init=False)
    hypothetical_roi_authorized: bool = field(default=False, init=False)
    forward_eligible: bool = field(default=False, init=False)
    buy_eligible: bool = field(default=False, init=False)


def first_day_smoke_contract(day: date) -> FirstDaySmoke:
    if type(day) is not date or day < date(2025, 7, 1):
        raise ValueError("DAY_INVALID")
    return FirstDaySmoke(day)


def check_smoke_measurements(contract: FirstDaySmoke, inventory_rows: int,
                             lane_rows: int, result_rows: int,
                             total_bytes: int) -> tuple[str, tuple[str, ...]]:
    """Offline counts only, NEVER a live query authorization or population proof.

    On any overrun/underflow STOP, never silently LIMIT/DISTINCT or drop races.
    """
    if type(contract) is not FirstDaySmoke or any(
        type(v) is not int or v < 0 for v in
        (inventory_rows, lane_rows, result_rows, total_bytes)
    ):
        raise ValueError("SMOKE_MEASUREMENTS_INVALID")
    reasons = []
    if not 1 <= inventory_rows <= contract.max_inventory_rows:
        reasons.append("INVENTORY_EMPTY_OR_OVER_LIMIT")
    if lane_rows > contract.max_lane_rows:
        reasons.append("LANE_ROWS_OVER_LIMIT")
    if result_rows > contract.max_result_rows:
        reasons.append("RESULT_ROWS_OVER_LIMIT")
    if total_bytes > contract.max_total_bytes:
        reasons.append("TRANSFER_BYTES_OVER_LIMIT")
    if lane_rows != 6 * inventory_rows:
        reasons.append("LANE_POPULATION_NOT_SIX_PER_RACE")
    if result_rows != inventory_rows:
        reasons.append("RESULT_POPULATION_NOT_ONE_PER_RACE")
    return ("HOLD_SMOKE_LIMIT_OR_COVERAGE" if reasons else "SMOKE_COUNTS_WITHIN_CAP_UNVERIFIED",
            tuple(reasons))
