"""Synthetic-only tests: no DB, network or official K fetch."""
from __future__ import annotations
import unittest

from v5.k_detail_backfill_gate_20261026 import (
    EXPECTED_RACES, CANCELLED_IDS, EXPECTED_TOTAL_RACES,
    EXPECTED_TOTAL_LANES, KDayGate, validate_day, validate_complete_batch,
)


def fixture(day):
    prefix = day.replace("-", "")
    cancel = set(CANCELLED_IDS.get(day, ()))
    n = EXPECTED_RACES[day]
    parsed = []
    i = 1
    while len(parsed) < n:
        venue = (i - 1) // 12 + 1
        race = (i - 1) % 12 + 1
        rid = f"{prefix}_{venue:02d}_{race:02d}"
        i += 1
        if rid in cancel:
            continue
        parsed.append({
            "race_id": rid,
            "parse_failed_candidate_lines": [],
            "entries": [{"lane": lane} for lane in range(1, 7)],
        })
    known = {
        x["race_id"]: {
            "result_status": "finished",
            "trifecta_ticket": "123",
            "trifecta_payout_yen": 120,
        }
        for x in parsed
    }
    for rid in cancel:
        known[rid] = {
            "result_status": "cancelled",
            "trifecta_ticket": None,
            "trifecta_payout_yen": 0,
        }
    return known, parsed


class KBackfillGateTests(unittest.TestCase):
    def test_all_days_and_exact_total(self):
        gates = []
        for day in EXPECTED_RACES:
            known, parsed = fixture(day)
            gates.append(validate_day(day, known, parsed))
        self.assertTrue(validate_complete_batch(gates))
        self.assertEqual(sum(x.k_races for x in gates), EXPECTED_TOTAL_RACES)
        self.assertEqual(sum(x.expected_lanes for x in gates), EXPECTED_TOTAL_LANES)

    def test_cancelled_race_cannot_be_treated_as_run(self):
        known, parsed = fixture("2026-10-25")
        known["20261025_20_12"]["result_status"] = "finished"
        with self.assertRaisesRegex(ValueError, "confirmed cancelled"):
            validate_day("2026-10-25", known, parsed)

    def test_unexpected_missing_race_fails(self):
        known, parsed = fixture("2026-10-22")
        known["20261022_21_01"] = {"result_status": "cancelled",
                                   "trifecta_ticket": None,
                                   "trifecta_payout_yen": 0}
        with self.assertRaisesRegex(ValueError, "unexpected absent"):
            validate_day("2026-10-22", known, parsed)

    def test_duplicate_lanes_fails(self):
        known, parsed = fixture("2026-10-15")
        parsed[0]["entries"][0]["lane"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate/missing lanes"):
            validate_day("2026-10-15", known, parsed)

    def test_parser_failed_line_fails(self):
        known, parsed = fixture("2026-10-16")
        parsed[0]["parse_failed_candidate_lines"] = ["unparsed"]
        with self.assertRaisesRegex(ValueError, "parser incomplete"):
            validate_day("2026-10-16", known, parsed)

    def test_race_duplicate_fails(self):
        known, parsed = fixture("2026-10-23")
        parsed[0]["race_id"] = parsed[1]["race_id"]
        with self.assertRaisesRegex(ValueError, "duplicate K race ID"):
            validate_day("2026-10-23", known, parsed)

    def test_cancelled_ticket_must_be_null(self):
        known, parsed = fixture("2026-10-21")
        known["20261021_03_12"]["trifecta_ticket"] = "123"
        with self.assertRaisesRegex(ValueError, "confirmed cancelled"):
            validate_day("2026-10-21", known, parsed)

    def test_disallow_out_of_scope_day(self):
        with self.assertRaisesRegex(ValueError, "scope"):
            validate_day("2026-10-26", {}, [])

    def test_missing_day_batch_fails(self):
        gates = []
        for day in list(EXPECTED_RACES)[:-1]:
            known, parsed = fixture(day)
            gates.append(validate_day(day, known, parsed))
        with self.assertRaisesRegex(ValueError, "dates"):
            validate_complete_batch(gates)


if __name__ == "__main__":
    unittest.main()
