from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research" / "candidate_discovery_late_bao_contract.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_late_bao_contract", PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryLateBaoContractTests(unittest.TestCase):
    def _odds(self):
        return {ticket: 8.0 + idx / 10.0 for idx, ticket in enumerate(mod.TICKETS)}

    def test_frozen_coefficients(self):
        self.assertEqual(0.06, mod.MOTOR_BETA)
        self.assertEqual(0.06, mod.EXHIBITION_BETA)
        self.assertEqual((1.0, 0.6, 0.3), mod.POS_W)

    def test_distribution_is_complete_and_normalized(self):
        probs = mod.bao_distribution(
            odds=self._odds(),
            motor_place2={1: 38.0, 2: 42.0, 3: 44.0, 4: 46.0, 5: 49.0, 6: 51.0},
            exhibition_time_rank={1: 2, 2: 1, 3: 3, 4: 4, 5: 6, 6: 5},
        )
        self.assertEqual(120, len(probs))
        self.assertAlmostEqual(1.0, sum(probs.values()), places=12)
        self.assertEqual(2, len(mod.top_tickets(probs)))

    def test_incomplete_market_fails_closed(self):
        odds = self._odds()
        odds.pop(next(iter(odds)))
        with self.assertRaises(ValueError):
            mod.bao_distribution(
                odds=odds,
                motor_place2={1: 38.0, 2: 42.0, 3: 44.0, 4: 46.0, 5: 49.0, 6: 51.0},
                exhibition_time_rank={1: 2, 2: 1, 3: 3, 4: 4, 5: 6, 6: 5},
            )

    def test_corroboration_never_removes_candidate(self):
        probs = mod.bao_distribution(
            odds=self._odds(),
            motor_place2={1: 38.0, 2: 42.0, 3: 44.0, 4: 46.0, 5: 49.0, 6: 51.0},
            exhibition_time_rank={1: 2, 2: 1, 3: 3, 4: 4, 5: 6, 6: 5},
        )
        top = mod.top_tickets(probs)
        result = mod.corroboration(v4_tickets=(top[0], "6-5-4"), bao_probs=probs)
        self.assertTrue(result["corroborated"])
        self.assertEqual(1, result["overlap_count"])
        self.assertFalse(result["candidate_removed"])
        self.assertFalse(result["purchase_action"])

    def test_source_has_no_integration_or_value_gate(self):
        text = PATH.read_text(encoding="utf-8").lower()
        for token in ("psycopg", "requests", "railway", "database_url", "raw_ev", "odds_min", "odds_max", "expected_value"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
