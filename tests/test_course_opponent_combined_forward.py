# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "course_opponent_combined_forward.py"
spec = importlib.util.spec_from_file_location("course_opp_combined", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CombinedForwardMathTests(unittest.TestCase):
    def test_ticket_contract_is_exact_120(self):
        self.assertEqual(len(mod.TICKETS), 120)
        self.assertEqual(len(set(mod.TICKETS)), 120)
        self.assertEqual(set(mod.HEAD_INDEX), set(range(6)))

    def test_zero_pressure_delta_is_identity(self):
        probs = [1.0 / 120.0] * 120
        out = mod.apply_first_place_delta(probs, [0.0] * 6)
        self.assertAlmostEqual(sum(out), 1.0, places=12)
        for a, b in zip(probs, out):
            self.assertAlmostEqual(a, b, places=12)

    def test_pressure_changes_only_first_marginal(self):
        probs = [float(i + 1) for i in range(120)]
        probs = [x / sum(probs) for x in probs]
        delta = [0.03, -0.01, -0.005, -0.005, -0.005, -0.005]
        out = mod.apply_first_place_delta(probs, delta)
        self.assertAlmostEqual(sum(out), 1.0, places=12)
        self.assertTrue(all(math.isfinite(x) and x > 0 for x in out))

        # Within each first-place lane, every ticket receives the same factor,
        # so P(second,third | first) is preserved exactly.
        for head in range(6):
            idxs = [i for i, h in enumerate(mod.HEAD_INDEX) if h == head]
            factors = [out[i] / probs[i] for i in idxs]
            self.assertLess(max(factors) - min(factors), 1e-12)

    def test_target_first_marginal_matches_fixed_delta_rule(self):
        probs = [1.0 / 120.0] * 120
        delta = [0.05, -0.01, -0.01, -0.01, -0.01, -0.01]
        out = mod.apply_first_place_delta(probs, delta)
        got = mod.first_marginal(out)
        expected = mod.normalize([1.0 / 6.0 + d for d in delta])
        for a, b in zip(got, expected):
            self.assertAlmostEqual(a, b, places=12)

    def test_bad_dimensions_fail_closed(self):
        with self.assertRaises(ValueError):
            mod.apply_first_place_delta([1.0 / 119.0] * 119, [0.0] * 6)
        with self.assertRaises(ValueError):
            mod.apply_first_place_delta([1.0 / 120.0] * 120, [0.0] * 5)

    def test_metric_rank_tie_break_is_deterministic(self):
        probs = [1.0 / 120.0] * 120
        actual = mod.TICKETS[9]
        ll, brier, rank = mod.metric(probs, actual)
        self.assertTrue(math.isfinite(ll))
        self.assertTrue(math.isfinite(brier))
        self.assertEqual(rank, 10.0)

    def test_valid_probs_rejects_nonfinite_negative_and_wrong_sum(self):
        self.assertTrue(mod.valid_probs([1.0 / 120.0] * 120, 120))
        bad = [1.0 / 120.0] * 120; bad[0] = float("nan")
        self.assertFalse(mod.valid_probs(bad, 120))
        bad = [1.0 / 120.0] * 120; bad[0] = -0.1
        self.assertFalse(mod.valid_probs(bad, 120))
        self.assertFalse(mod.valid_probs([0.5] * 120, 120))

    def test_course_integrity_accepts_valid_frozen_row(self):
        jst = timezone(timedelta(hours=9))
        d = date(2026, 9, 10)
        row = {
            "race_date": d,
            "deadline_at": datetime(2026, 9, 10, 12, 0, tzinfo=jst),
            "snapshot_at": datetime(2026, 9, 10, 9, 0, tzinfo=jst),
            "course_model_version": 1,
            "course_coef": 0.50,
            "source_cutoff_jst": "08:15",
            "ticket_order_version": "lexicographic_lane_loop_120_fixed_v1",
            "course_top3_rates": [50.0] * 6,
            "base_probs": [1.0 / 120.0] * 120,
            "course_probs": [1.0 / 120.0] * 120,
            "minutes_before": 180.0,
            "course_snapshot_ats": [datetime(2026, 9, 10, 7, 30, tzinfo=jst)] * 6,
        }
        self.assertTrue(mod.course_integrity(row))
        row["course_snapshot_ats"] = [datetime(2026, 9, 10, 8, 16, tzinfo=jst)] * 6
        self.assertFalse(mod.course_integrity(row))

    def test_opponent_integrity_requires_pre_deadline_creation_and_prior_train_end(self):
        jst = timezone(timedelta(hours=9))
        d = date(2026, 9, 10)
        row = {
            "race_date": d,
            "deadline_at": datetime(2026, 9, 10, 12, 0, tzinfo=jst),
            "opp_created_at": datetime(2026, 9, 10, 7, 0, tzinfo=jst),
            "opp_model_version": 2,
            "train_end": date(2026, 9, 9),
            "matched_opponents": [5] * 6,
            "base_win": [0.16] * 6,
            "adj_win": [0.17] * 6,
        }
        self.assertTrue(mod.opponent_integrity(row))
        row["train_end"] = d
        self.assertFalse(mod.opponent_integrity(row))
        row["train_end"] = date(2026, 9, 9)
        row["opp_created_at"] = datetime(2026, 9, 10, 12, 1, tzinfo=jst)
        self.assertFalse(mod.opponent_integrity(row))

    def test_source_has_no_sql_write_calls(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        forbidden = (
            'cur.execute("insert', 'cur.execute("update', 'cur.execute("delete',
            'cur.execute("alter', 'cur.execute("create', 'cur.execute("drop',
            "cur.execute('insert", "cur.execute('update", "cur.execute('delete",
            "cur.execute('alter", "cur.execute('create", "cur.execute('drop",
        )
        for token in forbidden:
            self.assertNotIn(token, text)
        self.assertIn('cur.execute("set transaction read only")', text)


if __name__ == "__main__":
    unittest.main()
