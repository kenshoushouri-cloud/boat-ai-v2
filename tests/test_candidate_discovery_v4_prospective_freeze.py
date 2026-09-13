from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "candidate_discovery_v4_prospective_freeze_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v4_prospective_freeze_pg", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

JST = timezone(timedelta(hours=9))


def feed_doc(*, scheduled: int = 12, evaluable: int = 12, legacy_deadline: str = "2026-09-14T10:00:00+09:00"):
    feed = []
    for rank in range(1, 7):
        feed.append({
            "race_id": f"core-{rank}",
            "race_date": "2026-09-14",
            "venue_id": "08",
            "race_no": rank,
            "deadline_at": f"2026-09-14T{10 + rank:02d}:00:00+09:00",
            "daily_rank": rank,
            "legacy_carryover": False,
            "tickets": [
                {"ticket": "1-2-3", "core_order": 1, "source": ["DISCOVERY_CORE"]},
                {"ticket": "1-3-2", "core_order": 2, "source": ["DISCOVERY_CORE"]},
            ],
        })
    feed.append({
        "race_id": "legacy-1",
        "race_date": "2026-09-14",
        "venue_id": "10",
        "race_no": 1,
        "deadline_at": legacy_deadline,
        "daily_rank": None,
        "legacy_carryover": True,
        "tickets": [{"ticket": "1-6-5", "core_order": None, "source": ["LEGACY"]}],
    })
    return {
        "contract": mod.V4_CONTRACT,
        "summary": {
            "scheduled_races": scheduled,
            "evaluable_races": evaluable,
            "core_races": 6,
            "core_tickets": 12,
        },
        "feed": feed,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }


class CandidateDiscoveryV4ProspectiveFreezeTests(unittest.TestCase):
    def setUp(self):
        self.old_target = mod.TARGET_DATE
        mod.TARGET_DATE = date(2026, 9, 14)

    def tearDown(self):
        mod.TARGET_DATE = self.old_target

    def test_start_requires_target_day_and_after_0815(self):
        cutoff = mod._validate_start(datetime(2026, 9, 14, 8, 15, tzinfo=JST))
        self.assertEqual(datetime(2026, 9, 14, 8, 15, tzinfo=JST), cutoff)
        with self.assertRaises(RuntimeError):
            mod._validate_start(datetime(2026, 9, 14, 8, 14, 59, tzinfo=JST))
        with self.assertRaises(RuntimeError):
            mod._validate_start(datetime(2026, 9, 15, 8, 16, tzinfo=JST))

    def test_generated_feed_requires_complete_universe(self):
        good = feed_doc()
        core = mod._validate_generated(good)
        self.assertEqual(6, len(core))
        with self.assertRaises(RuntimeError):
            mod._validate_generated(feed_doc(evaluable=11))

    def test_finish_must_precede_earliest_feed_deadline_not_only_core(self):
        data = feed_doc(legacy_deadline="2026-09-14T10:00:00+09:00")
        core = mod._validate_generated(data)
        earliest_core, earliest_feed = mod._validate_finish(
            datetime(2026, 9, 14, 8, 16, tzinfo=JST),
            datetime(2026, 9, 14, 8, 17, tzinfo=JST),
            data,
            core,
        )
        self.assertEqual(datetime(2026, 9, 14, 11, 0, tzinfo=JST), earliest_core)
        self.assertEqual(datetime(2026, 9, 14, 10, 0, tzinfo=JST), earliest_feed)
        with self.assertRaises(RuntimeError):
            mod._validate_finish(
                datetime(2026, 9, 14, 9, 59, tzinfo=JST),
                datetime(2026, 9, 14, 10, 0, tzinfo=JST),
                data,
                core,
            )

    def test_missing_deadline_fails_closed(self):
        data = feed_doc()
        data["feed"][-1]["deadline_at"] = None
        with self.assertRaises(RuntimeError):
            mod._validate_generated(data)


if __name__ == "__main__":
    unittest.main()
