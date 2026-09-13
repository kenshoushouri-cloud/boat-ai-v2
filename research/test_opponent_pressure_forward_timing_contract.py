# -*- coding: utf-8 -*-
from datetime import date, datetime, timezone, timedelta
import unittest

from research.opponent_pressure_forward_timing_contract import (
    OpponentSnapshotEvidence,
    forward_eligibility,
)

JST = timezone(timedelta(hours=9))
D = date(2026, 9, 11)


def ev(**changes):
    values = dict(
        race_date=D,
        deadline_at=datetime(2026, 9, 11, 10, 30, tzinfo=JST),
        created_at=datetime(2026, 9, 11, 7, 45, tzinfo=JST),
        updated_at=datetime(2026, 9, 11, 7, 45, tzinfo=JST),
        train_end=date(2026, 9, 10),
        model_version=2,
        matched_opponents=(5, 5, 5, 5, 5, 5),
    )
    values.update(changes)
    return OpponentSnapshotEvidence(**values)


class TimingContractTest(unittest.TestCase):
    def test_accepts_timing_clean_snapshot(self):
        self.assertEqual(forward_eligibility(ev()), (True, "timing_clean"))

    def test_missing_fails_closed(self):
        self.assertEqual(forward_eligibility(None), (False, "missing_snapshot"))

    def test_rejects_post_cutoff_create(self):
        self.assertEqual(
            forward_eligibility(ev(created_at=datetime(2026, 9, 11, 8, 15, 1, tzinfo=JST), updated_at=datetime(2026, 9, 11, 8, 15, 1, tzinfo=JST)))[1],
            "created_after_cutoff",
        )

    def test_rejects_safe_create_late_update(self):
        self.assertEqual(
            forward_eligibility(ev(updated_at=datetime(2026, 9, 11, 8, 16, tzinfo=JST)))[1],
            "updated_after_cutoff",
        )

    def test_rejects_at_deadline(self):
        t = datetime(2026, 9, 11, 8, 0, tzinfo=JST)
        self.assertEqual(
            forward_eligibility(ev(deadline_at=t, created_at=t, updated_at=t))[1],
            "created_at_or_after_deadline",
        )

    def test_rejects_updated_at_deadline(self):
        self.assertEqual(
            forward_eligibility(ev(deadline_at=datetime(2026, 9, 11, 8, 10, tzinfo=JST), updated_at=datetime(2026, 9, 11, 8, 10, tzinfo=JST)))[1],
            "updated_at_or_after_deadline",
        )

    def test_rejects_stale_training_boundary(self):
        self.assertEqual(forward_eligibility(ev(train_end=date(2026, 9, 9)))[1], "train_end_mismatch")

    def test_rejects_model_version_mismatch(self):
        self.assertEqual(forward_eligibility(ev(model_version=1))[1], "model_version_mismatch")

    def test_rejects_incomplete_opponent_coverage(self):
        self.assertEqual(forward_eligibility(ev(matched_opponents=(5, 5, 3, 5, 5, 5)))[1], "opponent_coverage_incomplete")

    def test_rejects_wrong_snapshot_date(self):
        self.assertEqual(
            forward_eligibility(ev(created_at=datetime(2026, 9, 10, 7, 45, tzinfo=JST)))[1],
            "snapshot_date_mismatch",
        )

    def test_rejects_timestamp_without_timezone(self):
        self.assertEqual(
            forward_eligibility(ev(created_at=datetime(2026, 9, 11, 7, 45)))[1],
            "invalid_timestamp",
        )

    def test_rejects_reverse_mutation_clock(self):
        self.assertEqual(
            forward_eligibility(ev(updated_at=datetime(2026, 9, 11, 7, 44, tzinfo=JST)))[1],
            "updated_before_created",
        )


if __name__ == "__main__":
    unittest.main()
