"""Offline unit tests for proposed isolated V5 primary physical writer routes.

No PostgreSQL, HTTP, systemd, file writes or service changes.
"""
import unittest

from boat_shared_storage_contract import RELATIONS
from v5.direct_shared_primary_routes import (
    STAGE_ROUTES, MODE_KEY, GATE_KEY, ISOLATION_KEY,
    canary_target, canonical_target, check_contract,
)
from v5.offline_stage_batch_plan import TARGETS as STAGE_PLAN


class StagePrimaryRoutesTests(unittest.TestCase):
    def test_exact_thirteen_mappings(self):
        check_contract()
        self.assertEqual(len(STAGE_ROUTES), 13)
        self.assertEqual(set(STAGE_ROUTES), {r.legacy for r in RELATIONS})
        self.assertEqual(set(STAGE_ROUTES.values()), {p[0] for p in STAGE_PLAN.values()})

    def test_physical_names_disjoint_from_old_or_views(self):
        for src, dst in STAGE_ROUTES.items():
            self.assertTrue(src.startswith("public.v2_"))
            self.assertTrue(dst.startswith("boat_data_stage."))
            self.assertNotIn(dst, STAGE_ROUTES)
            self.assertNotEqual(src, dst)
            self.assertFalse(dst.startswith("boat_data."))
            self.assertFalse(dst.startswith("v5_data."))

    def test_today_entries_stage_is_fixed(self):
        self.assertEqual(canonical_target("public.v2_race_entries"),
                         "boat_data_stage.entries")
        self.assertEqual(canonical_target("public.v2_realtime_odds_snapshots"),
                         "boat_data_stage.odds_snapshots")

    def test_unknown_or_unqualified_rejected(self):
        for name in ("v2_race_entries", "boat_data.entries",
                     "public.v2_v24_motor2_forward_shadow",
                     "boat_data_stage.entries",
                     "public.v2_race_entries;DROP TABLE entries"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                canonical_target(name)

    @staticmethod
    def context():
        return dict(
            verified_physical=True,
            verified_schema_and_keys=True,
            independent_native_writer=True,
            legacy_destination_isolated=True,
            live_buy_disabled=True,
        )

    def test_not_enabled_by_default(self):
        with self.assertRaisesRegex(RuntimeError, "not activated"):
            canary_target("public.v2_race_entries", env={}, **self.context())

    def test_flags_alone_cannot_enable(self):
        env={MODE_KEY:"CANARY", GATE_KEY:"YES", ISOLATION_KEY:"YES"}
        with self.assertRaisesRegex(RuntimeError, "proof missing"):
            canary_target("public.v2_race_entries", env=env)

    def test_no_legacy_isolation_gate(self):
        env={MODE_KEY:"CANARY", GATE_KEY:"YES"}
        with self.assertRaisesRegex(RuntimeError, "gates missing"):
            canary_target("public.v2_race_entries", env=env, **self.context())

    def test_missing_each_runtime_proof_rejected(self):
        env={MODE_KEY:"CANARY", GATE_KEY:"YES", ISOLATION_KEY:"YES"}
        for key in self.context():
            ctx=self.context()
            ctx[key]=False
            with self.subTest(proof=key), self.assertRaisesRegex(RuntimeError, "proof missing"):
                canary_target("public.v2_race_entries", env=env, **ctx)

    def test_only_fully_proved_canary_resolves_fixed_target(self):
        env={MODE_KEY:"CANARY", GATE_KEY:"YES", ISOLATION_KEY:"YES"}
        self.assertEqual(
            canary_target("public.v2_race_entries", env=env, **self.context()),
            "boat_data_stage.entries",
        )

    def test_legacy_routes_not_modified(self):
        from v5_daily_table_routes import resolve_table
        from v5_realtime_table_routes import resolve_realtime_table
        from unittest.mock import patch
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_table("v2_race_entries"), "v2_race_entries")
            self.assertEqual(resolve_realtime_table("v2_realtime_odds_snapshots"),
                             "v2_realtime_odds_snapshots")


if __name__ == "__main__":
    unittest.main()
