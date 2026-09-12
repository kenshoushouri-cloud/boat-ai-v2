from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class LearningOddsOnlyModeContractTest(unittest.TestCase):
    def test_learning_wrapper_requires_explicit_opt_in(self):
        body = text("run_learning_all_realtime_pg.py")
        self.assertIn('os.getenv("LEARNING_ODDS_ONLY", "0")', body)
        self.assertIn('env["ODDS_ONLY_MODE"] = "1" if odds_only else "0"', body)
        self.assertIn('env["COLLECT_SCOPE"] = "all"', body)
        self.assertIn('os.getenv("LEARNING_SNAPSHOT_LABEL", "learning_all")', body)
        self.assertIn('"/tmp/v21_learning_all_target_race_ids.txt"', body)

    def test_final_chain_does_not_enable_odds_only_mode(self):
        for path in (
            "run_final_pg.py",
            "v25_final_realtime_pipeline_pg.py",
        ):
            body = text(path)
            self.assertNotIn("ODDS_ONLY_MODE", body, path)
            self.assertNotIn("LEARNING_ODDS_ONLY", body, path)

    def test_odds_only_skips_beforeinfo_but_keeps_odds_fetch(self):
        body = text("v21_realtime_collector_pg_safe.py")
        self.assertIn('_env_flag("ODDS_ONLY_MODE", "0")', body)
        self.assertIn("if not odds_only_mode:", body)
        self.assertIn(
            'legacy._official_url("beforeinfo", legacy.TARGET_DATE, venue, race_no)',
            body,
        )
        self.assertIn(
            'legacy._official_url("odds3t", legacy.TARGET_DATE, venue, race_no)',
            body,
        )
        self.assertIn("skipped_odds_only", body)

        before_idx = body.index('legacy._official_url("beforeinfo"')
        odds_idx = body.index('legacy._official_url("odds3t"')
        gate_idx = body.rfind("if not odds_only_mode:", 0, before_idx)
        self.assertGreater(gate_idx, 0)
        self.assertLess(gate_idx, before_idx)
        self.assertLess(before_idx, odds_idx)

        # The odds request is outside the guarded beforeinfo block: same 8-space
        # loop indentation as the guard itself, not the 12-space guarded body.
        odds_request_line = next(
            line
            for line in body.splitlines()
            if 'legacy._official_url("odds3t"' in line
        )
        self.assertTrue(odds_request_line.startswith("            legacy._official_url"))
        odds_assignment_line = body.splitlines()[
            body.splitlines().index(odds_request_line) - 1
        ]
        self.assertEqual(odds_assignment_line, "        odds_html = legacy._fetch(")

    def test_all_non_odds_save_paths_remain_inside_default_full_mode(self):
        body = text("v21_realtime_collector_pg_safe.py")
        gate = body.index("        if not odds_only_mode:")
        odds = body.index("        odds_html = legacy._fetch(", gate)
        guarded = body[gate:odds]
        for token in (
            "save_weather(",
            "save_exhibition_and_entries(",
            "save_beforeinfo_extra(",
            'legacy._official_url("beforeinfo"',
        ):
            self.assertIn(token, guarded)
        self.assertNotIn('legacy._official_url("odds3t"', guarded)

    def test_odds_feature_semantics_are_left_cross_label(self):
        safe = text("v21_realtime_collector_pg_safe.py")
        self.assertIn("prev = legacy._fetch_previous_odds(rid)", safe)
        self.assertIn('"is_odds_drift": bool(', safe)
        self.assertIn('"is_odds_steam": bool(', safe)

        legacy = text("v21_realtime_collector_pg.py")
        start = legacy.index("def _fetch_previous_odds")
        end = legacy.index("def _infer_venue_style", start)
        lookup = legacy[start:end]
        self.assertIn("v2_realtime_odds_snapshots where race_id=%s", lookup)
        self.assertNotIn("snapshot_label", lookup)

    def test_learning_wrapper_remains_collection_only(self):
        body = text("run_learning_all_realtime_pg.py").lower()
        for token in (
            "v22_realtime_decision_engine_pg.py",
            "run_v22_targeted_pg.py",
            "v23_line_notifier_batch_pg.py",
            "send_line",
            "purchase_action",
        ):
            self.assertNotIn(token.lower(), body)


if __name__ == "__main__":
    unittest.main()
