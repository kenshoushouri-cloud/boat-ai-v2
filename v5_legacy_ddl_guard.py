"""Fail-closed guard against legacy public tables reappearing during V5 migration.

Only the explicit V5 cutover flag changes behavior. With flag absent, existing
realtime collector remains identical. This guard does NOT perform migration,
does NOT rewrite writes/reads and must never be enabled before a cutover plan.
"""
from __future__ import annotations

import os

GUARD_FLAG = "V5_BLOCK_LEGACY_REALTIME_DDL"


def require_legacy_realtime_ddl_allowed() -> None:
    """Stop BEFORE CREATE/ALTER if a V5 cutover has blocked legacy DDL."""
    flag = os.environ.get(GUARD_FLAG, "")
    if flag not in ("", "0", "NO", "YES"):
        raise RuntimeError(f"STOP: invalid {GUARD_FLAG} value; expected YES or unset")
    if flag == "YES":
        raise RuntimeError(
            "STOP: legacy realtime CREATE/ALTER blocked for V5 migration; "
            "do not recreate public.v2_realtime_* tables"
        )

# The legacy collector must not recreate even one source after a table is
# moved to V5. This extra catalog-only gate is independent of service env
# flags and requires one lightweight query, not six separate connections.
def forbid_legacy_realtime_if_physical_exists(fetch_all) -> None:
    """Fail before old DDL if ANY planned V5 physical snapshot object exists."""
    from v5_realtime_table_routes import TARGETS

    physical = tuple(TARGETS.values())
    labels = tuple(f"target_{i}" for i in range(len(physical)))
    query = "SELECT " + ", ".join(
        f"to_regclass(%s) AS {label}" for label in labels
    )
    rows = fetch_all(query, physical)
    if not isinstance(rows, (list, tuple)) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("STOP: realtime V5 physical catalog gate unavailable")
    record = rows[0]
    if any(label not in record for label in labels):
        raise RuntimeError("STOP: realtime V5 physical catalog gate incomplete")
    if any(record[label] is not None for label in labels):
        raise RuntimeError(
            "STOP: one or more V5 physical snapshot targets exist; "
            "refusing legacy public CREATE/ALTER"
        )
