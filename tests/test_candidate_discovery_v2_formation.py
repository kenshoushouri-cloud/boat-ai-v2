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

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "candidate_discovery_v2_formation_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v2_formation_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryV2Tests(unittest.TestCase):
    def entries(self):
        return [
            {
                "lane": lane,
                "racer_class": 3,
                "national_win_rate": 5.0 + lane * 0.15,
                "national_place2_rate": 32 + lane,
                "local_place2_rate": 29 + lane,
                "avg_st": 0.13 + lane * 0.006,
                "motor_place2_rate": 25 + lane * 3,
            }
            for lane in range(1, 7)
        ]

    def test_motor_adjust_is_normalized(self):
        base = mod.v1.ticket_probabilities(self.entries(), "12", 0.0)
        adjusted = mod.motor_adjust(base, self.entries())
        self.assertEqual(120, len(adjusted))
        self.assertTrue(math.isclose(sum(adjusted.values()), 1.0, abs_tol=1e-12))

    def test_race_metrics_include_top_ticket_formation(self):
        race = {"race_id": "R", "race_date": "2026-09-01", "venue_id": "12", "race_no": 7}
        probs = mod.v1.ticket_probabilities(self.entries(), "12", 0.0)
        metrics = mod.probability_metrics(race, probs, "BASE")
        self.assertEqual(120, len(metrics["ranked_tickets"]))
        self.assertGreater(metrics["head_p1"], 0)
        self.assertGreater(metrics["top3_mass"], 0)

    def test_source_has_no_odds_or_ev_selection(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("v2_odds_trifecta", text)
        self.assertNotIn("raw_ev", text)
        self.assertIn("set transaction read only", text)


if __name__ == "__main__":
    unittest.main()
