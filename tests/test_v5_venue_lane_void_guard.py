# -*- coding: utf-8 -*-
"""Offline test of V5 venue-lane research VOID selection and history.

Fake DB rows exercise main(), including a deliberately mislabeled cancelled
race with an alleged winner/history row. No DB, Railway or internet needed.
"""
from __future__ import annotations
import contextlib
import importlib
import io
import json
import sys
import types
import unittest
from unittest.mock import patch

from research.historical_void_registry import VERIFIED_VOID_RACE_IDS, EVIDENCE_REF

PREFIX = "V5_CURRENT_CORE_PLUS_VENUE_RESULT="


def load_venue_lane():
    fake_db=types.ModuleType("db_pg")
    fake_db.fetch_all=lambda *_args, **_kwargs: []
    with patch.dict(sys.modules, {"db_pg": fake_db}):
        return importlib.import_module("research.v5_current_core_plus_venue_lane_pg")


class TestResearchVenueLaneVoid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tuner=load_venue_lane()

    def test_main_drops_void_outcome_and_history_and_preserves_completed_races(self):
        # At least one authentic-shape race in each reporting split:
        # train, Apr, May and Jun-end; includes both completed 9/21 examples.
        normal=[
            ("20260105_01_01", "2026-01-05", "01", 1),
            ("20260405_02_01", "2026-04-05", "02", 2),
            ("20260505_03_01", "2026-05-05", "03", 3),
            ("20260921_09_04", "2026-09-21", "09", 4),
            ("20260921_10_09", "2026-09-21", "10", 1),
        ]
        cancelled=("20260921_09_05", "2026-09-21", "09", 5)
        self.assertIn(cancelled[0], VERIFIED_VOID_RACE_IDS)
        abnormal=[
            ("20260105_01_02", "2026-01-05", "01", 2, "K0"),
            ("20260505_03_02", "2026-05-05", "03", 3, "S1"),
            ("20260921_09_03", "2026-09-21", "09", 1, "F"),
        ]
        ordered=normal+[cancelled]+[row[:4] for row in abnormal]
        race_rows=[
            {"race_id":rid,"race_date":date,"venue":venue,"winner":winner}
            for rid,date,venue,winner in ordered
        ]
        entry_rows=[
            {"race_id":rid,"lane":lane,"racer_number":1000+idx*10+lane,
             "racer_class":"A1","recent_form":None,"exhibition_time_rank":lane}
            for idx,(rid, *_rest) in enumerate(ordered) for lane in range(1,7)
        ]
        history=[
            {"race_id":rid,"lane":lane,"racer_number":1000+idx*10+lane,
             "start_course":lane,"finish_position":lane,"finish_status":f"{lane:02d}",
             "is_flying":False,"is_late":False,
             "result_status":"official","race_status":"official","race_date":date}
            for idx,(rid,date,*_rest) in enumerate(normal) for lane in range(1,7)
        ]+[
            {"race_id":cancelled[0],"lane":1,"racer_number":9999,
             "start_course":1,"finish_position":1,"finish_status":"01",
             "is_flying":False,"is_late":False,
             "result_status":"official","race_status":"official","race_date":cancelled[1]}
        ]+[
            {"race_id":rid,"lane":lane,"racer_number":3000+idx*10+lane,
             "start_course":lane,"finish_position":lane,
             "finish_status":status if lane==1 else f"{lane:02d}",
             "is_flying":status=="F" and lane==1,"is_late":False,
             "result_status":"official","race_status":"official","race_date":date}
            for idx,(rid,date,venue,winner,status) in enumerate(abnormal) for lane in range(1,7)
        ]
        schemas={
            "v2_races":{"race_id","race_date","venue_code"},
            "v2_race_entries":{"race_id","lane","racer_number","racer_class","recent_form"},
            "v2_results":{"race_id","first_lane","result_status","race_status"},
            "v2_realtime_exhibition_snapshots":{"race_id","lane","exhibition_time_rank"},
            "v2_result_entries":{"race_id","lane","racer_number","start_course","finish_position","finish_status","is_flying","is_late"},
        }
        def fake_fetch(sql,args):
            sql=" ".join(sql.lower().split())
            if "select r.race_id,r.race_date" in sql:return race_rows
            if "select e.race_id,e.lane" in sql:return entry_rows
            if "select re.race_id,re.lane,re.racer_number" in sql:return history
            raise AssertionError("Unexpected DB query: "+sql[:130])
        output=io.StringIO()
        with patch.object(self.tuner.b,"cols",side_effect=lambda name:schemas[name]):
            with patch.object(self.tuner,"fetch_all",side_effect=fake_fetch):
                with contextlib.redirect_stdout(output):
                    self.tuner.main()
        result_line=next(line for line in output.getvalue().splitlines() if line.startswith(PREFIX))
        report=json.loads(result_line[len(PREFIX):])
        coverage=report["coverage"]
        self.assertEqual(report["period"]["start"],"2025-07-01")
        self.assertEqual(report["period"]["end"],"2026-10-05")
        self.assertEqual(coverage["completed_races"],5)
        self.assertEqual(coverage["scored"],5)
        self.assertEqual(coverage["void_candidate_rows_excluded"],1)
        self.assertEqual(coverage["void_history_rows_excluded"],1)
        self.assertEqual(coverage["incident_candidate_exclusions"],{"ABNORMAL_RESULT":3})
        self.assertEqual(coverage["incident_history_races_exclusions"],{"ABNORMAL_RESULT":3})
        self.assertEqual(coverage["incident_guard"],"result_side_research_fit_only")
        self.assertTrue(coverage["result_side_not_predeadline_evidence"])
        self.assertEqual(coverage["verified_void_registry_size"],71)
        self.assertEqual(coverage["void_evidence_ref"],EVIDENCE_REF)
        self.assertEqual(coverage["venue_count"],5)
        self.assertEqual(set(report["venue_delta_logloss"]),{"01","02","03","09","10"})
        self.assertEqual(report["candidate"]["added"],["venue_lane_residual"])
        self.assertTrue(report["candidate"]["strictly_prior_calendar_day"])
        self.assertFalse(report["candidate"]["same_day_results_used"])
        self.assertFalse(report["safety"]["db_write"])


if __name__=="__main__":
    unittest.main()
