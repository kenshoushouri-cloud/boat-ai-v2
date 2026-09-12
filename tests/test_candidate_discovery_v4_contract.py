from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research" / "candidate_discovery_v4_contract.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v4_contract", PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryV4ContractTests(unittest.TestCase):
    def test_constants_are_frozen(self):
        self.assertEqual(0.50, mod.COURSE_COEF)
        self.assertEqual(0.06, mod.MOTOR_BETA)
        self.assertEqual(2.20, mod.PROB_TEMP)

    def test_missing_course_lane_is_neutral(self):
        base = {lane: float(lane) for lane in mod.LANES}
        course = {1: 40.0, 2: 50.0, 3: 60.0, 4: 55.0, 5: 45.0}
        adjusted = mod.course_adjust_raw(base, course)
        self.assertEqual(base[6], adjusted[6])
        self.assertNotEqual(base[1], adjusted[1])

    def test_distribution_is_120_and_normalized(self):
        base = {1: 2.0, 2: 1.5, 3: 1.0, 4: 0.5, 5: 0.0, 6: -0.5}
        course = {1: 52.0, 2: 48.0, 3: 45.0, 4: 43.0, 5: 40.0, 6: 38.0}
        motor = {1: 40.0, 2: 42.0, 3: 44.0, 4: 46.0, 5: 48.0, 6: 50.0}
        probs = mod.build_v4_distribution(base_raw=base, course_top3=course, motor_place2=motor)
        self.assertEqual(120, len(probs))
        self.assertAlmostEqual(1.0, sum(probs.values()), places=12)
        self.assertEqual(2, len(mod.top_tickets(probs, 2)))

    def test_source_has_no_integration_or_value_gate(self):
        text = PATH.read_text(encoding="utf-8").lower()
        for token in ("psycopg", "requests", "railway", "line_notify", "database_url", "raw_ev", "odds_min", "odds_max"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
