from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

psycopg = types.ModuleType("psycopg")
psycopg.rows = types.ModuleType("psycopg.rows")
psycopg.rows.dict_row = object()
sys.modules.setdefault("psycopg", psycopg)
sys.modules.setdefault("psycopg.rows", psycopg.rows)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "candidate_discovery_frozen_eval_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_frozen_eval_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class CandidateDiscoveryFrozenEvalTests(unittest.TestCase):
    def test_ticket_normalization(self):
        self.assertEqual("1-2-3", mod.norm_ticket("1=2-3"))
        self.assertEqual("", mod.norm_ticket("1-1-2"))
        self.assertEqual("", mod.norm_ticket(None))

    def test_sha_sidecar_contract(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "feed.json"
            p.write_text('{"a":1}\n', encoding="utf-8")
            digest = mod.file_sha256(p)
            side = Path(str(p) + ".sha256")
            side.write_text(f"{digest}  {p.name}\n", encoding="utf-8")
            self.assertEqual(digest, mod.expected_sha256(side))

    def test_evaluate_uses_only_frozen_tickets(self):
        feed = [
            {"race_id": "r1", "tier": "A", "tickets": [{"ticket": "1-2-3"}, {"ticket": "1-3-2"}]},
            {"race_id": "r2", "tier": "B", "tickets": [{"ticket": "2-1-3"}]},
            {"race_id": "r3", "tier": "L", "tickets": [{"ticket": "3-1-2"}]},
        ]
        results = {
            "r1": {"trifecta_ticket": "1-3-2", "trifecta_payout_yen": 850},
            "r2": {"trifecta_ticket": "6-5-4", "trifecta_payout_yen": 12000},
        }
        out = mod.evaluate(feed, results)
        self.assertEqual(2, out["evaluated_races"])
        self.assertEqual(1, out["missing_results"])
        self.assertEqual(3, out["tickets"])
        self.assertEqual(1, out["hits"])
        self.assertEqual(300, out["investment_yen"])
        self.assertEqual(850, out["return_yen"])
        self.assertAlmostEqual(283.333, out["roi_pct"], places=3)

    def _feed_doc(self, contract: str, *, eligible: bool = False):
        doc = {
            "contract": contract,
            "mutation_performed": False,
            "line_sent": False,
            "purchase_action": False,
            "summary": {"scheduled_races": 10, "core_races": 6},
            "feed": [{"race_id": "r1", "tickets": [{"ticket": "1-2-3"}]}],
        }
        if eligible:
            doc["prospective_evidence_eligible"] = True
            doc["freeze_provenance"] = {
                "mode": "prospective",
                "prospective_evidence_eligible": True,
            }
        return doc

    def test_validate_accepts_baseline_without_prospective_flag(self):
        baseline = self._feed_doc("candidate_discovery_main_feed_v1")
        self.assertEqual(1, len(mod.validate_frozen_feed(baseline)))

    def test_validate_v4_requires_timestamp_proven_prospective_freeze(self):
        unproven = self._feed_doc("candidate_discovery_v4_main_feed_v1")
        with self.assertRaises(RuntimeError):
            mod.validate_frozen_feed(unproven)
        proven = self._feed_doc("candidate_discovery_v4_main_feed_v1", eligible=True)
        self.assertEqual(1, len(mod.validate_frozen_feed(proven)))

    def test_unknown_contract_fails_closed(self):
        with self.assertRaises(RuntimeError):
            mod.validate_frozen_feed(self._feed_doc("unknown_feed"))

    def test_validate_frozen_feed_fail_closed(self):
        bad = self._feed_doc("candidate_discovery_main_feed_v1")
        bad = json.loads(json.dumps(bad))
        bad["purchase_action"] = True
        with self.assertRaises(RuntimeError):
            mod.validate_frozen_feed(bad)

    def test_source_requires_official_positive_results(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertIn("result_status='official'", text)
        self.assertIn("race_status='official'", text)
        self.assertIn("trifecta_payout_yen > 0", text)
        self.assertIn('item.get("result_status") != "official"', text)
        self.assertIn('item.get("race_status") != "official"', text)

    def test_source_is_read_only(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertIn("set transaction read only", text)
        self.assertIn("candidate_discovery_v4_main_feed_v1", text)
        self.assertIn("prospective_evidence_eligible", text)
        self.assertIn("freeze_provenance", text)
        for token in (
            "delete from ", "insert into ", "update v2_", "alter table ",
            "drop table ", "truncate ", "vacuum ", "create table ",
        ):
            self.assertNotIn(token, text)
        self.assertIn('"purchase_action": false', text)


if __name__ == "__main__":
    unittest.main()
