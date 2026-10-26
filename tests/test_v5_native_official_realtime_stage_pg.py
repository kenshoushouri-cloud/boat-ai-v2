"""Offline unit tests for independent official 6-family realtime stage writer.

No official HTTP, PostgreSQL, collector, timers or BUY.
"""
import itertools
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from v5 import native_official_realtime_stage_pg as m

JST=timezone(timedelta(hours=9))
CAP=datetime(2026,10,27,12,0,tzinfo=JST)
RACE={"race_id":"20261027_01_01","deadline_at":"2026-10-27T15:22:00+09:00"}
ENTRIES=[{"race_id":RACE["race_id"],"lane":i,"racer_number":4100+i,
          "racer_name":"Sample "+str(i),"motor_no":i,"boat_no":i}
         for i in range(1,7)]
ODDS={f"{a}-{b}-{c}":float(100+a*10+b*2+c) for a,b,c in
      itertools.permutations(range(1,7),3)}

def fake_parser(exhibition=6, weather=True):
    return SimpleNamespace(
      _looks_no_data=lambda h:False,
      parse_weather=lambda h:{
          "weather":"晴","temperature_c":23 if weather else None,
          "water_temperature_c":19,"wind_speed_m":2,
          "wave_height_cm":1,"wind_direction":"北"},
      parse_exhibition=lambda h:[
          {"lane":i,"exhibition_course":i,
           "exhibition_time":6.6+i/100,"exhibition_time_rank":i,
           "exhibition_time_diff":(i-1)/100,
           "start_timing":.12,"start_timing_rank":i}
          for i in range(1,exhibition+1)],
      parse_beforeinfo_extra=lambda h,e:(
          {"is_stabilizer_used":False,"is_fixed_entry":False,
           "race_distance_m":1800,"has_new_propeller":False,
           "parts_replacement_count":0},
          [{"lane":i,"racer_number":4100+i,"parts_replacements":[]}
           for i in range(1,7)]),
    )


class NativeRealtimeStageTests(TestCase):
    def sample(self, *,exhibition=6,weather=True,odds=None,at=CAP):
        import official_odds3t_parser as p
        parser = fake_parser(exhibition,weather)
        with patch.dict(sys.modules, {"v21_realtime_collector_pg":parser}), \
             patch.object(p,"parse_official_odds3t",
                          return_value=ODDS if odds is None else odds):
            return m.prepare_rows(RACE,ENTRIES,"HTML","ODDS",at,at,
                                  "a"*64,"b"*64)

    def test_exactly_140_validated_rows_all_six_families(self):
        rows=self.sample()
        self.assertEqual({k:len(v) for k,v in rows.items()},
            {"entry_snapshots":6,"exhibition_snapshots":6,
             "odds_snapshots":120,"weather_snapshots":1,
             "race_condition_snapshots":1,"racer_condition_snapshots":6})
        self.assertEqual({r["lane"] for r in rows["entry_snapshots"]},
                         set(range(1,7)))
        self.assertEqual(len({r["snapshot_label"]
                              for v in rows.values() for r in v}),1)

    def test_never_use_legacy_odds_fallback(self):
        with self.assertRaisesRegex(RuntimeError,"ODDS_NOT_COMPLETE"):
            self.sample(odds=dict(list(ODDS.items())[:119]))

    def test_exhibition_six_required(self):
        with self.assertRaisesRegex(RuntimeError,"EXHIBITION_NOT_SIX"):
            self.sample(exhibition=5)

    def test_weather_completeness_required(self):
        with self.assertRaisesRegex(RuntimeError,"WEATHER_INCOMPLETE"):
            self.sample(weather=False)

    def test_deadline_expired_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"PREDEADLINE"):
            self.sample(at=datetime(2026,10,27,15,20,tzinfo=JST))

    def test_naive_capture_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"NAIVE_CAPTURE"):
            m._check_before_cutoff(datetime(2026,10,27,12),CAP)

    def test_official_endpoints_only(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_OFFICIAL"):
            m.official_page("raceresult","20261027_01_01")

    def test_stage_table_allowlist_six(self):
        self.assertEqual(len(m.SNAPSHOT_KEYS),6)
        self.assertEqual(set(m.SNAPSHOT_KEYS),set(m.COLUMN_SETS))
        self.assertTrue(all(x.startswith("entry") or x.startswith("exhibition")
                            or x.startswith("odds") or x.startswith("weather")
                            or x.startswith("race_condition") or
                            x.startswith("racer_condition")
                            for x in m.COLUMN_SETS))

    def test_apply_denies_without_local_database_pre_http(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"LOCAL_CONOHA"):
                m.ready_to_apply()

    def test_apply_denies_missing_isolation_before_http(self):
        with patch.dict(os.environ,{"DATABASE_URL":"postgresql:///railway"},
                        clear=True):
            with self.assertRaisesRegex(RuntimeError,"MISSING_NATIVE"):
                m.ready_to_apply()

    def test_apply_denies_buy(self):
        env={"DATABASE_URL":"postgresql:///railway",**m.REQUIRED,
             "BUY_ENABLED":"YES"}
        with patch.dict(os.environ,env,clear=True):
            with self.assertRaisesRegex(RuntimeError,"BUY_NOT_OFF"):
                m.ready_to_apply()

    def test_apply_verifies_night_delta_gate(self):
        with patch.dict(os.environ,{"DATABASE_URL":"postgresql:///railway",
                                    **m.REQUIRED},clear=True), \
             patch.object(m,"blocked_by_stage_delta") as check:
            m.ready_to_apply()
            check.assert_called_once()

    def test_direct_save_cannot_bypass_authorization(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"LOCAL_CONOHA"):
                m.save_canary(RACE,{})

    def test_preview_never_opens_database(self):
        race={**RACE,"race_date":"2026-10-27"}
        with patch.object(m,"official_fetch",return_value=("HTML",CAP)),\
             patch.object(m,"official_payload",return_value=(race,ENTRIES)),\
             patch.object(m,"official_page",return_value=("HTML",CAP,"a"*64)),\
             patch.object(m,"prepare_rows",return_value={}),\
             patch.object(m,"save_canary") as saved,\
             patch.object(m,"ready_to_apply") as gate:
            self.assertEqual(m.main(["--race-id",RACE["race_id"]]),0)
            saved.assert_not_called()
            gate.assert_not_called()

    def test_apply_checks_guards_before_any_http(self):
        with patch.object(m,"ready_to_apply",side_effect=RuntimeError("HOLD")) ,\
             patch.object(m,"official_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError,"HOLD"):
                m.main(["--race-id",RACE["race_id"],"--apply"])
            fetch.assert_not_called()


if __name__=="__main__":
    main()
