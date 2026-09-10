from __future__ import annotations

from datetime import datetime, timezone, timedelta
import importlib.util
import os
from pathlib import Path
import unittest

os.environ.setdefault("TARGET_DATE", "2026-09-11")

SCRIPT = Path(__file__).with_name("opponent_pressure_shadow_v2_compact.py")
spec = importlib.util.spec_from_file_location("opp_pressure_v2", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

JST = timezone(timedelta(hours=9))


def meta(deadline: datetime | None = None):
    return {
        "race": {
            "race_date": mod.TARGET_DATE,
            "venue_id": "01",
            "race_no": 1,
            "deadline_at": deadline or datetime(2026, 9, 11, 8, 32, tzinfo=JST),
        }
    }


class TimingGuardTest(unittest.TestCase):
    def test_accepts_pre_cutoff_pre_deadline(self):
        observed = mod._assert_forward_write_window(
            meta(), datetime(2026, 9, 11, 7, 0, tzinfo=JST)
        )
        self.assertEqual(observed.hour, 7)

    def test_rejects_exact_cutoff(self):
        with self.assertRaisesRegex(RuntimeError, "cutoff reached"):
            mod._assert_forward_write_window(
                meta(), datetime(2026, 9, 11, 8, 15, tzinfo=JST)
            )

    def test_rejects_crossed_race_deadline(self):
        with self.assertRaisesRegex(RuntimeError, "race deadline reached"):
            mod._assert_forward_write_window(
                meta(datetime(2026, 9, 11, 7, 0, tzinfo=JST)),
                datetime(2026, 9, 11, 7, 1, tzinfo=JST),
            )

    def test_rejects_missing_deadline(self):
        bad = meta()
        bad["race"]["deadline_at"] = None
        with self.assertRaisesRegex(RuntimeError, "missing/naive race deadline"):
            mod._assert_forward_write_window(
                bad, datetime(2026, 9, 11, 7, 0, tzinfo=JST)
            )

    def test_rejects_wrong_target_date(self):
        with self.assertRaisesRegex(RuntimeError, "target date mismatch"):
            mod._assert_forward_write_window(
                meta(), datetime(2026, 9, 12, 7, 0, tzinfo=JST)
            )

    def test_rejects_naive_observation_time(self):
        with self.assertRaisesRegex(RuntimeError, "timezone-aware"):
            mod._assert_forward_write_window(meta(), datetime(2026, 9, 11, 7, 0))

    def test_rejects_naive_deadline(self):
        with self.assertRaisesRegex(RuntimeError, "missing/naive race deadline"):
            mod._assert_forward_write_window(
                meta(datetime(2026, 9, 11, 8, 32)),
                datetime(2026, 9, 11, 7, 0, tzinfo=JST),
            )


if __name__ == "__main__":
    unittest.main()
