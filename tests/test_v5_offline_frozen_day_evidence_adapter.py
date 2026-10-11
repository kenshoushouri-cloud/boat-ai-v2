"""Local offline tests using real FrozenDay and the existing evidence audit."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from v5.offline_prior_day_counter_update import FrozenDay, FrozenRace
from v5.offline_day_evidence_coverage import DayEvidenceRow
from v5.offline_frozen_day_evidence_adapter import audit_actual_frozen_day

DAY = date(2026, 5, 1)
JST = ZoneInfo("Asia/Tokyo")
A, B, C = "20260501_24_10", "20260501_24_11", "20260501_24_12"
LANES = tuple(range(4101, 4107))


def fixed(rid: str, tickets=()):
    return FrozenRace(rid, LANES, ("A1", "A2", "B1", "B2", "A1", "A2"),
                      (3, 1, 4, 2, 6, 5), tickets)


def day(*races):
    return FrozenDay(DAY, tuple(races), date(2026, 4, 30), 11, "opaque-fingerprint")


def row(rid, decision, *, lane_ids=LANES):
    def t(h, m):
        return datetime(2026, 5, 1, h, m, tzinfo=JST)
    return DayEvidenceRow(rid, decision, t(17, 35), t(17, 41),
                          lane_ids, None, t(17, 31), t(17, 32),
                          None, None)


def check(d, inventory=None, ledger=None, claim=None):
    return audit_actual_frozen_day(
        d, (A, B, C) if inventory is None else inventory,
        "caller-roster-unverified",
        (row(A, "FROZEN"), row(B, "NO_BUY"), row(C, "PENDING"))
        if ledger is None else ledger,
        (A, B) if claim is None else claim,
    )


class TestFrozenDayEvidenceAdapter(unittest.TestCase):
    def sample(self):
        return day(fixed(A, ((2, 1, 5),)), fixed(B))

    def test_real_frozen_day_keeps_no_buy_and_pending(self):
        result = check(self.sample())
        self.assertEqual(result.actual_frozen_race_ids, (A, B))
        self.assertEqual(result.frozen_hypothetical_ticket_ids, (A,))
        self.assertEqual(result.frozen_no_buy_ids, (B,))
        self.assertEqual(result.audit.inventory_count, 3)
        self.assertEqual(result.audit.frozen_count, 1) # hypothetical tickets only
        self.assertEqual(result.audit.no_buy_count, 1)
        self.assertEqual(result.audit.pending_count, 1)
        self.assertTrue(result.audit.caller_inventory_matches_decision_ledger)
        self.assertFalse(result.independently_verified)
        self.assertFalse(result.forward_eligible)
        self.assertFalse(result.buy_eligible)
        self.assertFalse(result.audit.buy_eligible)

    def test_bad_claim_cannot_replace_real_frozen_set(self):
        d = self.sample()
        for ids in ((A,), (A, C), (B, B), (), (A, B, C)):
            with self.subTest(ids=ids), self.assertRaisesRegex(
                ValueError, "CLAIMED_FROZEN_IDS_MISMATCH"
            ):
                check(d, claim=ids)
        self.assertEqual(check(d, claim=(B, A)).actual_frozen_race_ids, (A, B))

    def test_empty_ticket_not_fake_selected_ticket(self):
        with self.assertRaisesRegex(ValueError, "FROZEN_TICKET_DECISION_MISMATCH"):
            check(self.sample(), ledger=(row(A, "FROZEN"), row(B, "FROZEN"), row(C, "PENDING")))
        with self.assertRaisesRegex(ValueError, "FROZEN_TICKET_DECISION_MISMATCH"):
            check(self.sample(), ledger=(row(A, "NO_BUY"), row(B, "NO_BUY"), row(C, "PENDING")))

    def test_unfrozen_race_never_inferred_as_no_buy(self):
        with self.assertRaisesRegex(ValueError, "UNFROZEN_RACE_MUST_BE_PENDING"):
            check(self.sample(), ledger=(row(A, "FROZEN"), row(B, "NO_BUY"), row(C, "NO_BUY")))

    def test_missing_frozen_race_and_duplicate_ledger_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ACTUAL_FROZEN_RACE_MISSING_FROM_LEDGER"):
            check(self.sample(), ledger=(row(A, "FROZEN"), row(C, "PENDING")))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_LEDGER_RACE"):
            check(self.sample(), ledger=(row(A, "FROZEN"), row(A, "FROZEN"), row(B, "NO_BUY")))

    def test_identity_mismatch_fails_without_fabricating_official_evidence(self):
        with self.assertRaisesRegex(ValueError, "FROZEN_RACER_IDENTITY_MISMATCH"):
            check(self.sample(), ledger=(row(A, "FROZEN", lane_ids=(9999,)+LANES[1:]),
                                         row(B, "NO_BUY"), row(C, "PENDING")))
        result = check(self.sample(), ledger=(row(A, "FROZEN", lane_ids=None),
                                              row(B, "NO_BUY"), row(C, "PENDING")))
        self.assertIn("INDEPENDENT_SIX_LANE_POSITIVE_EVIDENCE_MISSING",
                      result.audit.rows[0].predecision_reasons)
        self.assertFalse(result.audit.inventory_independently_verified)

    def test_caller_inventory_gap_does_not_vanish(self):
        result = check(self.sample(), inventory=(A, B, C, "20260501_24_09"))
        self.assertEqual(result.audit.unaccounted_ids, ("20260501_24_09",))
        self.assertFalse(result.audit.caller_inventory_matches_decision_ledger)

    def test_forged_day_or_duplicate_actual_frozen_rejected(self):
        with self.assertRaisesRegex(ValueError, "ACTUAL_FROZEN_DAY_REQUIRED"):
            check(replace(self.sample(), baseline_fitted_through=DAY))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ACTUAL_FROZEN_RACE"):
            check(day(fixed(A, ((2, 1, 5),)), fixed(A, ((2, 1, 5),)), fixed(B)))


if __name__ == "__main__":
    unittest.main()
