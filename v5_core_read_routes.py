"""Allowlisted SQL identifier composition for staged physical V5 core tables.

Read mapping follows v5_daily_table_routes to avoid source divergence.
Existing deployments stay on public.v2_* by default. No database access.
"""
from __future__ import annotations

from psycopg import sql
from v5_daily_table_routes import resolve_table

LEGACY = frozenset((
    "v2_venues", "v2_races", "v2_race_entries",
    "v2_results", "v2_result_entries", "v2_odds_trifecta",
))

SHARED_VENUES_TARGET = "boat_data.venues"

PHYSICAL = {
    "v2_venues": "v5_data.venues",
    "v2_races": "v5_data.raw_races",
    "v2_race_entries": "v5_data.raw_entries",
    "v2_results": "v5_data.raw_results",
    "v2_result_entries": "v5_data.raw_racer_results",
    "v2_odds_trifecta": "v5_data.trifecta_odds",
}


def core_relation(name: str):
    """Resolve exactly one allowlisted core table as a quoted SQL identifier."""
    if name not in LEGACY:
        raise ValueError("STOP: unknown core table")
    routed = resolve_table(name)
    if routed == name:
        return sql.Identifier("public", name)
    if PHYSICAL.get(name) != routed and not (
        name == "v2_venues" and routed == SHARED_VENUES_TARGET
    ):
        raise RuntimeError("STOP: unexpected core table route")
    namespace, relation = routed.split(".", 1)
    return sql.Identifier(namespace, relation)


LEGACY_ENTRY_DDL = (
    "alter table v2_race_entries add column if not exists tilt numeric;",
    "alter table v2_race_entries add column if not exists motor_no integer;",
    "alter table v2_race_entries add column if not exists boat_no integer;",
)


def legacy_entry_alters():
    """Only retain old entry-table DDL when that source is still public.

    This is a disabled-by-default migration staging gate: no DDL occurs
    here. The caller must validate a moved V5 target separately.
    """
    routed = resolve_table("v2_race_entries")
    if routed == "v2_race_entries":
        return LEGACY_ENTRY_DDL
    if routed == PHYSICAL["v2_race_entries"]:
        return ()
    raise RuntimeError("STOP: unexpected core entries DDL route")
