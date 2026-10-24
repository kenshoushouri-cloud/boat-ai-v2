#!/usr/bin/env python3
"""Purely offline V5 stage-copy plan; never opens PG or executes DDL/DML.

Input: versioned 13-table canonical source manifest from GitHub. The output is a
deterministic non-executable migration plan and a list of mandatory blockers.
It is NOT a backup, copy program, readiness certificate or authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from boat_shared_storage_contract import RELATIONS, assert_contract

# Explicit audited allowlist: physical source -> proposed stage destination.
# Existing venues stage stays untouched. VIEWs are not overwritten.
TARGETS = {
    "public.v2_venues": ("boat_data_stage.venues", 0),
    "public.v2_races": ("boat_data_stage.races", 1),
    "public.v2_race_entries": ("boat_data_stage.entries", 1),
    "public.v2_results": ("boat_data_stage.results", 1),
    "public.v2_result_entries": ("boat_data_stage.racer_results", 1),
    "public.v2_odds_trifecta": ("boat_data_stage.trifecta_odds", 1),
    "public.v2_realtime_exhibition_snapshots": ("boat_data_stage.exhibition_snapshots", 1),
    "public.v2_racer_course_stats_snapshots": ("boat_data_stage.racer_course_stats_snapshots", 2),
    "public.v2_realtime_entry_snapshots": ("boat_data_stage.entry_snapshots", 2),
    "public.v2_realtime_odds_snapshots": ("boat_data_stage.odds_snapshots", 2),
    "public.v2_realtime_weather_snapshots": ("boat_data_stage.weather_snapshots", 2),
    "public.v2_realtime_race_condition_snapshots": ("boat_data_stage.race_condition_snapshots", 2),
    "public.v2_realtime_racer_condition_snapshots": ("boat_data_stage.racer_condition_snapshots", 2),
}

BLOCKERS = (
    "independent_offsite_restore_unverified",
    "runtime_writers_not_completely_certified",
    "per_table_keys_defaults_constraints_and_acl_not_approved",
    "incremental_insert_update_delete_catchup_untested",
    "source_stage_row_and_content_parity_unproven",
    "automatic_rollback_and_collector_restart_untested",
    "live_cutover_not_separately_approved",
    "model_asof_and_first_capture_not_verified",
)


def plan(manifest: dict) -> dict:
    if manifest.get("schema_id") != "boat_shared_cutover_route_inventory_v1":
        raise ValueError("unrecognized fixed manifest schema")
    rows = manifest.get("tables")
    if not isinstance(rows, list) or len(rows) != 13:
        raise ValueError("expected exactly 13 canonical source entries")
    sources = [r.get("legacy_relation") for r in rows]
    if len(set(sources)) != 13 or set(sources) != set(TARGETS):
        raise ValueError("manifest source allowlist mismatch or duplicate")
    assert_contract()
    verified_views = {r.legacy: r.canonical for r in RELATIONS}
    canonical = [r.get("canonical_relation") for r in rows]
    if len(set(canonical)) != 13 or any(
        verified_views.get(r.get("legacy_relation")) != r.get("canonical_relation")
        for r in rows
    ):
        raise ValueError("unexpected/duplicate canonical VIEW names")
    approved = manifest.get("safety", {})
    if approved.get("cutover_ready") is not False:
        raise ValueError("unexpected live cutover authorization state")
    entries = []
    for source, (stage, wave) in TARGETS.items():
        row = next(r for r in rows if r["legacy_relation"] == source)
        # Manifest documents pre-cutover state; do not accept it as authority
        # to overwrite a currently existing stage or turn any route on.
        entries.append({
            "source": source,
            "canonical_view": row["canonical_relation"],
            "proposed_stage": stage,
            "wave": wave,
            "mode": "PRESERVE_EXISTING_STAGE_VERIFY_ONLY" if wave == 0 else "NOT_COPIED_REQUIRES_SEPARATE_APPROVAL",
            "candidate_writers": row.get("candidate_writer_files", []),
            "actual_writers_certified": row.get("full_writer_reader_and_ddl_coverage_certified") is True,
            "change_capture_certified": row.get("ongoing_change_capture_validated") is True,
        })
    return {
        "mode": "OFFLINE_PLAN_ONLY_NO_SQL_EXECUTION",
        "table_count": 13,
        "wave_0_preserve": 1,
        "wave_1_priority": 6,
        "wave_2_remaining": 6,
        "production_cutover": "NO_GO",
        "automatic_night_cutover": "NOT_INSTALLED",
        "current_collectors": "UNCHANGED",
        "tables": entries,
        "cutover_blockers": list(BLOCKERS),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="local checked-in manifest JSON")
    args = parser.parse_args()
    result = plan(json.loads(Path(args.manifest).read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
