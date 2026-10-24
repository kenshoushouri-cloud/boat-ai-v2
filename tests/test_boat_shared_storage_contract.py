"""Offline checks for version-neutral data identities (V5/V6)."""
import unittest

from boat_shared_storage_contract import (
    BOAT_HISTORY_DATABASE,
    CANONICAL_SCHEMA,
    HISTORY_RELATIONS,
    RELATIONS,
    RESEARCH_ONLY,
    STAGED_PILOTS,
    assert_contract,
    shared_target,
    split_identifier,
)


class SharedStorageContractTests(unittest.TestCase):
    def test_unique_all_sources_and_targets(self):
        self.assertTrue(assert_contract())
        self.assertEqual(len(RELATIONS), 13)

    def test_common_schema_is_not_versioned(self):
        self.assertEqual(CANONICAL_SCHEMA, "boat_data")
        self.assertTrue(all(r.canonical.startswith("boat_data.") for r in RELATIONS))
        self.assertFalse(any(".v5_" in r.canonical for r in RELATIONS))

    def test_staged_venues_not_a_canonical_final_table(self):
        self.assertEqual(STAGED_PILOTS["public.v2_venues"], "boat_data_stage.venues")
        self.assertEqual(shared_target("public.v2_venues"), "boat_data.venues")
        self.assertNotEqual(STAGED_PILOTS["public.v2_venues"], shared_target("public.v2_venues"))

    def test_old_source_to_future_same_physical_target(self):
        self.assertEqual(shared_target("public.v2_realtime_exhibition_snapshots"),
                         "boat_data.exhibition_snapshots")
        self.assertEqual(shared_target("public.v2_results"), "boat_data.results")
        self.assertEqual(split_identifier("boat_data.results"),
                         ("boat_data", "results"))

    def test_unknown_identifier_refused(self):
        for name in ("public.v2_unknown", "v5_data.venues", "boat_data.unknown",
                     "boat_data.results;DROP TABLE public.v2_results"):
            with self.assertRaises(ValueError):
                split_identifier(name)
        with self.assertRaises(ValueError):
            shared_target("public.v2_unknown")

    def test_research_not_in_prediction_contract(self):
        for name in RESEARCH_ONLY:
            with self.assertRaises(ValueError):
                shared_target(name)

    def test_archive_is_external_database_not_copied(self):
        self.assertEqual(BOAT_HISTORY_DATABASE, "boat_history_archive")
        for name in HISTORY_RELATIONS:
            with self.assertRaises(ValueError):
                shared_target(name)


if __name__ == "__main__":
    unittest.main()
