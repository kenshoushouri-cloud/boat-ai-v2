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
SCRIPT = ROOT / ".github" / "scripts" / "candidate_discovery_v3_archetypes_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v3_archetypes_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryV3Tests(unittest.TestCase):
    def test_ticket_score_has_no_hard_gate(self):
        for mode in ("market_lead", "model_lead", "consensus"):
            values = [mod.ticket_score(pr, mr, mode) for pr, mr in ((1, 1), (20, 5), (5, 20), (120, 120))]
            self.assertTrue(all(value >= 0 for value in values))

    def test_lane_contexts_generalize_s02_s03_s04_shapes(self):
        self.assertTrue(mod.lane_matches("IN_STRONG_LATE_MARKET", "12", 8))
        self.assertTrue(mod.lane_matches("STANDARD_LATE_MARKET", "07", 8))
        self.assertTrue(mod.lane_matches("EARLY_MODEL", "12", 2))
        self.assertFalse(mod.lane_matches("IN_STRONG_LATE_MARKET", "12", 4))

    def test_source_has_no_absolute_odds_or_ev_thresholds(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("raw_ev", text)
        self.assertNotIn("odds_min", text)
        self.assertNotIn("odds_max", text)
        self.assertIn("set transaction read only", text)


if __name__ == "__main__":
    unittest.main()
