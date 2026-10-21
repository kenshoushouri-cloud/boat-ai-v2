"""Offline safety tests for opt-in V5 daily relation routing.

Runs without PostgreSQL, ConoHa, network or writes.
"""
import os
import unittest
from unittest.mock import patch

from v5_daily_table_routes import resolve_table

KEYS = (
    "V5_DAILY_WRITE_ROUTE_PROFILE",
    "CONFIRM_V5_PHYSICAL_WRITER_ROUTE",
)


class DailyPhysicalTableRouteTests(unittest.TestCase):
    def base(self, **add):
        env = {k: v for k, v in os.environ.items() if k not in KEYS}
        env.update(add)
        return patch.dict(os.environ, env, clear=True)

    def test_default_legacy_is_identical(self):
        with self.base():
            for table in ("v2_venues", "v2_odds_trifecta",
                          "v2_races", "v2_results", "v2_race_entries"):
                self.assertEqual(resolve_table(table), table)

    def test_explicit_legacy_unchanged_even_if_confirmation_is_set(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="legacy",
                       CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_venues"), "v2_venues")

    def test_invalid_profile_fails_closed(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="all",
                       CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            with self.assertRaises(RuntimeError):
                resolve_table("v2_venues")

    def test_venues_requires_gate(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="venues"):
            with self.assertRaises(RuntimeError):
                resolve_table("v2_venues")

    def test_venues_profile_routes_only_venue(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="venues",
                       CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_venues"), "v5_data.venues")
            self.assertEqual(resolve_table("v2_odds_trifecta"), "v2_odds_trifecta")
            self.assertEqual(resolve_table("v2_races"), "v2_races")

    def test_odds_profile_routes_only_odds(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="odds",
                       CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_odds_trifecta"), "v5_data.trifecta_odds")
            self.assertEqual(resolve_table("v2_venues"), "v2_venues")

    def test_combined_profile_both(self):
        with self.base(V5_DAILY_WRITE_ROUTE_PROFILE="venues_odds",
                       CONFIRM_V5_PHYSICAL_WRITER_ROUTE="YES"):
            self.assertEqual(resolve_table("v2_venues"), "v5_data.venues")
            self.assertEqual(resolve_table("v2_odds_trifecta"), "v5_data.trifecta_odds")
            self.assertEqual(resolve_table("v2_results"), "v2_results")


if __name__ == "__main__":
    unittest.main()
