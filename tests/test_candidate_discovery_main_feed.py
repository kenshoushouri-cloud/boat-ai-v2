from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

psycopg = types.ModuleType("psycopg")
psycopg.rows = types.ModuleType("psycopg.rows")
psycopg.rows.dict_row = object()
sys.modules.setdefault("psycopg", psycopg)
sys.modules.setdefault("psycopg.rows", psycopg.rows)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "candidate_discovery_main_feed_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_main_feed_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryMainFeedTests(unittest.TestCase):
    def test_fixed_core_contract(self):
        self.assertEqual(6, mod.CORE_RACES)
        self.assertEqual(2, mod.CORE_TICKETS)
        self.assertEqual("A", mod.tier_for(1))
        self.assertEqual("B", mod.tier_for(3))
        self.assertEqual("C", mod.tier_for(6))

    def test_legacy_rules_are_carried(self):
        self.assertEqual({"S01", "S02", "S03", "S04", "S05"}, mod.LEGACY_RULES)

    def test_source_keeps_odds_display_only_and_fail_closed(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertIn('"display_odds"', text)
        self.assertNotIn("raw_ev", text)
        self.assertNotIn("odds_min", text)
        self.assertNotIn("odds_max", text)
        self.assertIn("set transaction read only", text)
        self.assertIn('"purchase_action": false', text)


if __name__ == "__main__":
    unittest.main()
