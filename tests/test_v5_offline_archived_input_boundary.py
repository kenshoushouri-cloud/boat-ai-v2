"""No DB / HTTP. Synthetic strictly retrospective six-lane input boundary tests."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from v5.offline_archived_input_boundary import prepare_archived_research_input
from v5.offline_prior_day_factor_export import FactorVectors

JST = ZoneInfo("Asia/Tokyo")
RID = "20260501_24_12"
DEADLINE = datetime(2026, 5, 1, 17, 41, tzinfo=JST)
LATE = datetime(2026, 8, 15, 13, 54, tzinfo=JST)
CUTOFF = datetime(2026, 5, 1, 17, 30, tzinfo=JST)
FACTOR_KEYS = ("recent_form", "exhibition_rank", "racer_course", "opponent", "venue_lane")


def raw():
    return tuple(dict(
        race_id=RID, race_date=date(2026, 5, 1), deadline_at=DEADLINE,
        lane=n, racer_number=4100+n, racer_class="A1",
        recent_form_json_type="array",
        parsed_history=[{"race_date": "2026-04-30", "finish_position": 3}],
        exhibition_time_rank=(3, 1, 4, 2, 6, 5)[n-1],
        exhibition_source="official_beforeinfo_historical",
        exhibition_snapshot_at=LATE,
        independent_official_six_active_verified=False,
        original_first_observation_verified=False,
        forward_eligible=False, buy_eligible=False,
    ) for n in range(1, 7))


def factors(**updates):
    kw=dict(
        reason="RETROSPECTIVE_PRIOR_DAY_COUNTER_MATH_ONLY",
        race_id=RID, fitted_through=date(2026, 4, 30),
        base_probabilities=(.2, .2, .2, .2, .1, .1),
        factors={name: (1.,)*6 for name in FACTOR_KEYS},
    )
    kw.update(updates)
    return FactorVectors(**kw)


def inspected(**updates):
    kw=dict(raw_rows=raw(), prior_day_factors=factors(),
            decision_cutoff_at=CUTOFF, ticket_count=2,
            stake_per_ticket_yen=100)
    kw.update(updates)
    return prepare_archived_research_input(**kw)


def updated_row(**changes):
    rs=[dict(r) for r in raw()]
    rs[0].update(changes)
    return tuple(rs)


class TestArchivedInputBoundary(unittest.TestCase):
    def test_complete_archived_candidate_is_never_forward_buy_or_real_roi(self):
        out=inspected()
        self.assertEqual(out.reason,"ARCHIVED_RESEARCH_INPUT_ONLY_NO_ORIGINAL_ASOF_PROOF")
        self.assertIsNotNone(out.archived_case)
        self.assertEqual(len(out.archived_case.lanes),6)
        self.assertEqual(tuple(x.exhibition_time_rank for x in out.archived_case.lanes),
                         (3,1,4,2,6,5))
        self.assertEqual(out.archived_case.ticket_count,2)
        self.assertIn("EXHIBITION_SNAPSHOT_AFTER_DEADLINE",out.source_warnings)
        self.assertFalse(out.original_predeadline_cutoff_verified)
        self.assertFalse(out.prior_day_model_origin_independently_verified)
        self.assertFalse(out.v5_real_roi_verified)
        self.assertFalse(out.forward_eligible)
        self.assertFalse(out.buy_eligible)

    def test_null_unexported_or_wrong_reason_factors_hold(self):
        self.assertEqual(inspected(prior_day_factors=None).reason,
                         "HOLD_PRIOR_DAY_FACTORS_MISSING")
        self.assertEqual(inspected(prior_day_factors=factors(reason="CLAIMED_FUTURE")).reason,
                         "HOLD_UNVERIFIED_OR_LEAKING_FACTOR_DATE")

    def test_target_or_later_fitted_counter_date_holds(self):
        for d in (date(2026,5,1),date(2026,8,15)):
            with self.subTest(day=d):
                self.assertEqual(inspected(prior_day_factors=factors(fitted_through=d)).reason,
                                 "HOLD_UNVERIFIED_OR_LEAKING_FACTOR_DATE")

    def test_mismatched_factor_race_holds(self):
        self.assertEqual(inspected(prior_day_factors=factors(race_id="20260501_24_11")).reason,
                         "HOLD_UNVERIFIED_OR_LEAKING_FACTOR_DATE")

    def test_wrong_factor_schema_and_missing_vector_holds(self):
        missing={k:(1.,)*6 for k in FACTOR_KEYS if k!="opponent"}
        for vectors in (missing,{k:(1.,)*5 for k in FACTOR_KEYS}):
            with self.subTest(vectors=vectors):
                self.assertEqual(inspected(prior_day_factors=factors(factors=vectors)).reason,
                                 "HOLD_FACTOR_VALUES_INCOMPLETE")

    def test_invalid_base_or_nonfinite_factor_holds(self):
        self.assertEqual(inspected(prior_day_factors=factors(
            base_probabilities=(.2,)*6)).reason,"HOLD_FACTOR_VALUES_INCOMPLETE")
        bad={k:(1.,)*6 for k in FACTOR_KEYS}
        bad["opponent"]=(float("nan"),)*6
        self.assertEqual(inspected(prior_day_factors=factors(factors=bad)).reason,
                         "HOLD_FACTOR_VALUES_INCOMPLETE")

    def test_explicit_cutoff_required_and_never_defaulted(self):
        self.assertEqual(inspected(decision_cutoff_at=None).reason,
                         "HOLD_DECISION_CUTOFF_UNVERIFIED")
        self.assertEqual(inspected(decision_cutoff_at=datetime(2026,5,1,17,30)).reason,
                         "HOLD_DECISION_CUTOFF_UNVERIFIED")
        self.assertEqual(inspected(decision_cutoff_at=DEADLINE).reason,
                         "HOLD_DECISION_CUTOFF_UNVERIFIED")

    def test_missing_or_invalid_ticket_policy_holds(self):
        for changes in ({"ticket_count":None},{"ticket_count":0},
                        {"stake_per_ticket_yen":None},{"stake_per_ticket_yen":50},
                        {"ticket_count":True}):
            with self.subTest(**changes):
                self.assertEqual(inspected(**changes).reason,
                                 "HOLD_EXPLICIT_RESEARCH_TICKET_POLICY")

    def test_result_and_odds_columns_cannot_enter_prediction_input(self):
        for field in ("winning_ticket","trifecta_payout_yen","closing_odds"):
            with self.subTest(field=field):
                out=inspected(raw_rows=updated_row(**{field:"2-1-5"}))
                self.assertEqual(out.reason,"HOLD_UNREVIEWED_RAW_COLUMNS")
                self.assertIsNone(out.archived_case)

    def test_incomplete_or_duplicate_six_lane_values_hold_before_factors(self):
        self.assertEqual(inspected(raw_rows=raw()[:-1]).reason,
                         "HOLD_SIX_LANE_RAW_VALUES")
        self.assertEqual(inspected(raw_rows=updated_row(lane=2)).reason,
                         "HOLD_SIX_LANE_RAW_VALUES")

    def test_recent_history_date_must_be_strictly_string(self):
        out=inspected(raw_rows=updated_row(parsed_history=[{"race_date":date(2026,4,30)}]))
        self.assertEqual(out.reason,"HOLD_HISTORY_RAW_FORMAT")

    def test_late_or_unverified_exhibition_remains_research_only(self):
        out=inspected()
        self.assertTrue(out.retrospective_only)
        self.assertEqual(out.archived_case.lanes[0].exhibition_snapshot_at,LATE)
        self.assertFalse(out.original_predeadline_cutoff_verified)
        self.assertFalse(out.official_six_active_verified)


if __name__=="__main__":
    unittest.main()
