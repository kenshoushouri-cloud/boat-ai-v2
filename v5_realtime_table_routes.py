"""Explicit, disabled-by-default V5 physical routing for realtime snapshots.

Physical target names are staging candidates, not existing production tables.
Do NOT set route flags until source moves, writer/read audits, backup restore
and operational rollback are explicitly approved. Never silently fall back.
"""
from __future__ import annotations
import os

PROFILE_KEY = "V5_REALTIME_PHYSICAL_PROFILE"
CONFIRM_KEY = "CONFIRM_V5_REALTIME_PHYSICAL_ROUTE"

TARGETS = {
    "v2_realtime_weather_snapshots": "v5_data.raw_weather_snapshots",
    "v2_realtime_exhibition_snapshots": "v5_data.raw_exhibition_snapshots",
    "v2_realtime_entry_snapshots": "v5_data.raw_entry_snapshots",
    "v2_realtime_odds_snapshots": "v5_data.raw_odds_snapshots",
    "v2_realtime_race_condition_snapshots": "v5_data.raw_race_condition_snapshots",
    "v2_realtime_racer_condition_snapshots": "v5_data.raw_racer_condition_snapshots",
}


def physical_enabled() -> bool:
    value = os.environ.get(PROFILE_KEY, "legacy")
    if value == "legacy":
        return False
    if value != "physical":
        raise RuntimeError(f"STOP: invalid {PROFILE_KEY}")
    if os.environ.get(CONFIRM_KEY) != "YES":
        raise RuntimeError(f"STOP: {CONFIRM_KEY} not confirmed")
    return True


def resolve_realtime_table(name: str) -> str:
    active = physical_enabled()
    if name not in TARGETS:
        raise ValueError("STOP: unknown realtime table")
    return TARGETS[name] if active else name


def verify_physical_targets(fetch_all) -> None:
    """Catalog existence check; never create tables or scan large data."""
    if not physical_enabled():
        return
    for target in TARGETS.values():
        rows = fetch_all("SELECT relkind FROM pg_class WHERE oid=to_regclass(%s)", (target,))
        if not rows or rows[0].get("relkind") not in ("r", "p"):
            raise RuntimeError("STOP: missing or non-table V5 snapshot target")
