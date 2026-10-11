"""Synthetic only: full candidate-day denominator is never outcome-filtered."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from v5.offline_prior_day_counter_update import FrozenDay, FrozenRace
from v5.offline_day_evidence_coverage import DayEvidenceRow
from v5.offline_trifecta_shadow_ranking import OfflineTrifectaShadowRanking
from v5.offline_retrospective_result_adapter import FrozenResearchRank, StoredResultRow
from v5.offline_whole_day_research_ledger import reconcile_whole_day_research

JST = ZoneInfo("Asia/Tokyo")
DAY = date(2026, 5, 1)
A, B, C, D = ("20260501_24_09", "20260501_24_10",
              "20260501_24_11", "20260501_24_12")
LANES = tuple(range(4101, 4107))
WIN = (2, 1, 5)


def moment(h, m):
    return datetime(2026, 5, 1, h, m, tzinfo=JST)


def frozen_race(rid, ticket=()):
    return FrozenRace(rid, LANES, ("A1", "A2", "B1", "B2", "A1", "A2"),
                      (3, 1, 4, 2, 6, 5),
                      (ticket,) if ticket else ())


def frozen_day(*races):
    return FrozenDay(DAY, tuple(races), date(2026, 4, 30), 0,
                     "synthetic-frozen-state-fingerprint")


def ledger_row(rid, decision):
    return DayEvidenceRow(rid, decision, moment(17, 30), moment(17, 41),
                          LANES, "unapproved-origin",
                          None, datetime(2026, 8, 15, 13, 54, tzinfo=JST),
                          None, None)


def rank(rid=A, count=1):
    names = ("-".join(map(str, p)) for p in permutations(range(1, 7), 3))
    masses = {name: (10 if name == "2-1-5" else 1) for name in names}
    total = sum(masses.values())
    distribution = tuple(sorted((t, float(p / total))
                                for t, p in masses.items()))
    top = tuple(sorted(distribution, key=lambda t: (-t[1], t[0])))[:count]
    return FrozenResearchRank(
        OfflineTrifectaShadowRanking(
            "SYNTHETIC_120_TICKET_PL_SHADOW_UNVALIDATED_HARD_HOLD",
            rid, count, distribution, top, True),
        moment(17, 30), moment(17, 41),
        datetime(2026, 8, 15, 13, 54, tzinfo=JST), 100)


def stored(rid=A, *, refunds=(), verified=False):
    return StoredResultRow(rid, "official", "official", "2-1-5", 6180,
                           refunds, verified)


def mixed(**override):
    args = dict(
        frozen_day=frozen_day(frozen_race(A, WIN), frozen_race(B)),
        inventory_race_ids=(A, B, C),
        inventory_source_ref="claimed-inventory-not-authenticated",
        decisions=(ledger_row(A, "FROZEN"), ledger_row(B, "NO_BUY"),
                   ledger_row(C, "PENDING")),
        claimed_frozen_race_ids=(A, B),
        frozen_ranks=(rank(),),
        result_rows=(stored(verified=True), stored(B, verified=True)),
    )
    args.update(override)
    return reconcile_whole_day_research(**args)


class TestWholeDayResearchLedger(unittest.TestCase):
    def test_full_denominator_and_nonselected_results_retained(self):
        out = mixed()
        self.assertEqual(out.all_race_decisions,
                         ((A, "FROZEN"), (B, "NO_BUY"), (C, "PENDING")))
        self.assertEqual(out.selected_race_ids, (A,))
        self.assertEqual(out.no_buy_race_ids, (B,))
        self.assertEqual(out.pending_race_ids, (C,))
        self.assertEqual(len(out.all_result_rows), 2)
        self.assertEqual(out.coverage.audit.inventory_count, 3)
        self.assertEqual(out.scenario.economics.candidate_races, 1)
        self.assertTrue(out.hypothetical_roi_available)
        self.assertEqual(out.scenario.economics.hypothetical_net_yen, 6080)
        self.assertFalse(out.original_selection_time_verified)
        self.assertFalse(out.inventory_independently_verified)
        self.assertFalse(out.v5_real_roi_verified)
        self.assertFalse(out.buy_eligible)

    def test_refund_unknown_preserved_without_full_cohort_roi(self):
        out = mixed(result_rows=(stored(refunds=None),))
        self.assertEqual(out.scenario.economics.unresolved_races, 1)
        self.assertEqual(out.scenario.economics.status_by_race[0][1],
                         "REFUND_MAPPING_UNVERIFIED")
        self.assertIsNone(out.scenario.economics.hypothetical_roi_pct)
        self.assertFalse(out.hypothetical_roi_available)
        self.assertEqual(out.coverage.audit.inventory_count, 3)

    def test_no_selection_still_has_day_inventory_and_no_roi(self):
        out = mixed(
            frozen_day=frozen_day(frozen_race(B)),
            decisions=(ledger_row(A, "PENDING"), ledger_row(B, "NO_BUY"),
                       ledger_row(C, "PENDING")),
            claimed_frozen_race_ids=(B,),
            frozen_ranks=(),
            result_rows=(stored(A), stored(B)),
        )
        self.assertEqual(out.reason, "ZERO_SELECTED_RACES_NO_ROI")
        self.assertEqual(out.selected_race_ids, ())
        self.assertEqual(out.no_buy_race_ids, (B,))
        self.assertEqual(out.pending_race_ids, (A, C))
        self.assertIsNone(out.scenario)
        self.assertFalse(out.hypothetical_roi_available)
        self.assertEqual(len(out.all_result_rows), 2)

    def test_missing_selected_rank_or_extra_unselected_rank_denied(self):
        with self.assertRaisesRegex(ValueError, "RECONSTRUCTED_RANK_COHORT_MISMATCH"):
            mixed(frozen_ranks=())
        with self.assertRaisesRegex(ValueError, "RECONSTRUCTED_RANK_COHORT_MISMATCH"):
            mixed(frozen_ranks=(rank(), rank(B)))

    def test_wrong_or_duplicate_frozen_ticket_denied(self):
        with self.assertRaisesRegex(ValueError, "RECONSTRUCTED_TICKET_SELECTION_MISMATCH"):
            mixed(frozen_day=frozen_day(
                frozen_race(A, (1, 2, 3)), frozen_race(B)))
        bad = replace(frozen_race(A, WIN), selected_tickets=(WIN, WIN))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_FROZEN_TICKET"):
            mixed(frozen_day=frozen_day(bad, frozen_race(B)))

    def test_decision_cutoff_mismatch_denied(self):
        edited = replace(rank(), decision_cutoff_at=moment(17, 31))
        with self.assertRaisesRegex(ValueError, "RECONSTRUCTED_DECISION_CLOCK_MISMATCH"):
            mixed(frozen_ranks=(edited,))

    def test_inventory_gap_and_unfrozen_no_buy_denied(self):
        with self.assertRaisesRegex(ValueError, "CLAIMED_DAY_INVENTORY_INCOMPLETE"):
            mixed(inventory_race_ids=(A, B, C, D))
        with self.assertRaisesRegex(ValueError, "UNFROZEN_RACE_MUST_BE_PENDING"):
            mixed(decisions=(ledger_row(A, "FROZEN"), ledger_row(B, "NO_BUY"),
                             ledger_row(C, "NO_BUY")))

    def test_result_outside_inventory_or_duplicate_denied(self):
        with self.assertRaisesRegex(ValueError, "RESULT_OUTSIDE_INVENTORY_OR_DUPLICATE"):
            mixed(result_rows=(stored(), stored()))
        with self.assertRaisesRegex(ValueError, "RESULT_OUTSIDE_INVENTORY_OR_DUPLICATE"):
            mixed(result_rows=(stored(), stored(D)))

    def test_missing_selected_result_is_unresolved_not_deleted(self):
        out = mixed(result_rows=(stored(B),))
        self.assertEqual(out.coverage.audit.inventory_count, 3)
        self.assertEqual(out.scenario.economics.unresolved_races, 1)
        self.assertEqual(out.scenario.economics.candidate_races, 1)
        self.assertIsNone(out.scenario.economics.hypothetical_net_yen)
        self.assertFalse(out.hypothetical_roi_available)


if __name__ == "__main__":
    unittest.main()
