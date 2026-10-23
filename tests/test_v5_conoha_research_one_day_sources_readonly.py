"""Offline only synthetic tests of local readonly source bridge (no DB)."""
from __future__ import annotations

import unittest
from datetime import date

from v5.conoha_research_one_day_sources_readonly import (
    assemble_source_proposals,held_summary,
)

DAY=date(2026,10,20)

def sample(rid="20261020_21_02", exhibition=True):
    return [
        dict(
            race_id=rid,lane=i,racer_number=4200+i,
            racer_class="A1" if i<4 else "B1",
            k_racer_number=4200+i,
            start_course=i,
            finish_position=(2,1,3,4,5,6)[i-1],
            finish_status=f"{(2,1,3,4,5,6)[i-1]:02d}",
            is_flying=False,is_late=False,
            exhibition_time_rank=i if exhibition else None,
            snapshot_label="conoha_forward_20261020_100000" if exhibition else None,
            result_status="official",race_status="official",
            trifecta_ticket="2-1-3",
        ) for i in range(1,7)
    ]

class TestOneDayReadOnlySourceBridge(unittest.TestCase):
    def test_holds_all_real_shaped_rows_without_refund_attestation(self):
        src=assemble_source_proposals(DAY,sample())
        self.assertEqual((src.race_total,src.roster6,
                          src.k_course_shape6,src.exhibition6,
                          src.fit_source_shape6),(1,1,1,1,1))
        self.assertEqual(len(src.fit_proposals),1)
        self.assertEqual(len(src.course_proposals),1)
        self.assertIsNone(src.fit_proposals[0].refund_boats)
        self.assertIsNone(src.course_proposals[0].incident_free_verified)
        report=held_summary(src)
        self.assertIn("RESEARCH_FIT_ACCEPTED=0",report)
        self.assertIn("K_COURSE_FIT_ACCEPTED=0",report)
        self.assertIn("BUY_ELIGIBLE=0",report)
        self.assertFalse(src.buy_eligible)

    def test_exhibition_missing_does_not_remove_course_history_proposal(self):
        src=assemble_source_proposals(DAY,sample(exhibition=False))
        self.assertEqual((src.exhibition6,src.fit_source_shape6),(0,0))
        self.assertEqual(len(src.fit_proposals),0)
        self.assertEqual(len(src.course_proposals),1)

    def test_flying_and_incomplete_course_rejected_from_k(self):
        x=sample();x[0]["is_flying"]=True
        src=assemble_source_proposals(DAY,x)
        self.assertEqual(len(src.course_proposals),0)
        self.assertEqual(len(src.fit_proposals),0)
        y=sample();y[1]["start_course"]=None
        src=assemble_source_proposals(DAY,y)
        self.assertEqual(src.k_course_shape6,0)

    def test_k_racer_mismatch_rejected(self):
        x=sample();x[1]["k_racer_number"]=9999
        src=assemble_source_proposals(DAY,x)
        self.assertEqual(src.k_course_shape6,0)

    def test_results_with_unknown_ticket_are_not_model_fit(self):
        x=sample()
        for row in x: row["trifecta_ticket"]=None
        src=assemble_source_proposals(DAY,x)
        self.assertEqual(src.k_course_shape6,1)
        self.assertEqual(src.fit_source_shape6,0)

    def test_duplicate_lanes_fail_roster(self):
        x=sample();x[5]["lane"]=5
        src=assemble_source_proposals(DAY,x)
        self.assertEqual(src.roster6,0)

    def test_multirace_split_without_authority(self):
        src=assemble_source_proposals(
            DAY,sample()+sample("20261020_21_03",exhibition=False))
        self.assertEqual((src.race_total,src.roster6,
                          src.k_course_shape6,src.fit_source_shape6),
                         (2,2,2,1))
        self.assertEqual(len(src.course_proposals),2)
        self.assertIn("UNVERIFIED_REFUND_AND_INCIDENT_GATES=HOLD",held_summary(src))

if __name__=="__main__":
    unittest.main()
