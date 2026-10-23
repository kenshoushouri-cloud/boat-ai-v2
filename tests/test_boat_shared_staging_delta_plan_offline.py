"""Offline-only safety regression tests; no PostgreSQL or cloud credentials."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from deploy.conoha.boat_shared_staging_delta_plan_offline import (
    CUTOVER_GATES, STAGE_GATES, DigestRow, blockers, inspect_manifest,
    plan_full_key_delta,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/BOAT_SHARED_13_SOURCE_ROUTE_MANIFEST_20261023.json"


def fixture():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class SharedStagingOfflineTests(unittest.TestCase):
    def test_13_relations_are_isolated_from_nonupdatable_views(self):
        plans = inspect_manifest(fixture())
        self.assertEqual(len(plans), 13)
        self.assertEqual(len({p.isolated_staging_relation for p in plans}), 13)
        self.assertTrue(all(p.isolated_staging_relation.startswith("boat_data_stage.")
                            and p.existing_read_view.startswith("boat_data.")
                            and not p.cutover_ready and not p.stage_ready_for_write
                            for p in plans))

    def test_research_or_duplicate_mapping_fails_closed(self):
        doc = fixture()
        doc["tables"][0]["legacy_relation"] = "public.v2_exhibition_shadow_decisions"
        with self.assertRaises(ValueError):
            inspect_manifest(doc)
        doc = fixture()
        doc["tables"][0] = copy.deepcopy(doc["tables"][1])
        with self.assertRaises(ValueError):
            inspect_manifest(doc)

    def test_view_or_runtime_state_change_never_auto_authorizes(self):
        doc = fixture()
        doc["tables"][0]["target_relation_kind"] = "r"
        with self.assertRaises(ValueError):
            inspect_manifest(doc)
        doc = fixture()
        doc["safety"]["cutover_ready"] = True
        with self.assertRaises(ValueError):
            inspect_manifest(doc)
        doc = fixture()
        doc["tables"][0]["physical_copy_completed"] = True
        with self.assertRaises(ValueError):
            inspect_manifest(doc)

    def test_all_gates_default_closed_and_string_true_rejected(self):
        self.assertEqual(blockers(STAGE_GATES, {}), STAGE_GATES)
        self.assertEqual(blockers(CUTOVER_GATES, {}), CUTOVER_GATES)
        self.assertEqual(blockers(STAGE_GATES, {STAGE_GATES[0]: "true"}), STAGE_GATES)
        self.assertEqual(blockers(STAGE_GATES, {k: True for k in STAGE_GATES}), ())

    def test_complete_key_delta_detects_insert_update_delete(self):
        h = lambda char: char * 64
        src = [DigestRow(("01",), h("a")), DigestRow(("03",), h("b"))]
        dst = [DigestRow(("02",), h("c")), DigestRow(("03",), h("d"))]
        ops = list(plan_full_key_delta(src, dst))
        self.assertEqual([(o.operation, o.key) for o in ops],
                         [("INSERT", ("01",)), ("DELETE", ("02",)),
                          ("UPDATE", ("03",))])
        self.assertEqual(ops[0].source_digest, h("a"))
        self.assertIsNone(ops[1].source_digest)

    def test_equal_or_empty_snapshots_have_no_delta(self):
        row = DigestRow(("race", "1"), "a" * 64)
        self.assertEqual(list(plan_full_key_delta([row], [row])), [])
        self.assertEqual(list(plan_full_key_delta([], [])), [])

    def test_duplicate_unsorted_key_and_invalid_digest_rejected(self):
        a = DigestRow(("1",), "a" * 64)
        b = DigestRow(("2",), "b" * 64)
        for source in ([a, a], [b, a], [DigestRow(("3",), "not-a-hash")]):
            with self.subTest(source=source), self.assertRaises(ValueError):
                list(plan_full_key_delta(source, [a]))

    def test_manifest_missing_table_is_stop(self):
        doc = fixture()
        doc["tables"].pop()
        with self.assertRaises(ValueError):
            inspect_manifest(doc)


if __name__ == "__main__":
    unittest.main()
