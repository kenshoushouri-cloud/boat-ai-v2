from __future__ import annotations

import importlib.util
from itertools import permutations
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research" / "candidate_discovery_bettype_contract.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_bettype_contract", PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def sample_trifecta() -> dict[str, float]:
    # Deterministic nonuniform distribution for contract tests.
    raw = {}
    for a, b, c in permutations(range(1, 7), 3):
        raw[f"{a}-{b}-{c}"] = (7 - a) * 100 + (7 - b) * 10 + (7 - c)
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


class BetTypeContractTests(unittest.TestCase):
    def test_frozen_grid(self):
        self.assertEqual(("trifecta", "exacta", "trio"), mod.BET_TYPES)
        self.assertEqual((1, 2, 3, 5), mod.FIXED_POINT_COUNTS)
        self.assertEqual((0.20, 0.35, 0.50), mod.COVERAGE_TARGETS)
        self.assertEqual(12, mod.COVERAGE_MAX_TICKETS)
        self.assertEqual(100, mod.STAKE_PER_TICKET_YEN)

    def test_derived_ticket_counts_and_mass(self):
        p = sample_trifecta()
        exacta = mod.exacta_from_trifecta(p)
        trio = mod.trio_from_trifecta(p)
        self.assertEqual(120, len(p))
        self.assertEqual(30, len(exacta))
        self.assertEqual(20, len(trio))
        self.assertAlmostEqual(1.0, sum(exacta.values()), places=12)
        self.assertAlmostEqual(1.0, sum(trio.values()), places=12)

    def test_exacta_is_sum_over_third_place(self):
        p = sample_trifecta()
        exacta = mod.exacta_from_trifecta(p)
        expected = sum(prob for ticket, prob in p.items() if ticket.startswith("1-2-"))
        self.assertAlmostEqual(expected, exacta["1-2"], places=14)

    def test_trio_is_sum_of_six_permutations(self):
        p = sample_trifecta()
        trio = mod.trio_from_trifecta(p)
        expected = sum(
            p[f"{a}-{b}-{c}"]
            for a, b, c in permutations((1, 2, 3), 3)
        )
        self.assertAlmostEqual(expected, trio["1-2-3"], places=14)

    def test_fixed_strategy_uses_100_yen_per_ticket(self):
        p = sample_trifecta()
        grid = mod.build_comparison_grid(p)
        row = next(x for x in grid if x["bet_type"] == "exacta" and x["strategy"] == "top5")
        self.assertEqual(5, row["ticket_count"])
        self.assertEqual(500, row["stake_yen"])

    def test_coverage_never_exceeds_cap(self):
        p = sample_trifecta()
        for bet_type in mod.BET_TYPES:
            q = mod.distribution_for_bet_type(p, bet_type)
            for target in mod.COVERAGE_TARGETS:
                tickets = mod.select_coverage(q, target)
                self.assertGreaterEqual(len(tickets), 1)
                self.assertLessEqual(len(tickets), mod.COVERAGE_MAX_TICKETS)

    def test_source_is_pure_and_does_not_use_market_or_results(self):
        text = PATH.read_text(encoding="utf-8").lower()
        for token in (
            "psycopg", "database_url", "requests", "railway", "line_notify",
            "raw_ev", "odds_min", "odds_max", "payout", "result_status"
        ):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
