"""Offline unit tests for V5 native racer course-stats stage collector.

No official HTTP, PostgreSQL, collector, timers or BUY.
"""
from datetime import date
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

from v5 import native_racer_course_stage as m

GOOD_ENV={"DATABASE_URL":"postgresql:///railway",
          "V5_SHARED_PRIMARY_MODE":"CANARY",
          "V5_NATIVE_COURSE_STATS_STAGE_APPROVED":"YES",
          "CONFIRM_V5_SHARED_PRIMARY_CANARY":"YES",
          "CONFIRM_LEGACY_WRITES_SEPARATELY":"YES"}

def six(racer=4001,e=(10.0,20.0,30.0,10.0,20.0,10.0),
        t=(50.0,40.0,30.0,20.0,10.0,5.0),s=(.15,.16,.17,.18,.19,.2)):
    return [{"racer_number":racer,"course":c+1,"entry_rate":e[c],
             "top3_rate":t[c],"avg_st":s[c]} for c in range(6)]

class ValidRows(TestCase):
    def test_complete(self):
        self.assertTrue(m.valid_rows(six(),4001))
    def test_not_six(self):
        self.assertFalse(m.valid_rows(six()[:5],4001))
    def test_wrong_racer_or_course_order(self):
        self.assertFalse(m.valid_rows(six(4002),4001))
        rows=six(); rows[0],rows[1]=rows[1],rows[0]
        self.assertFalse(m.valid_rows(rows,4001))
    def test_out_of_range(self):
        self.assertFalse(m.valid_rows(six(e=(101,0,0,0,0,0)),4001))
        self.assertFalse(m.valid_rows(six(t=(-1,0,0,0,0,0)),4001))
        self.assertFalse(m.valid_rows(six(s=(-.01,.1,.1,.1,.1,.1)),4001))
        self.assertFalse(m.valid_rows(six(s=(2,.1,.1,.1,.1,.1)),4001))
        self.assertFalse(m.valid_rows(six(s=(2.5,.1,.1,.1,.1,.1)),4001))
    def test_avg_st_bounds_zero_inclusive_two_exclusive(self):
        self.assertTrue(m.valid_rows(six(s=(0,0.0,.1,.1,.1,.1)),4001))
        self.assertTrue(m.valid_rows(six(s=(1.99,.1,.1,.1,.1,.1)),4001))
    def test_official_dash_none_is_kept_not_zero(self):
        rows=six(e=(32.6,67.4,None,None,None,None),
                 t=(78.6,51.7,None,None,None,None),
                 s=(.16,.14,None,None,None,None))
        self.assertTrue(m.valid_rows(rows,4001))
    def test_all_metrics_missing_is_rejected(self):
        rows=six(e=(None,)*6,t=(None,)*6,s=(None,)*6)
        self.assertFalse(m.valid_rows(rows,4001))

class SnapshotId(TestCase):
    def test_deterministic_negative_and_distinct(self):
        d=date(2026,10,30)
        a=m.snapshot_id(4001,d,1)
        self.assertEqual(a,m.snapshot_id(4001,d,1))
        self.assertLess(a,0)
        ids={m.snapshot_id(r,d,c) for r in (4001,4002) for c in range(1,7)}
        self.assertEqual(12,len(ids))
        self.assertNotEqual(a,m.snapshot_id(4001,date(2026,10,31),1))

class Authorize(TestCase):
    def run_auth(self,env,delta=None):
        with patch.dict("os.environ",env,clear=True), \
             patch.object(m,"blocked_by_stage_delta",
                          side_effect=delta) as b:
            m.authorize()
            return b
    def test_ok(self):
        self.assertTrue(self.run_auth(GOOD_ENV).called)
    def test_missing_gate_each(self):
        for g in m.GATES:
            env={k:v for k,v in GOOD_ENV.items() if k!=g}
            with self.assertRaises(RuntimeError) as c:
                self.run_auth(env)
            self.assertIn("HOLD_MISSING_GATE_"+g,str(c.exception))
    def test_not_canary_or_wrong_db(self):
        with self.assertRaises(RuntimeError):
            self.run_auth({**GOOD_ENV,"V5_SHARED_PRIMARY_MODE":"OFF"})
        with self.assertRaises(RuntimeError):
            self.run_auth({**GOOD_ENV,"DATABASE_URL":"postgresql:///other"})
    def test_buy_flags_block(self):
        for k in ("BUY_ENABLED","AUTO_BUY","ENABLE_PURCHASE"):
            with self.assertRaises(RuntimeError) as c:
                self.run_auth({**GOOD_ENV,k:"YES"})
            self.assertIn("HOLD_BUY_ENABLED",str(c.exception))
    def test_stage_delta_block_propagates(self):
        with self.assertRaises(RuntimeError):
            self.run_auth(GOOD_ENV,delta=RuntimeError("HOLD_STAGE_DELTA_WRITE_WINDOW"))

class FetchRows(TestCase):
    def resp(self,url="https://www.boatrace.jp/owpc/pc/data/racersearch/course?toban=4001"):
        r=MagicMock(); r.url=url; r.content=b"x"; r.text="<html/>"
        r.apparent_encoding="utf-8"; r.raise_for_status=lambda:None
        return r
    def run_fetch(self,response,parsed):
        client=MagicMock(); client.get.return_value=response
        sess=MagicMock(); sess.__enter__.return_value=client
        fake=MagicMock(); fake.parse_course_stats.return_value=(parsed,{})
        with patch("requests.Session",return_value=sess), \
             patch.dict("sys.modules",{"collect_racer_course_stats_pg":fake}):
            return m.fetch_rows(4001,date(2026,10,30))
    def test_builds_six_stage_rows(self):
        out=self.run_fetch(self.resp(),six())
        self.assertEqual(6,len(out))
        self.assertEqual(set(m.FIELDS),set(out[0]))
        self.assertEqual(m.SOURCE,out[0]["source"])
        self.assertEqual({"entry_rate":10.0,"top3_rate":50.0,"avg_st":.15},out[0]["raw"])
        self.assertEqual(6,len({r["id"] for r in out}))
    def test_redirect_to_other_page_rejected(self):
        with self.assertRaises(RuntimeError):
            self.run_fetch(self.resp("https://www.boatrace.jp/owpc/pc/other?toban=4001"),six())
        with self.assertRaises(RuntimeError):
            self.run_fetch(self.resp("https://evil.example/owpc/pc/data/racersearch/course?toban=4001"),six())
    def test_no_course_data_is_distinct_error(self):
        for parsed in ([],six(e=(None,)*6,t=(None,)*6,s=(None,)*6)):
            with self.assertRaises(m.NoCourseData) as c:
                self.run_fetch(self.resp(),parsed)
            self.assertIn("HOLD_OFFICIAL_COURSE_NO_DATA",str(c.exception))
    def test_out_of_range_page_is_real_failure_not_no_data(self):
        with self.assertRaises(RuntimeError) as c:
            self.run_fetch(self.resp(),six(e=(101,0,0,0,0,0)))
        self.assertNotIsInstance(c.exception,m.NoCourseData)
        self.assertIn("HOLD_OFFICIAL_COURSE_UNRESOLVED",str(c.exception))

class SaveGuards(TestCase):
    def rows(self,day):
        return [{**r,"id":m.snapshot_id(4001,day,r["course"]),"snapshot_date":day,
                 "source":m.SOURCE,"raw":{},"created_at":"x","updated_at":"x"}
                for r in six()]
    def test_non_today_snapshot_rejected_before_db(self):
        with patch.object(m,"authorize"), patch("psycopg.connect") as conn:
            with self.assertRaises(RuntimeError) as c:
                m.save_racer(self.rows(date(2020,1,1)))
            self.assertIn("HOLD_ONLY_TODAY_SNAPSHOT",str(c.exception))
            conn.assert_not_called()
    def test_not_six_rows_rejected(self):
        with patch.object(m,"authorize"):
            with self.assertRaises(ValueError):
                m.save_racer(self.rows(m.today())[:5])
    def test_authorize_called_first(self):
        with patch.object(m,"authorize",side_effect=RuntimeError("HOLD_X")), \
             patch("psycopg.connect") as conn:
            with self.assertRaises(RuntimeError):
                m.save_racer(self.rows(m.today()))
            conn.assert_not_called()

class Main(TestCase):
    def test_plan_makes_no_http_and_no_writes(self):
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///railway"},clear=True), \
             patch.object(m,"pending",return_value=[4001,4002]), \
             patch.object(m,"fetch_rows") as f, patch.object(m,"save_racer") as s, \
             patch.object(m,"authorize") as a:
            self.assertEqual(0,m.main([]))
            f.assert_not_called(); s.assert_not_called(); a.assert_not_called()
    def test_apply_partial_returns_3_and_hold_does_not_stop(self):
        calls=[]
        def fetch(r,d):
            if r==4002: raise RuntimeError("HOLD_OFFICIAL_COURSE_UNRESOLVED")
            return six(r)
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///railway"},clear=True), \
             patch.object(m,"pending",side_effect=[[4001,4002,4003],[4002]]), \
             patch.object(m,"fetch_rows",side_effect=fetch), \
             patch.object(m,"save_racer",side_effect=lambda rows:calls.append(rows) or 6), \
             patch.object(m,"authorize"), patch.object(m.time,"sleep"):
            self.assertEqual(3,m.main(["--apply"]))
        self.assertEqual(2,len(calls))
    def test_consecutive_failures_stop_run(self):
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///railway"},clear=True), \
             patch.object(m,"pending",return_value=list(range(4001,4020))), \
             patch.object(m,"fetch_rows",side_effect=RuntimeError("HOLD_X")) as f, \
             patch.object(m,"authorize"), patch.object(m.time,"sleep"):
            with self.assertRaises(RuntimeError) as c:
                m.main(["--apply"])
            self.assertIn("HOLD_CONSECUTIVE_FAILURES",str(c.exception))
            self.assertEqual(m.MAX_CONSECUTIVE_FAIL,f.call_count)
    def run_apply(self,fetch,racers,pend_after):
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///railway"},clear=True), \
             patch.object(m,"pending",side_effect=[racers,pend_after]), \
             patch.object(m,"fetch_rows",side_effect=fetch) as f, \
             patch.object(m,"save_racer",return_value=6), \
             patch.object(m,"authorize"), patch.object(m.time,"sleep"):
            return f,m.main(["--apply"])
    def test_rookies_do_not_count_toward_consecutive_failures(self):
        def fetch(r,d):
            if r<4000+10: raise m.NoCourseData("HOLD_OFFICIAL_COURSE_NO_DATA")
            return six(r)
        racers=list(range(4001,4021)); rookies=[r for r in racers if r<4010]
        f,code=self.run_apply(fetch,racers,rookies)
        self.assertEqual(20,f.call_count)
        self.assertEqual(0,code)
    def test_rookie_neither_counts_nor_resets_the_streak(self):
        seq=[RuntimeError("HOLD_X")]*4+[m.NoCourseData("n")]+[RuntimeError("HOLD_X")]
        with self.assertRaises(RuntimeError) as c:
            self.run_apply(seq,list(range(4001,4021)),[])
        self.assertIn("HOLD_CONSECUTIVE_FAILURES",str(c.exception))
    def test_success_resets_streak_even_with_rookies_between(self):
        seq=[RuntimeError("HOLD_X")]*4+[six()]+[RuntimeError("HOLD_X")]*4+[six()]
        f,code=self.run_apply(seq,list(range(4001,4011)),[])
        self.assertEqual(3,code)
        self.assertEqual(10,f.call_count)
    def test_no_data_on_every_racer_stops_as_layout_change(self):
        with self.assertRaises(RuntimeError) as c:
            self.run_apply(m.NoCourseData("n"),list(range(4001,4101)),[])
        self.assertIn("LAYOUT_CHANGE",str(c.exception))
    def test_remaining_only_rookies_is_complete(self):
        seq=[six(),m.NoCourseData("n")]
        f,code=self.run_apply(seq,[4001,4002],[4002])
        self.assertEqual(0,code)
    def test_apply_complete_returns_0(self):
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///railway"},clear=True), \
             patch.object(m,"pending",side_effect=[[4001],[]]), \
             patch.object(m,"fetch_rows",return_value=six()), \
             patch.object(m,"save_racer",return_value=6), \
             patch.object(m,"authorize"), patch.object(m.time,"sleep"):
            self.assertEqual(0,m.main(["--apply"]))
    def test_wrong_db_and_bad_limit(self):
        with patch.dict("os.environ",{"DATABASE_URL":"postgresql:///x"},clear=True):
            with self.assertRaises(RuntimeError): m.main([])
        with patch.dict("os.environ",GOOD_ENV,clear=True):
            with self.assertRaises(ValueError): m.main(["--max-racers","0"])

if __name__=="__main__":
    main()
