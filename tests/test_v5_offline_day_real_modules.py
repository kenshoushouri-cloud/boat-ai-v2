"""Actual V5 inference/ranking/cash modules joined by offline day pipeline.

Synthetic records only. Never authenticates first sight, opens network or buys.
"""
import dataclasses
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from v5.offline_mainline_inference import OfflineV5InferenceInput, check_offline_v5_inference
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas
from v5.offline_trifecta_cash_ledger import MockOrder, MockTicketReturn, PredeadlineMockRace, PostraceMockResult
from v5.offline_day_shadow_pipeline import OfflineV5DayInput, evaluate_offline_v5_day

T = datetime(2026, 10, 10, 10, tzinfo=timezone(timedelta(hours=9)))
SOURCE, RESULT = b'fictional-source', b'fictional-result'
FACTORS = ('recent_form', 'exhibition_rank', 'racer_course', 'opponent', 'venue_lane')


def day():
    candidates, pre, post = [], [], []
    for i in (1, 2):
        rid = f'20261010_03_0{i}'
        c = OfflineV5InferenceInput(
            rid, T + timedelta(minutes=20), (101, 102, 103, 104, 105, 106),
            (.3, .25, .15, .13, .1, .07),
            {k: (1.,) * 6 for k in FACTORS},
        )
        rank = rank_offline_v5_trifectas(check_offline_v5_inference(c), ticket_count=2)
        assert rank.synthetic_math_consistent
        orders = tuple(MockOrder(t, 100, 8., T+timedelta(minutes=2),
                                 T+timedelta(minutes=5), f'fake-{rid}-{j}')
                       for j, (t, _) in enumerate(rank.top_tickets))
        pre.append(PredeadlineMockRace(rid, T+timedelta(hours=1), T,
                   c.decision_cutoff_at, 'fictional', SOURCE,
                   hashlib.sha256(SOURCE).hexdigest(), orders))
        void = i == 2
        winner = None if void else orders[0].ticket
        post.append(PostraceMockResult(
            rid, T+timedelta(hours=4), 'fictional', RESULT,
            hashlib.sha256(RESULT).hexdigest(), 'VOID' if void else 'OFFICIAL',
            winner, tuple(MockTicketReturn(o.ticket, 0 if void else
                (900 if o.ticket == winner else 0), 100 if void else 0) for o in orders),
        ))
        candidates.append(c)
    return OfflineV5DayInput(tuple(candidates), (2, 2), tuple(pre), tuple(post))


class TestOfflineActualV5Modules(unittest.TestCase):
    def test_real_modules_two_races_with_void(self):
        result = evaluate_offline_v5_day(day())
        self.assertEqual(result.reason, 'SYNTHETIC_V5_DAY_INTEGRATION_ONLY_HARD_HOLD')
        self.assertEqual((result.candidate_races, result.simulated_tickets,
                          result.synthetic_paid_yen, result.synthetic_return_yen,
                          result.synthetic_net_yen, result.synthetic_roi_pct),
                         (2, 4, 400, 1100, 700, 275.))
        for key in ('independently_authenticated_source', 'six_active_starts_confirmed',
                    'selection_eligible', 'forward_eligible', 'buy_eligible'):
            self.assertIs(getattr(result, key), False)

    def test_real_modules_mismatched_freeze_denied(self):
        d = day()
        changed = dataclasses.replace(d.candidates[0], decision_cutoff_at=T+timedelta(minutes=21))
        result = evaluate_offline_v5_day(dataclasses.replace(d, candidates=(changed, d.candidates[1])))
        self.assertEqual(result.reason, 'INFERENCE_NOT_TIED_TO_FROZEN_DECISION_TIME')
        self.assertEqual(result.synthetic_paid_yen, 0)

    def test_real_modules_pending_result_denied(self):
        d = day()
        pending = dataclasses.replace(d.postrace[1], status='PENDING')
        result = evaluate_offline_v5_day(dataclasses.replace(d, postrace=(d.postrace[0], pending)))
        self.assertEqual(result.reason, 'V5_SHADOW_CASH_LEDGER_UNRESOLVED_OR_INVALID_SETTLEMENT')
        self.assertIsNone(result.synthetic_roi_pct)


if __name__ == '__main__':
    unittest.main()
