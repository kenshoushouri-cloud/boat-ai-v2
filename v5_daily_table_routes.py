"""Opt-in V5 physical table routing for daily collectors.

Default routing is byte-for-byte legacy table names. No DB/network side effects.
Never activate a physical route before the target table actually exists and
the migration transaction, rollback and writer inventory are approved.
"""
from __future__ import annotations

import os

ROUTES = {
    "venues": {"v2_venues": "v5_data.venues"},
    "odds": {"v2_odds_trifecta": "v5_data.trifecta_odds"},
    "venues_odds": {
        "v2_venues": "v5_data.venues",
        "v2_odds_trifecta": "v5_data.trifecta_odds",
    },
    # Proposed physical names avoid collisions with current v5_data.* VIEWs.
    # Staged only: all core writers, readers and restore gates must pass
    # before the existing double gate may ever be enabled in production.
    "core": {
        "v2_venues": "v5_data.venues",
        "v2_races": "v5_data.raw_races",
        "v2_race_entries": "v5_data.raw_entries",
        "v2_results": "v5_data.raw_results",
        "v2_result_entries": "v5_data.raw_racer_results",
        "v2_odds_trifecta": "v5_data.trifecta_odds",
    },
}
MODE_KEY = "V5_DAILY_WRITE_ROUTE_PROFILE"
GATE_KEY = "CONFIRM_V5_PHYSICAL_WRITER_ROUTE"


def resolve_table(table: str) -> str:
    """Return the target of a daily upsert, with opt-in double protection.

    This only routes daily writes via repair_month_all_pg.py. It does not
    redirect SQL reads, nested legacy collectors, other services, or DDL.
    """
    profile = os.environ.get(MODE_KEY, "legacy")
    if profile == "legacy":
        return table
    if profile not in ROUTES:
        raise RuntimeError(f"Unsupported {MODE_KEY} value")
    if os.environ.get(GATE_KEY) != "YES":
        raise RuntimeError(f"V5 route blocked: {GATE_KEY} is not YES")
    return ROUTES[profile].get(table, table)
