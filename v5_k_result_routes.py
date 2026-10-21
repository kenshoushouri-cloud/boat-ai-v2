"""Conservative K-file six-lane result writer routes for proposed V5 storage.

Disabled by default. Never permit a split where summary results are in V5
but six-lane results are re-created in public. Catalog check is read-only.
No DB or service access at import time.
"""
from __future__ import annotations

from v5_daily_table_routes import resolve_table
from v5_core_read_routes import core_relation

LEGACY = ("v2_results", "v2_result_entries")
PHYSICAL = ("v5_data.raw_results", "v5_data.raw_racer_results")


def k_targets():
    """Return quoted result identifiers + physical bit; fail on mixed modes."""
    names = tuple(resolve_table(name) for name in LEGACY)
    if names == LEGACY:
        return core_relation(LEGACY[0]), core_relation(LEGACY[1]), False
    if names == PHYSICAL:
        return core_relation(LEGACY[0]), core_relation(LEGACY[1]), True
    raise RuntimeError("STOP: K result tables must use one storage profile")


def result_columns_location():
    """information_schema parameters for the same target as K result UPDATE."""
    name = resolve_table("v2_results")
    if name == LEGACY[0]:
        return "public", "v2_results"
    if name == PHYSICAL[0]:
        # Also reject a mixed six-lane route.
        k_targets()
        return "v5_data", "raw_results"
    raise RuntimeError("STOP: unsafe K results column target")


def validate_physical_targets(cursor):
    """Read pg_catalog only; no CREATE TABLE/INDEX on a moved legacy source."""
    for target in PHYSICAL:
        cursor.execute(
            "SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (target,)
        )
        row = cursor.fetchone()
        if not row or row[0] not in ("r", "p"):
            raise RuntimeError("STOP: missing/non-table physical K result target")
