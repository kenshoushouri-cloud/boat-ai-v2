"""Synthetic-only regression tests for the V5 13-source offline planner."""
import copy
import json
import unittest
from pathlib import Path

from v5.offline_stage_batch_plan import TARGETS, plan


def fixed_manifest():
    base = {
        "schema_id": "boat_shared_cutover_route_inventory_v1",
        "safety": {"cutover_ready": False},
        "tables": [],
    }
    for src in TARGETS:
        base["tables"].append({
            "legacy_relation": src,
            "canonical_relation": "boat_data." + src.removeprefix("public.v2_"),
            "full_writer_reader_and_ddl_coverage_certified": False,
            "ongoing_change_capture_validated": False,
        })
    return base


class StageBatchPlannerTest(unittest.TestCase):
    def test_thirteen_rows_partitioned_without_writes(self):
        result = plan(fixed_manifest())
        self.assertEqual(result["table_count"], 13)
        self.assertEqual([result["wave_0_preserve"], result["wave_1_priority"], result["wave_2_remaining"]], [1, 6, 6])
        self.assertEqual(result["production_cutover"], "NO_GO")
        self.assertEqual(result["automatic_night_cutover"], "NOT_INSTALLED")
        self.assertEqual(result["mode"], "OFFLINE_PLAN_ONLY_NO_SQL_EXECUTION")

    def test_venues_existing_stage_is_preserved(self):
        result = plan(fixed_manifest())
        venue = next(x for x in result["tables"] if x["source"] == "public.v2_venues")
        self.assertEqual(venue["proposed_stage"], "boat_data_stage.venues")
        self.assertEqual(venue["mode"], "PRESERVE_EXISTING_STAGE_VERIFY_ONLY")

    def test_duplicate_or_missing_source_denied(self):
        m = fixed_manifest()
        m["tables"][-1] = copy.deepcopy(m["tables"][0])
        with self.assertRaisesRegex(ValueError, "allowlist|duplicate"):
            plan(m)

    def test_wrong_manifest_version_or_cutover_flag_denied(self):
        m = fixed_manifest()
        m["schema_id"] = "unknown"
        with self.assertRaises(ValueError):
            plan(m)
        m = fixed_manifest()
        m["safety"]["cutover_ready"] = True
        with self.assertRaisesRegex(ValueError, "cutover authorization"):
            plan(m)

    def test_canonical_view_collision_denied(self):
        m = fixed_manifest()
        m["tables"][1]["canonical_relation"] = m["tables"][0]["canonical_relation"]
        with self.assertRaisesRegex(ValueError, "canonical VIEW"):
            plan(m)


if __name__ == "__main__":
    unittest.main()
