# -*- coding: utf-8 -*-
"""Offline integration check of the V5 research outcome/history VOID guard.

The V5 script is imported with a fake db_pg module. No DB, Railway,
network, Production selection or actual bets are touched.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from research.historical_void_registry import VERIFIED_VOID_RACE_IDS

PREFIX = "V5_LC_RF_EXRANK_RC_PLUS_OPPONENT_RESULT="

def load_research_module():
    fake_db = types.ModuleType("db_pg")
    fake_db.fetch_all = lambda *_args, **_kwargs: []
    script = Path(__file__).resolve().parents[1] / "research" / "v5_lc_rf_exrank_rc_plus_opponent_pg.py"
    spec = importlib.util.spec_from_file_location("_offline_v5_void_integration", script)
    mod = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"db_pg": fake_db}):
        spec.loader.exec_module(mod)
    return mod


class TestV5VoidIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v5 = load_research_module()

    def test_guard_exactly_excludes_71_and_preserves_completed_venue_races(self):
        normal = [
            {"race_id": "20260921_09_04", "winner": 4},
            {"race_id": "20260921_10_09", "winner": 1},
        ]
        fake_candidates = normal + [{"race_id": rid, "winner": 1} for rid in sorted(VERIFIED_VOID_RACE_IDS)]
        selected, skipped = self.v5.exclude_verified_void_rows(fake_candidates)
        self.assertEqual(skipped, 71)
        self.assertEqual(selected, normal)
        self.assertEqual(fake_candidates[:2], normal)  # No mutation

    def test_guard_fails_closed_without_provenance_key(self):
        for rows in ([{}], [{"race_id": None}], [{"race_id": 1234}]):
            with self.subTest(rows=rows):
                with self.assertRaises((KeyError, ValueError)):
                    self.v5.exclude_verified_void_rows(rows)

    def test_backtest_main_filters_both_outcomes_and_history(self):
        valid = ["20260921_09_04", "20260921_10_09"]
        cancelled = "20260921_09_05"
        race_rows = [
            {"race_id": valid[0], "race_date": "2026-09-21", "venue": "09", "winner": 4},
            {"race_id": valid[1], "race_date": "2026-09-21", "venue": "10", "winner": 1},
            # Deliberately incorrect legacy 'official' winner for a K-confirmed VOID:
            {"race_id": cancelled, "race_date": "2026-09-21", "venue": "09", "winner": 5},
        ]
        entry_rows = [
            {
                "race_id": rid, "lane": lane, "racer_number": 2000 + ix * 10 + lane,
                "racer_class": "A1", "recent_form": None, "exhibition_time_rank": lane,
            }
            for ix, rid in enumerate(valid + [cancelled])
            for lane in range(1, 7)
        ]
        hist_rows = [
            {
                "race_id": rid, "racer_number": 2000 + ix * 10 + lane,
                "start_course": lane, "finish_position": lane,
                "race_date": "2026-09-21",
            }
            for ix, rid in enumerate(valid)
            for lane in range(1, 7)
        ] + [{
            "race_id": cancelled, "racer_number": 9999,
            "start_course": 1, "finish_position": 1, "race_date": "2026-09-21",
        }]
        schema = {
            "v2_races": {"race_id", "race_date", "venue_code"},
            "v2_race_entries": {"race_id", "lane", "racer_number", "racer_class", "recent_form"},
            "v2_results": {"race_id", "first_lane", "result_status", "race_status"},
            "v2_realtime_exhibition_snapshots": {"race_id", "lane", "exhibition_time_rank"},
            "v2_result_entries": {"race_id", "racer_number", "start_course", "finish_position"},
        }

        def fake_fetch(sql, args):
            normalized = " ".join(sql.lower().split())
            if "information_schema.columns" in normalized:
                return [{"column_name": col} for col in sorted(schema[args[0]])]
            if "select r.race_id,r.race_date" in normalized:
                return race_rows
            if "select e.race_id,e.lane" in normalized:
                return entry_rows
            if "select re.race_id,re.racer_number" in normalized:
                return hist_rows
            raise AssertionError(f"Unexpected SQL: {normalized[:120]}")

        output = io.StringIO()
        with patch.object(self.v5, "fetch_all", side_effect=fake_fetch):
            with contextlib.redirect_stdout(output):
                self.v5.main()

        result_line = next(line for line in output.getvalue().splitlines() if line.startswith(PREFIX))
        report = json.loads(result_line[len(PREFIX):])
        self.assertEqual(report["period"], {"start": "2025-07-01", "end": "2026-10-05"})
        self.assertEqual(report["coverage"]["completed_races"], 2)
        self.assertEqual(report["coverage"]["scored"], 2)
        self.assertEqual(report["coverage"]["void_candidate_rows_excluded"], 1)
        self.assertEqual(report["coverage"]["void_history_rows_excluded"], 1)
        self.assertEqual(report["coverage"]["verified_void_registry_size"], 71)
        self.assertEqual(report["coverage"]["venue_count"], 2)
        self.assertEqual(set(report["venue_delta_logloss"]), {"09", "10"})


if __name__ == "__main__":
    unittest.main()
