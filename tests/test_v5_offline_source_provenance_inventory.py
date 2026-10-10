"""Pure fake-only source inventory checks; no DB/HTTP/deployment."""
import dataclasses
import unittest
from v5.offline_source_provenance_inventory import (
    DERIVED, MUTABLE, UNREVIEWED, REQUIRED_FEATURES, review_offline_source_provenance,
)


class StaticSourceInventoryTest(unittest.TestCase):
    def assert_hold(self, r):
        for key in (
            "original_first_observation_verified", "six_active_starts_confirmed",
            "selection_eligible", "beforeinfo_first_write_eligible",
            "forward_eligible", "buy_eligible",
        ):
            self.assertIs(getattr(r, key), False)
        self.assertEqual(r.approved_provenance_features, 0)
        self.assertTrue(all(x.independently_frozen_proof is False for x in r.features))

    def test_seven_feature_classification(self):
        r = review_offline_source_provenance()
        by = {x.feature: x.classification for x in r.features}
        self.assertEqual(set(by), REQUIRED_FEATURES)
        self.assertEqual(by["lane_class"], MUTABLE)
        self.assertEqual(by["exhibition_rank"], MUTABLE)
        for k in ("recent_form", "racer_course", "opponent", "venue_lane"):
            self.assertEqual(by[k], DERIVED)
        self.assertEqual(by["prior_day_k"], UNREVIEWED)
        self.assertEqual(dict(r.counts), {MUTABLE: 2, DERIVED: 4, UNREVIEWED: 1})
        self.assert_hold(r)

    def test_snapshot_timestamps_never_approve(self):
        r = review_offline_source_provenance({"lane_class": {
            "snapshot_at": "2026-10-10T09:00:00+09:00",
            "updated_at": "2026-10-10T09:01:00+09:00",
            "immutable": True, "forward_eligible": True,
        }})
        lane = next(x for x in r.features if x.feature == "lane_class")
        self.assertEqual(lane.classification, MUTABLE)
        self.assertIn("snapshot_at", lane.claimed_fields_ignored)
        self.assertIn("updated_at", lane.claimed_fields_ignored)
        self.assertIn("forward_eligible", lane.claimed_fields_ignored)
        self.assert_hold(r)

    def test_historical_upsert_cannot_become_freeze(self):
        r = review_offline_source_provenance({"exhibition_rank": {
            "historical_upsert": False, "original_frozen_at": "prior-to-cutoff",
            "raw_sha256": "a" * 64, "independent_auditor": True,
        }})
        x = next(z for z in r.features if z.feature == "exhibition_rank")
        self.assertEqual(x.classification, MUTABLE)
        self.assertEqual(len(x.claimed_fields_ignored), 4)
        self.assert_hold(r)

    def test_derived_claimed_freeze_not_verified(self):
        r = review_offline_source_provenance({
            x: {"source_observed_at": "fake", "feature_observed_at": "fake"}
            for x in ("recent_form", "racer_course", "opponent", "venue_lane")
        })
        self.assertEqual(sum(x.classification == DERIVED for x in r.features), 4)
        self.assert_hold(r)

    def test_prior_day_k_claims_do_not_change_unreviewed(self):
        r = review_offline_source_provenance({"prior_day_k": {
            "first_write_confirmed": True, "six_active_starts_confirmed": True,
        }})
        x = next(z for z in r.features if z.feature == "prior_day_k")
        self.assertEqual(x.classification, UNREVIEWED)
        self.assert_hold(r)

    def test_unknown_feature_or_bad_structure_fails_closed(self):
        for x in ({"unknown_feature": {}}, {"lane_class": True},
                  {123: {}}, {"lane_class": {4: "bad"}}, [], "all-safe"):
            with self.subTest(value=x):
                r = review_offline_source_provenance(x)
                self.assertEqual(r.status, "INVALID_UNTRUSTED_INPUT_HARD_HOLD")
                self.assertEqual(len(r.features), 7)
                self.assert_hold(r)

    def test_fields_are_names_only_no_payload_leak(self):
        secret = "never-output-this-caller-secret"
        r = review_offline_source_provenance({"exhibition_rank": {
            "snapshot_at": secret, "raw_sha256": secret, "random_metadata": secret,
        }})
        self.assertNotIn(secret, repr(r))
        self.assertNotIn("random_metadata", repr(r))
        self.assert_hold(r)

    def test_result_and_rows_immutable(self):
        r = review_offline_source_provenance()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.forward_eligible = True
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.features[0].classification = "APPROVED"
        self.assertIsInstance(r.features, tuple)
        self.assertIsInstance(r.counts, tuple)
        self.assert_hold(r)


if __name__ == "__main__":
    unittest.main()
