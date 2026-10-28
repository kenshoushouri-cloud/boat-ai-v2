"""Offline unit tests for V5 native deadline sync.

No official HTTP, PostgreSQL, collector, timers or BUY.
"""
from datetime import datetime, timedelta, timezone
from unittest import TestCase, main
from unittest.mock import patch

from v5 import native_deadline_sync as m
from v5 import native_realtime_due_runner as runner

JST=timezone(timedelta(hours=9))
DAY="2026-10-27"
NOW=datetime(2026,10,27,12,2,tzinfo=JST)
TIMES=[f"{h:02d}:{mi:02d}" for h,mi in
       [(12,50),(13,20),(13,50),(14,20),(14,50),(15,20),
        (15,50),(16,20),(16,50),(17,20),(17,50),(18,20)]]
TABLE={i+1:t for i,t in enumerate(TIMES)}

def dt(text,day=DAY):
    return datetime.fromisoformat(f"{day}T{text}:00+09:00")

def rows(venue="10",shift_races=None,table=TABLE):
    """Stored rows equal to the table, except races in shift_races."""
    out=[]
    for no,t in table.items():
        stored=dt(t)+(shift_races or {}).get(no,timedelta(0))
        out.append((f"20261027_{venue}_{no:02d}",stored,
                    stored.strftime("%H:%M")))
    return out

def fetch_ok(table=TABLE,calls=None):
    def fetch(day,venue):
        if calls is not None:
            calls.append(venue)
        v=table[venue] if venue in table else table
        if isinstance(v,Exception):
            raise v
        return v,NOW
    return fetch

class CheckTableTests(TestCase):
    def test_valid(self):
        m.check_table(TABLE)

    def test_not_twelve(self):
        t=dict(TABLE); del t[12]
        with self.assertRaisesRegex(RuntimeError,"NOT_12"):
            m.check_table(t)

    def test_not_strictly_increasing(self):
        for bad in ("13:20","12:00"):
            t=dict(TABLE); t[3]=bad  # equal to 2R / earlier than 2R
            with self.assertRaisesRegex(RuntimeError,"NOT_MONOTONIC"):
                m.check_table(t)

    def test_bad_time_text(self):
        t=dict(TABLE); t[5]="9:5"
        with self.assertRaisesRegex(RuntimeError,"BAD_TIME_TEXT"):
            m.check_table(t)

class OfficialVenueTableTests(TestCase):
    def html(self,venue,links=None,alt="桐生"):
        head="<th>レース</th>"+"".join(f"<th>{i}R</th>" for i in range(1,13))
        cells="".join(f"<td>{t}</td>" for t in TIMES)
        links=[venue] if links is None else links
        a="".join(f'<a href="/owpc/pc/race/raceindex?jcd={c}&hd=20261027">x</a>'
                  for c in links)
        return (f'<html><body><img src="t_01.png" alt="{alt}" />{a}<table>'
                f"<tr>{head}</tr><tr><th>締切予定時刻</th>{cells}</tr>"
                "</table></body></html>")

    def fetch(self,html):
        return patch.object(m,"official_fetch",return_value=(html,NOW))

    def test_one_request_parses_all_twelve(self):
        with self.fetch(self.html("10")) as f:
            texts,cap=m.official_venue_table(DAY,"10")
        f.assert_called_once_with("20261027_10_01")
        self.assertEqual(texts,TABLE)

    def test_venue_name_text_not_required(self):
        # real pages only have the name as <img alt>, never as body text
        with self.fetch(self.html("10",alt="")):
            self.assertEqual(m.official_venue_table(DAY,"10")[0],TABLE)

    def test_other_venue_page_rejected(self):
        with self.fetch(self.html("11")):
            with self.assertRaisesRegex(RuntimeError,"VENUE_CODE_MISMATCH"):
                m.official_venue_table(DAY,"10")

    def test_mixed_or_missing_venue_codes_rejected(self):
        for links in (["10","11"],[]):
            with self.fetch(self.html("10",links=links)):
                with self.assertRaisesRegex(RuntimeError,"VENUE_CODE_MISMATCH"):
                    m.official_venue_table(DAY,"10")

class CompareTests(TestCase):
    def test_one_fetch_per_venue_all_races(self):
        calls=[]
        r=rows("10")+rows("11")
        diffs,holds=m.compare(r,fetch=fetch_ok(calls=calls),
                              sleep=lambda s:None,now=NOW)
        self.assertEqual(sorted(calls),["10","11"])
        self.assertEqual(len(diffs),24)
        self.assertEqual({d["status"] for d in diffs},{"SAME"})
        self.assertEqual(holds,{})

    def test_shift_reject_over_60_and_past(self):
        r=rows("10",{2:timedelta(minutes=-10),     # official later by 10
                     3:timedelta(minutes=-61),     # official later by 61
                     4:timedelta(minutes=10)})     # official earlier by 10
        diffs,_=m.compare(r,fetch=fetch_ok(),sleep=lambda s:None,now=NOW)
        st={d["race_id"][-2:]:d for d in diffs}
        self.assertEqual(st["02"]["status"],"SHIFT")
        self.assertEqual(st["02"]["shift"],timedelta(minutes=10))
        self.assertEqual(st["03"]["reason"],"HOLD_SHIFT_OVER_60MIN")
        self.assertEqual(st["04"]["status"],"SHIFT")
        self.assertEqual(st["04"]["shift"],timedelta(minutes=-10))
        past=datetime(2026,10,27,13,30,tzinfo=JST)  # after 1R/2R official
        diffs,_=m.compare(rows("10",{2:timedelta(minutes=5)}),
                          fetch=fetch_ok(),sleep=lambda s:None,now=past)
        d2=[d for d in diffs if d["race_id"].endswith("_02")][0]
        self.assertEqual(d2["reason"],"HOLD_NEW_DEADLINE_IN_PAST")

    def test_venue_hold_isolated_and_logged(self):
        calls=[]
        table={"10":RuntimeError("HOLD_NOT_MONOTONIC_INCREASING"),"11":TABLE}
        diffs,holds=m.compare(rows("10")+rows("11"),
                              fetch=fetch_ok(table,calls),
                              sleep=lambda s:None,now=NOW)
        self.assertIn("HOLD_NOT_MONOTONIC_INCREASING",holds["10"])
        self.assertEqual({d["venue"] for d in diffs},{"11"})

class SlotTests(TestCase):
    def at(self,h,mi):
        return datetime(2026,10,27,h,mi,tzinfo=JST)

    def test_slot_minutes(self):
        for mi in (0,2,4,15,19,30,34,45,49):
            self.assertIsNone(m.apply_blocked(self.at(12,mi)),mi)
        for mi in (5,14,20,29,35,44,50,59):
            self.assertIn("NOT_APPLY_SLOT",m.apply_blocked(self.at(12,mi)))

    def test_0300_0600_blocked_even_in_slot(self):
        for h,mi in ((3,0),(3,2),(4,17),(5,47)):
            self.assertIn("0300_0600",m.apply_blocked(self.at(h,mi)))
        self.assertIsNone(m.apply_blocked(self.at(6,2)))
        self.assertIsNone(m.apply_blocked(self.at(2,47)))

    def test_apply_outside_slot_does_no_io(self):
        with patch.object(m,"stored_races") as s, \
             patch.object(m,"official_venue_table") as o, \
             patch.object(m,"_connect") as c:
            self.assertIsNone(m.sync(apply=True,now=self.at(12,7)))
            self.assertIsNone(m.sync(apply=True,now=self.at(4,2)))
        s.assert_not_called(); o.assert_not_called(); c.assert_not_called()

class FakeCur:
    def __init__(self,log,rowcounts):
        self.log=log; self.rowcounts=rowcounts; self.rowcount=0
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self,sql,params=None):
        self.log.append((" ".join(sql.split()),params))
        if sql.lstrip().startswith("UPDATE"):
            self.rowcount=self.rowcounts.pop(0)
    def fetchone(self): return (True,)

class FakeConn:
    def __init__(self,rowcounts):
        self.log=[]; self.rowcounts=rowcounts; self.tx=0
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def transaction(self):
        conn=self
        class Tx:
            def __enter__(s): conn.tx+=1; conn.log.append(("BEGIN",None))
            def __exit__(s,*a): conn.log.append(("COMMIT",None)); return False
        return Tx()
    def cursor(self): return FakeCur(self.log,self.rowcounts)

class ApplyTests(TestCase):
    def shifted(self):
        r=rows("10",{2:timedelta(minutes=-10)})+rows("11",{1:timedelta(minutes=5)})
        diffs,_=m.compare(r,fetch=fetch_ok(),sleep=lambda s:None,now=NOW)
        return diffs

    def test_update_and_history_in_same_transaction(self):
        conn=FakeConn([1,1])
        with patch.object(m,"_connect",return_value=conn):
            n=m.apply_changes(self.shifted())
        self.assertEqual(n,2)
        self.assertEqual(conn.tx,2)  # one transaction per venue
        sql=[s for s,_ in conn.log]
        i=sql.index("BEGIN")
        j=sql.index("COMMIT")
        seg=sql[i:j]
        self.assertTrue(any(s.startswith("UPDATE boat_data_stage.races")
                            for s in seg))
        ins=[(s,p) for s,p in conn.log
             if "INSERT INTO boat_data_stage.race_deadline_changes" in s][0]
        p=ins[1]
        self.assertEqual(p[0],"20261027_10_02")
        self.assertEqual(p[1],DAY)
        self.assertEqual(p[6],10)   # delta_minutes
        self.assertEqual(p[5],"13:20")
        self.assertEqual(p[4],"13:10")

    def test_no_history_when_row_changed_meanwhile(self):
        conn=FakeConn([0,1])
        with patch.object(m,"_connect",return_value=conn):
            n=m.apply_changes(self.shifted())
        self.assertEqual(n,1)
        inserts=[s for s,_ in conn.log if "INSERT INTO" in s]
        self.assertEqual(len(inserts),1)

    def test_rejected_and_same_never_written(self):
        r=rows("10",{3:timedelta(minutes=-61)})
        diffs,_=m.compare(r,fetch=fetch_ok(),sleep=lambda s:None,now=NOW)
        with patch.object(m,"_connect") as c:
            self.assertEqual(m.apply_changes(diffs),0)
        c.assert_not_called()

class EntryPointTests(TestCase):
    def test_main_without_flags_does_nothing(self):
        with patch.object(m,"stored_races") as s, \
             patch.object(m,"official_venue_table") as o:
            self.assertEqual(m.main([]),0)
        s.assert_not_called(); o.assert_not_called()

    def test_compare_stage_never_writes_and_lists_all_venues(self):
        r=rows("10",{2:timedelta(minutes=-10)})+rows("11")
        with patch.object(m,"stored_races",return_value=r), \
             patch.object(m,"official_venue_table",
                          return_value=(TABLE,NOW)), \
             patch.object(m,"_connect") as c, \
             patch.object(m,"apply_changes") as ap, \
             patch.object(m,"time"):
            self.assertEqual(m.main(["--compare-stage"]),0)
        ap.assert_not_called(); c.assert_not_called()

    def test_compare_stage_not_blocked_by_clock(self):
        with patch.object(m,"stored_races",return_value=[]) as s, \
             patch.object(m,"apply_blocked") as ab:
            m.sync(apply=False,now=datetime(2026,10,27,4,7,tzinfo=JST))
        s.assert_called_once(); ab.assert_not_called()

    def test_apply_requires_gates_before_any_io(self):
        with patch.object(m,"ready_to_apply",
                          side_effect=RuntimeError("HOLD_X")), \
             patch.object(m,"stored_races") as s:
            with self.assertRaises(RuntimeError):
                m.main(["--apply"])
        s.assert_not_called()

class RunnerTests(TestCase):
    def test_runner_sync_failure_does_not_stop_collection(self):
        with patch.object(runner,"ready_to_apply"), \
             patch.object(runner,"deadline_sync",
                          side_effect=RuntimeError("boom")) as sy, \
             patch.object(runner,"candidates",return_value=[]):
            self.assertEqual(runner.main(["--apply"]),0)
        sy.assert_called_once_with(apply=True)

    def test_runner_plan_mode_never_syncs(self):
        with patch.object(runner,"deadline_sync") as sy, \
             patch.object(runner,"candidates",return_value=[]):
            self.assertEqual(runner.main([]),0)
        sy.assert_not_called()

if __name__=="__main__":
    main()
