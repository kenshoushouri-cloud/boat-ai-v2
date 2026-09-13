# -*- coding: utf-8 -*-
from pathlib import Path
import unittest


SCRIPT = Path("research/candidate_discovery_market_forward_annotate_pg.py")


class CandidateDiscoveryMarketForwardAnnotateSafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8").lower()

    def test_requires_immutable_freeze_identity(self) -> None:
        self.assertIn("candidate_v4_freeze_sha256", self.text)
        self.assertIn("candidate_v4_freeze_run_id", self.text)
        self.assertIn("candidate_v4_freeze_artifact_id", self.text)
        self.assertIn("freeze sha-256 mismatch", self.text)
        self.assertIn("extract_core_top1", self.text)
        self.assertIn("prospective_start", self.text)
        self.assertNotIn("20260913_11_02", self.text)

    def test_database_contract_is_read_only_and_outcome_free(self) -> None:
        self.assertIn("set transaction read only", self.text)
        self.assertIn("v2_realtime_odds_snapshots", self.text)
        self.assertNotIn("v2_results", self.text)
        for forbidden in (
            "trifecta_payout_yen",
            "result_status",
            "race_status",
            "delete from ",
            "insert into ",
            "update v2_",
            "alter table ",
            "drop table ",
            "truncate ",
            "vacuum ",
            "create table ",
        ):
            self.assertNotIn(forbidden, self.text, forbidden)

    def test_annotation_never_authorizes_purchase_or_promotion(self) -> None:
        self.assertIn('"purchase_action": false', self.text)
        self.assertIn('"production_behavior_changed": false', self.text)
        self.assertIn('"promotion_allowed": false', self.text)
        self.assertIn("block_research_only", self.text)
        self.assertIn("annotate_feed", self.text)


if __name__ == "__main__":
    unittest.main()
