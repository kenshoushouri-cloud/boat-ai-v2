"""Offline safety gates for common V5/V6 venues: no network or DB writes.

The live source remains legacy even though boat_data schema exists.
Do not flip any route flags until a later migration/canary approves them.
"""
import os
import unittest
from unittest.mock import patch

from db_pg import _table_identifier
from v5_core_read_routes import core_relation, legacy_entry_alters
from v5_daily_table_routes import resolve_table

KEYS = (
    "V5_DAILY_WRITE_ROUTE_PROFILE",
    "CONFIRM_V5_PHYSICAL_WRITER_ROUTE",
    "CONFIRM_BOAT_SHARED_VENUES_ROUTE",
)

class SharedVenuesSafetyTests(unittest.TestCase):
    def env(self, **flags):
        env = {k: v for k, v in os.environ.items() if k not in KEYS}
        env.update(flags)
        return patch.dict(os.environ, env, clear=True)

    def test_default_legacy_is_unchanged(self):
        with self.env():
            self.assertEqual(resolve_table("v2_venues"), "v2_venues")
            self.assertEqual(core_relation("v2_venues").as_string(),
                             '"public"."v2_venues"')

    def test_old_venues_route_keeps_staging_name(self):
        with self.env(V5_DAILY_WRITE_ROUTE_PROFILE="venues",
                      CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_venues"), "v5_data.venues")

    def test_new_shared_profile_without_first_confirmation_stops(self):
        with self.env(V5_DAILY_WRITE_ROUTE_PROFILE="shared_venues_v1"):
            with self.assertRaises(RuntimeError):
                resolve_table("v2_venues")

    def test_new_shared_profile_without_third_confirmation_stops(self):
        with self.env(V5_DAILY_WRITE_ROUTE_PROFILE="shared_venues_v1",
                      CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            with self.assertRaisesRegex(RuntimeError, "CONFIRM_BOAT_SHARED_VENUES_ROUTE"):
                resolve_table("v2_venues")

    def test_new_shared_profile_with_only_third_confirmation_stops(self):
        with self.env(V5_DAILY_WRITE_ROUTE_PROFILE="shared_venues_v1",
                      CONFIRM_BOAT_SHARED_VENUES_ROUTE="YES"):
            with self.assertRaises(RuntimeError):
                resolve_table("v2_venues")

    def test_shared_venues_only_when_all_three_gates_approved(self):
        with self.env(V5_DAILY_WRITE_ROUTE_PROFILE="shared_venues_v1",
                      CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES",
                      CONFIRM_BOAT_SHARED_VENUES_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_venues"), "boat_data.venues")
            self.assertEqual(resolve_table("v2_races"), "v2_races")
            self.assertEqual(resolve_table("v2_results"), "v2_results")
            self.assertEqual(core_relation("v2_venues").as_string(),
                             '"boat_data"."venues"')
            self.assertEqual(core_relation("v2_races").as_string(),
                             '"public"."v2_races"')
            self.assertEqual(len(legacy_entry_alters()), 3)

    def test_db_writer_quotes_shared_name_as_allowlisted_identifier(self):
        self.assertEqual(_table_identifier("boat_data.venues").as_string(),
                         '"boat_data"."venues"')
        with self.assertRaises(ValueError):
            _table_identifier("boat_data.other")
        with self.assertRaises(ValueError):
            _table_identifier("boat_data.venues; DROP TABLE public.v2_venues")

if __name__ == "__main__":
    unittest.main()
