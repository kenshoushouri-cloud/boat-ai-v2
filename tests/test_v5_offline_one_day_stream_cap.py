"""Synthetic one-row-at-a-time limit guards. No DB / Railway calls."""
import unittest
from datetime import date
from unittest.mock import Mock
from v5.offline_one_day_stream_cap import (
    FeatureStream, StreamStopped, read_one_day_features, read_one_day_postrace,
    iter_server_cursor, reviewed_select_statements,
)
from v5.offline_catalog_smoke_gate import FirstDaySmoke

DAY = date(2026, 5, 1)


def make_factory(counts, counters=None, size=16):
    def factory(q):
        if counters is not None:
            counters.append(q)
        for n in range(counts.get(q, 0)):
            yield {"label": q, "n": n, "data": "x"*size}
    return factory


class StreamCapTests(unittest.TestCase):
    def test_q3_not_read_in_feature_stage(self):
        called = []
        a = read_one_day_features(DAY, make_factory({"Q1":2,"Q2":12},called))
        self.assertEqual(called,["Q1","Q2"])
        self.assertEqual(len(a.lanes),12)
        self.assertFalse(a.buy_eligible)

    def test_q3_requires_explicit_seal(self):
        called = []
        a = read_one_day_features(DAY, make_factory({"Q1":1,"Q2":6}))
        with self.assertRaisesRegex(StreamStopped,"FROZEN_SELECTION_REQUIRED"):
            read_one_day_postrace(a,make_factory({"Q3":1},called))
        self.assertEqual(called,[])

    def test_three_streams_pass_but_never_actual_roi(self):
        a = read_one_day_features(DAY,make_factory({"Q1":2,"Q2":12}))
        b = read_one_day_postrace(a,make_factory({"Q3":2}),selection_sealed=True)
        self.assertEqual(len(b.results),2)
        self.assertFalse(b.actual_roi_verified)
        self.assertFalse(b.buy_eligible)

    def test_none_row_is_rejected_not_treated_as_eof(self):
        def factory(_):
            yield {"ok": 1}
            yield None
        with self.assertRaisesRegex(StreamStopped,"UNEXPECTED_ROW_TYPE"):
            read_one_day_features(DAY, factory)

    def test_q1_cap_stops_source_early_and_never_reads_q2(self):
        calls, closed = [], []
        def factory(q):
            calls.append(q)
            try:
                for n in range(100):
                    calls.append(n)
                    yield {"i": n}
            finally:
                closed.append(q)
        contract = FirstDaySmoke(DAY,max_inventory_rows=2)
        with self.assertRaisesRegex(StreamStopped,"Q1_ROW_LIMIT_EXCEEDED"):
            read_one_day_features(DAY,factory,contract)
        self.assertEqual(len([v for v in calls if type(v) is int]),3)
        self.assertEqual(closed,["Q1"])
        self.assertNotIn("Q2",calls)

    def test_single_row_oversize_immediate_hold(self):
        with self.assertRaisesRegex(StreamStopped,"ONE_ROW_TOO_LARGE"):
            read_one_day_features(DAY,make_factory({"Q1":1,"Q2":6},size=64_100))

    def test_total_bytes_limit_during_feature_stream(self):
        limit = FirstDaySmoke(DAY,max_total_bytes=150)
        with self.assertRaisesRegex(StreamStopped,"DECODED_BYTES_LIMIT_EXCEEDED"):
            read_one_day_features(DAY,make_factory({"Q1":1,"Q2":6}),limit)

    def test_q2_count_short_no_auto_trim(self):
        with self.assertRaisesRegex(StreamStopped,"Q2_RAW_ROW_COUNT_MISMATCH"):
            read_one_day_features(DAY,make_factory({"Q1":2,"Q2":11}))

    def test_q3_count_short_no_auto_trim(self):
        a=read_one_day_features(DAY,make_factory({"Q1":2,"Q2":12}))
        with self.assertRaisesRegex(StreamStopped,"Q3_RAW_ROW_COUNT_MISMATCH"):
            read_one_day_postrace(a,make_factory({"Q3":1}),selection_sealed=True)

    def test_q3_bytes_respect_prior_stream_budget(self):
        a=read_one_day_features(DAY,make_factory({"Q1":1,"Q2":6},size=40))
        small=FirstDaySmoke(DAY,max_total_bytes=a.decoded_bytes+5)
        with self.assertRaisesRegex(StreamStopped,"Q3_DECODED_BYTES_LIMIT_EXCEEDED"):
            read_one_day_postrace(a,make_factory({"Q3":1}),selection_sealed=True,contract=small)

    def test_empty_q1_not_assumed_holiday(self):
        with self.assertRaisesRegex(StreamStopped,"EMPTY_INVENTORY_UNKNOWN_NOT_HOLIDAY"):
            read_one_day_features(DAY,make_factory({"Q1":0}))

    def test_sql_pin_rejects_tampering(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            fp=Path(tmp)/"source.sql"
            fp.write_text("WITH p AS (SELECT 1) SELECT 1;",encoding="utf-8")
            with self.assertRaisesRegex(StreamStopped,"UNREVIEWED_SOURCE_SQL"):
                reviewed_select_statements(fp)

    def test_server_cursor_disabled_before_use(self):
        conn=Mock()
        source=iter_server_cursor(conn,"SELECT 1",{})
        with self.assertRaisesRegex(StreamStopped,"DB_FETCH_DISABLED_BY_DEFAULT"):
            next(source)
        conn.cursor.assert_not_called()

    def test_one_row_fetch_cursor_is_closed_on_overrun(self):
        class Cursor:
            itersize=100
            def __init__(self): self.n=0;self.closed=False
            def __enter__(self):return self
            def __exit__(self,*args):self.closed=True
            def execute(self, sql, params):pass
            def fetchone(self):
                self.n+=1
                return {"i":self.n}
        cur=Cursor()
        conn=Mock();conn.cursor.return_value=cur
        def factory(_label):
            return iter_server_cursor(conn,"SELECT 1",{},explicit_manual_read=True)
        with self.assertRaisesRegex(StreamStopped,"Q1_ROW_LIMIT_EXCEEDED"):
            read_one_day_features(DAY,factory,FirstDaySmoke(DAY,max_inventory_rows=1))
        self.assertEqual(cur.itersize,1)
        self.assertEqual(cur.n,2)
        self.assertTrue(cur.closed)


if __name__ == "__main__":
    unittest.main()
