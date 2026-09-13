from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

psycopg = types.ModuleType("psycopg")
psycopg.rows = types.ModuleType("psycopg.rows")
psycopg.rows.dict_row = object()
sys.modules.setdefault("psycopg", psycopg)
sys.modules.setdefault("psycopg.rows", psycopg.rows)

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "candidate_discovery_v1_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryV1Tests(unittest.TestCase):
    def test_ticket_probabilities_are_complete_and_normalized(self):
        entries = [
            {
                "lane": lane,
                "racer_class": 3,
                "national_win_rate": 5.5 + lane * 0.1,
                "national_place2_rate": 35 + lane,
                "local_place2_rate": 30 + lane,
                "avg_st": 0.14 + lane * 0.005,
                "motor_place2_rate": 30 + lane,
            }
            for lane in range(1, 7)
        ]
        probs = mod.ticket_probabilities(entries, "12", 0.0)
        self.assertEqual(120, len(probs))
        self.assertTrue(math.isclose(1.0, sum(probs.values()), rel_tol=0, abs_tol=1e-12))

    def test_rank_day_uses_equal_structural_consensus(self):
        rows = [
            {"race_id": "A", "p1": 0.10, "margin": 0.03, "concentration": 0.20},
            {"race_id": "B", "p1": 0.09, "margin": 0.02, "concentration": 0.19},
            {"race_id": "C", "p1": 0.08, "margin": 0.01, "concentration": 0.18},
        ]
        ranked = mod.rank_day(rows)
        self.assertEqual(["A", "B", "C"], [row["race_id"] for row in ranked])
        self.assertEqual([1, 2, 3], [row["daily_rank"] for row in ranked])

    def test_source_does_not_read_odds_or_raw_ev(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("v2_odds_trifecta", text)
        self.assertNotIn("raw_ev", text)
        self.assertIn("set transaction read only", text)


if __name__ == "__main__":
    unittest.main()
