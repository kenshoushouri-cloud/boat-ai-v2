"""Offline V5 core race, entries, official result and trifecta source routing.

No DB, HTTP, service launch, ALTER, COPY or schema writes.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from v5_core_read_routes import core_relation
from v5_daily_table_routes import resolve_table
from v5.conoha_realtime_window_pg import build_candidates_query

PROFILE = "V5_DAILY_WRITE_ROUTE_PROFILE"
CONFIRM = "CONFIRM_V5_PHYSICAL_WRITER_ROUTE"


class CoreReadRouteTests(unittest.TestCase):
    def configured(self, mode=None, confirm=None):
        env = {k: v for k, v in os.environ.items()
               if k not in (PROFILE, CONFIRM,
                             "V5_REALTIME_PHYSICAL_PROFILE",
                             "CONFIRM_V5_REALTIME_PHYSICAL_ROUTE")}
        if mode is not None:
            env[PROFILE] = mode
        if confirm is not None:
            env[CONFIRM] = confirm
        return patch.dict(os.environ, env, clear=True)

    def test_legacy_default_keeps_five_core_tables(self):
        with self.configured():
            for old in ("v2_venues", "v2_races", "v2_race_entries",
                        "v2_results", "v2_odds_trifecta"):
                self.assertEqual(resolve_table(old), old)
                self.assertEqual(core_relation(old).as_string(),
                                 '"public"."'+old+'"')

    def test_opted_core_has_five_fixed_physical_names(self):
        targets = {
            "v2_venues": "venues",
            "v2_races": "raw_races",
            "v2_race_entries": "raw_entries",
            "v2_results": "raw_results",
            "v2_odds_trifecta": "trifecta_odds",
        }
        with self.configured("core", "YES"):
            for old, target in targets.items():
                self.assertEqual(resolve_table(old), "v5_data."+target)
                self.assertEqual(core_relation(old).as_string(),
                                 '"v5_data"."'+target+'"')

    def test_unconfirmed_core_is_blocked(self):
        with self.configured("core"):
            with self.assertRaisesRegex(RuntimeError, "not YES"):
                core_relation("v2_races")

    def test_unknown_profile_fails_closed(self):
        with self.configured("CORE", "YES"):
            with self.assertRaises(RuntimeError):
                core_relation("v2_races")

    def test_unknown_table_is_never_accepted(self):
        with self.configured():
            with self.assertRaisesRegex(ValueError, "unknown"):
                core_relation("v2_realtime_odds_snapshots")

    def test_odds_only_keeps_races_unmoved(self):
        with self.configured("odds", "YES"):
            self.assertEqual(core_relation("v2_races").as_string(),
                             '"public"."v2_races"')
            self.assertEqual(core_relation("v2_odds_trifecta").as_string(),
                             '"v5_data"."trifecta_odds"')

    def test_forward_scheduler_follows_core_race_mapping(self):
        with self.configured("core", "YES"):
            statement = build_candidates_query().as_string()
        self.assertIn('FROM "v5_data"."raw_races" r', statement)
        self.assertIn('"public"."v2_realtime_exhibition_snapshots"', statement)

    def test_forward_scheduler_legacy_default_keeps_core_race(self):
        with self.configured():
            statement = build_candidates_query().as_string()
        self.assertIn('FROM "public"."v2_races" r', statement)

    def test_core_collector_uses_same_routes_at_all_read_points(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "v21_realtime_collector_pg.py").read_text(encoding="utf-8")
        self.assertIn('core_relation("v2_races")', src)
        self.assertIn('core_relation("v2_race_entries")', src)
        self.assertIn('core_relation("v2_odds_trifecta")', src)
        self.assertNotIn('fetch_all("select * from v2_races', src)

    def test_midnight_result_reads_and_writes_share_core_route(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "v5/conoha_midnight_results_pg.py").read_text(encoding="utf-8")
        self.assertIn('core_relation("v2_races")', src)
        self.assertIn('core_relation("v2_results")', src)
        self.assertIn('upsert_rows("v2_results",', src)
        daily = (root / "repair_month_all_pg.py").read_text(encoding="utf-8")
        self.assertIn("resolve_v5_daily_table(table)", daily)


if __name__ == "__main__":
    unittest.main()
