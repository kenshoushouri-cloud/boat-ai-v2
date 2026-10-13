#!/usr/bin/env python3
"""Pure-stdlib checks; this file never connects to the production system."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v5_offline_dag import STAGES, Evidence, UnsafePlan, gate, validate_dag


NOW = datetime(2026, 10, 14, 9, 10, tzinfo=timezone(timedelta(hours=9)))


def good_evidence() -> Evidence:
    return Evidence(
        deadline_at=NOW + timedelta(minutes=8),
        captured_at=NOW,
        roster_complete=True,
        beforeinfo_complete=True,
        odds_complete=True,
        captured_before_decision_proven=True,
        source_is_historical_replay=False,
        already_frozen=False,
    )


class TestDAG(unittest.TestCase):
    def test_order_matches_dependencies(self):
        order = validate_dag(STAGES)
        self.assertEqual(len(order), 8)
        names = {s.name: s for s in STAGES}
        for i, name in enumerate(order):
            self.assertTrue(set(names[name].needs) <= set(order[:i]))

    def test_forward_stages_before_result_capture(self):
        order = validate_dag(STAGES)
        self.assertLess(order.index("v5_shadow_predict"), order.index("result_capture"))

    def test_dag_is_not_executable(self):
        self.assertTrue(all(s.mode != "enabled" for s in STAGES))

    def test_duplicate_stage_fail_closed(self):
        with self.assertRaisesRegex(UnsafePlan, "duplicate"):
            validate_dag((*STAGES, STAGES[0]))

    def test_cycle_fail_closed(self):
        mutated = [replace(s, needs=("result_audit",)) if s.name == "roster_prepare" else s for s in STAGES]
        with self.assertRaises(UnsafePlan):
            validate_dag(mutated)

    def test_result_data_not_upstream_of_shadow(self):
        mutated = [replace(s, needs=("result_capture",)) if s.name == "v5_shadow_predict" else s for s in STAGES]
        with self.assertRaises(UnsafePlan):
            validate_dag(mutated)

    def test_no_unknown_new_execution_stage(self):
        with self.assertRaises(UnsafePlan):
            validate_dag((*STAGES, replace(STAGES[0], name="buy_now")))

    def test_ready_is_only_shadow(self):
        self.assertEqual(gate(good_evidence()), "READY_SHADOW_ONLY_BUY_HARD_HOLD")

    def test_missing_beforeinfo(self):
        self.assertEqual(gate(replace(good_evidence(), beforeinfo_complete=False)), "SKIP_MISSING_BEFOREINFO")

    def test_missing_odds(self):
        self.assertEqual(gate(replace(good_evidence(), odds_complete=False)), "SKIP_MISSING_ODDS")

    def test_missing_roster(self):
        self.assertEqual(gate(replace(good_evidence(), roster_complete=False)), "SKIP_MISSING_ROSTER")

    def test_no_timestamp(self):
        self.assertEqual(gate(replace(good_evidence(), captured_at=None)), "SKIP_MISSING_CAPTURE_PROOF")

    def test_no_proven_freeze(self):
        self.assertEqual(gate(replace(good_evidence(), captured_before_decision_proven=False)), "SKIP_MISSING_CAPTURE_PROOF")

    def test_capture_at_deadline_not_allowed(self):
        x = good_evidence()
        self.assertEqual(gate(replace(x, captured_at=x.deadline_at)), "SKIP_LATE_CAPTURE")

    def test_delayed_capture_not_allowed(self):
        x = good_evidence()
        self.assertEqual(gate(replace(x, captured_at=x.deadline_at + timedelta(seconds=1))), "SKIP_LATE_CAPTURE")

    def test_historical_not_forward(self):
        self.assertEqual(gate(replace(good_evidence(), source_is_historical_replay=True)), "SKIP_HISTORICAL_NOT_FORWARD")

    def test_duplicate_freeze(self):
        self.assertEqual(gate(replace(good_evidence(), already_frozen=True)), "SKIP_ALREADY_FROZEN")

    def test_naive_time_not_accepted(self):
        self.assertEqual(gate(replace(good_evidence(), captured_at=NOW.replace(tzinfo=None))), "SKIP_MISSING_CAPTURE_PROOF")

    def test_cli_plan_no_exec(self):
        proc = subprocess.run([sys.executable, str(Path(__file__).with_name("v5_offline_dag.py")), "--race-date", "2026-10-14"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("V5_DAG=OFFLINE_PLAN_ONLY", proc.stdout)
        self.assertIn("V5_DAG_PRODUCTION_READY=NO", proc.stdout)

    def test_cli_bad_date_rejected(self):
        proc = subprocess.run([sys.executable, str(Path(__file__).with_name("v5_offline_dag.py")), "--race-date", "2026-02-30"], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
