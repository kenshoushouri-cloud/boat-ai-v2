"""Version-independent relational storage contract for BOAT AI V5 and later V6.

This module is a *planning/identity* contract only. Importing it has no I/O,
and it does NOT enable, create, copy, rename, move, write or delete tables.
Existing live V5 routes keep their legacy defaults until separate guarded
service, reader/writer and rollback checks are complete.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Relation:
    category: str
    legacy: str
    canonical: str
    evidence_rule: str


# All source identities are within the 'railway' database, EXCEPT for
# BOAT_HISTORY_DATABASE below, deliberately not copied to this DB.
STORAGE_DATABASE = "railway"
CANONICAL_SCHEMA = "boat_data"
BOAT_HISTORY_DATABASE = "boat_history_archive"

RELATIONS = (
    Relation("core", "public.v2_venues", "boat_data.venues", "MASTER_VERSION"),
    Relation("core", "public.v2_races", "boat_data.races", "RACE_CUTOFF"),
    Relation("core", "public.v2_race_entries", "boat_data.entries", "RACER_ASOF"),
    Relation("core", "public.v2_results", "boat_data.results", "POSTRACE_ONLY"),
    Relation("core", "public.v2_result_entries", "boat_data.racer_results", "POSTRACE_ONLY"),
    Relation("core", "public.v2_odds_trifecta", "boat_data.trifecta_odds", "ODDS_ASOF_REQUIRED"),
    Relation("feature", "public.v2_racer_course_stats_snapshots", "boat_data.racer_course_stats_snapshots", "ASOF_REQUIRED"),
    Relation("realtime", "public.v2_realtime_entry_snapshots", "boat_data.entry_snapshots", "PREDEADLINE_CAPTURE"),
    Relation("realtime", "public.v2_realtime_exhibition_snapshots", "boat_data.exhibition_snapshots", "PREDEADLINE_CAPTURE"),
    Relation("realtime", "public.v2_realtime_odds_snapshots", "boat_data.odds_snapshots", "PREDEADLINE_CAPTURE"),
    Relation("realtime", "public.v2_realtime_weather_snapshots", "boat_data.weather_snapshots", "PREDEADLINE_CAPTURE"),
    Relation("realtime", "public.v2_realtime_race_condition_snapshots", "boat_data.race_condition_snapshots", "PREDEADLINE_CAPTURE"),
    Relation("realtime", "public.v2_realtime_racer_condition_snapshots", "boat_data.racer_condition_snapshots", "PREDEADLINE_CAPTURE"),
)

# Staged prior to this contract's creation: preserve as is until a guarded,
# independently verified follow-on staging can be prepared. Older v5_data.venues\n# references are historical proposals, NOT this current physical pilot.
STAGED_PILOTS = {"public.v2_venues": "boat_data_stage.venues"}

# Historical data is in a SEPARATE database; explicit read-only connection
# is required, never silently attached or bulk copied.
HISTORY_RELATIONS = (
    "public.v2_recent_form_archive",
    "archive.v2_realtime_race_condition_snapshots",
    "archive.v2_realtime_racer_condition_snapshots",
)

# Legacy V24 forward shadow is preserved for RESEARCH, never a proven V5/V6
# live prediction feature.
RESEARCH_ONLY = frozenset({"public.v2_v24_motor2_forward_shadow"})


def shared_target(source: str) -> str:
    """Return a fixed allowlisted target or fail closed. Does not connect."""
    for row in RELATIONS:
        if row.legacy == source:
            return row.canonical
    raise ValueError("STOP: unknown or research-only shared data relation")


def split_identifier(qualified: str) -> tuple[str, str]:
    """Prevent dynamic unapproved relation/schema injection."""
    allowed = {r.canonical for r in RELATIONS}
    if qualified not in allowed:
        raise ValueError("STOP: unapproved common storage identifier")
    schema, table = qualified.split(".")
    return schema, table


def assert_contract():
    """Offline sanity gate: deterministic target names and provenance rules."""
    src = [r.legacy for r in RELATIONS]
    dst = [r.canonical for r in RELATIONS]
    if len(src) != len(set(src)) or len(dst) != len(set(dst)):
        raise RuntimeError("STOP: duplicate shared data mapping")
    if any(not target.startswith(CANONICAL_SCHEMA + ".") for target in dst):
        raise RuntimeError("STOP: incorrect target namespace")
    if any(not r.evidence_rule for r in RELATIONS):
        raise RuntimeError("STOP: missing evidence rule")
    if any(r.legacy in RESEARCH_ONLY for r in RELATIONS):
        raise RuntimeError("STOP: research-only data in live storage")
    return True
