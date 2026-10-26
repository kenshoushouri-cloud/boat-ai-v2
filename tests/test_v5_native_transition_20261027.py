"""Standalone OFFLINE contract tests for next-day native V5 transition code.

No PG connection, site HTTP, systemd modifications, or old collector writes.
"""
from __future__ import annotations
import os
import unittest
from unittest.mock import patch
from datetime import date

from v5 import native_core_day_runner as core
from v5 import native_realtime_due_runner as realtime
from v5 import native_results_catchup_stage as results

class TransitionTests(unittest.TestCase):
    def test_core_14_venues_twelve_races(self):
        venues=[f"{n:02d}" for n in range(1,15)]
        planned=core.target_ids("20261027",venues,24,12)
        self.assertEqual(len(planned),168)
        self.assertEqual(planned[0],"20261027_01_01")
        self.assertEqual(planned[-1],"20261027_14_12")

    def test_core_reject_bad_race_plan(self):
        with self.assertRaisesRegex(ValueError,"DAY_PLAN"):
            core.target_ids("20261027",["01"],24,13)

    def test_core_write_gates_fail_closed_before_http(self):
        with patch.dict(os.environ,{},clear=True), \
             patch.object(core,"fetch_official_index") as fetch:
            with self.assertRaisesRegex(RuntimeError,"LOCAL_DB"):
                core.main(["--apply"])
            fetch.assert_not_called()

    def test_core_preview_single_target_no_stage_writer(self):
        from datetime import datetime, timezone, timedelta
        now=datetime(2026,10,27,6,45,tzinfo=timezone(timedelta(hours=9)))
        race={"race_id":"20261027_01_01","race_date":"2026-10-27"}
        entries=[{"lane":i} for i in range(1,7)]
        with patch.object(core,"datetime") as clock, \
             patch.object(core,"fetch_official_index",return_value="html"), \
             patch.object(core,"official_venues",return_value=["01"]), \
             patch.object(core,"official_fetch",return_value=("html",now)), \
             patch.object(core,"official_payload",return_value=(race,entries)), \
             patch.object(core,"apply_one") as apply, \
             patch.object(core.time,"sleep"):
            clock.now.return_value=now
            self.assertEqual(core.main(["--scope","today"]),0)
            apply.assert_not_called()

    def test_realtime_preview_no_apply_or_http(self):
        with patch.object(realtime,"candidates",return_value=["20261027_01_01"]), \
             patch.object(realtime,"collect_one") as collect, \
             patch.object(realtime,"ready_to_apply") as approve:
            self.assertEqual(realtime.main([]),0)
            collect.assert_not_called()
            approve.assert_not_called()

    def test_realtime_queue_over_cap_fails_not_claims_complete(self):
        with patch.object(realtime,"candidates",return_value=[
             "20261027_01_01","20261027_02_01"]):
            self.assertEqual(realtime.main(["--max-races","1"]),2)

    def test_realtime_gate_denies_before_stage_reader(self):
        with patch.object(realtime,"ready_to_apply",
                          side_effect=RuntimeError("HOLD_AUTH")), \
             patch.object(realtime,"candidates") as candidates:
            with self.assertRaisesRegex(RuntimeError,"HOLD_AUTH"):
                realtime.main(["--apply"])
            candidates.assert_not_called()

    def test_results_valid_trifecta_only(self):
        self.assertTrue(results.verified_result({
            "result_status":"official","trifecta_ticket":"1-2-3",
            "trifecta_payout_yen":4000}))
        self.assertFalse(results.verified_result({
            "result_status":"official","trifecta_ticket":"1-1-3",
            "trifecta_payout_yen":4000}))
        self.assertFalse(results.verified_result({
            "result_status":"official","trifecta_ticket":"1-2-3",
            "trifecta_payout_yen":0}))
        self.assertTrue(results.verified_result({"result_status":"cancelled"}))

    def test_results_gate_denies_without_local_db(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"LOCAL_DB"):
                results.authorize()

    def test_results_preview_no_site_or_write(self):
        with patch.dict(os.environ,{"DATABASE_URL":"postgresql:///railway"},
                        clear=True), \
             patch.object(results,"pending",return_value=["20261026_01_01"]), \
             patch.object(results,"fetch_parsed") as fetch, \
             patch.object(results,"save_one") as save, \
             patch.object(results,"target_day",return_value=date(2026,10,26)):
            self.assertEqual(results.main([]),0)
            fetch.assert_not_called()
            save.assert_not_called()

    def test_results_apply_blocks_before_pending_read(self):
        with patch.dict(os.environ,{},clear=True), \
             patch.object(results,"pending") as pending:
            with self.assertRaisesRegex(RuntimeError,"LOCAL_DB"):
                results.main(["--apply"])
            pending.assert_not_called()

if __name__=="__main__":
    unittest.main()
