"""Offline-only tests. Fake psycopg never opens a network connection."""
import os
import re
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from v5.historical_odds_readonly_sample_audit_pg import (
    REQUIRED, checked_race_ids, run_sample_audit, summarize_odds,
)

RID = '20261005_03_01'

class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.query = ''
    def __enter__(self): return self
    def __exit__(self, *unused): pass
    def execute(self, sql, params=None):
        q = ' '.join(sql.split())
        self.conn.commands.append((q,params))
        assert not re.match(r'^(INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER|CREATE|COPY)',q,re.I)
        self.query = q
    def fetchall(self):
        q = self.query
        if 'information_schema.columns' in q:
            data=[{'table_name':t,'column_name':c} for t,fields in REQUIRED.items() for c in fields]
            if self.conn.no_columns: data=[r for r in data if r['column_name'] != 'odds']
            return data
        if 'FROM pg_indexes' in q:
            return ([{'tablename':t,'indexdef':f'CREATE INDEX t ON public.{t} USING btree (race_id)'}
                     for t in REQUIRED if t!='v2_results' or not self.conn.no_index])
        if 'FROM v2_odds_trifecta' in q:
            return [{'race_id':RID,'n':120,'valid':120,'distinct_tickets':self.conn.distinct,
                     'final':120,'nonfinal':0,'missing_final':0,
                     'oldest_stored_fetch':datetime(2026,10,6,tzinfo=timezone.utc),
                     'newest_stored_fetch':datetime(2026,10,6,tzinfo=timezone.utc)}]
        if 'FROM v2_results' in q:
            return [{'race_id':RID,'result_status':'official','race_status':'official',
                     'trifecta_ticket':'1-2-3','trifecta_payout_yen':12340}]
        if 'FROM v2_result_entries' in q:
            return [{'race_id':RID,'rows':6,'flying':1,'late':0}]
        raise AssertionError('unexpected query '+q)

class Connection:
    def __init__(self, **opts):
        self.opts=opts;self.commands=[];self.no_columns=False;self.no_index=False;self.distinct=120
    def __enter__(self):return self
    def __exit__(self,*unused):pass
    def cursor(self):return Cursor(self)

class TestOfflineHistoricalOddsSample(unittest.TestCase):
    def test_off_by_default_no_db_access(self):
        with patch.dict(os.environ,{'V5_READONLY_ODDS_AUDIT':'', 'V5_AUDIT_RACE_IDS':RID},clear=True):
            self.assertEqual(run_sample_audit(),{'status':'DISABLED_BY_DEFAULT','database_read_executed':False})

    def test_exact_opt_in_only(self):
        with patch.dict(os.environ,{'V5_READONLY_ODDS_AUDIT':'true'},clear=True):
            self.assertEqual(run_sample_audit()['status'],'DISABLED_BY_DEFAULT')

    def test_missing_ids_rejected(self):
        for value in (None,'','20261005_03_01,','20261005_03_01,20261005_03_01',
                      '20261005_03_01,20261005_03_02,20261005_03_03,20261005_03_04'):
            with self.subTest(value=value), self.assertRaises(ValueError):checked_race_ids(value)

    def test_invalid_date_and_range_rejected(self):
        for value in ('20250230_03_01','20250630_03_01','20261005_25_01','20261005_03_13','bad'):
            with self.subTest(value=value),self.assertRaises(ValueError):checked_race_ids(value)

    def test_valid_3_ids(self):
        self.assertEqual(len(checked_race_ids(','.join(f'20261005_03_0{i}' for i in range(1,4)))),3)

    def test_exactly_120_distinct_valid_and_final(self):
        self.assertEqual(summarize_odds(120,120,120,120,0,0),
                         '120_RECORDED_FINAL_FLAG_CANDIDATE_NOT_SOURCE_PROOF')

    def test_duplicate_tickets_denied_even_with_120_rows(self):
        self.assertEqual(summarize_odds(120,120,119,120,0,0),'NOT_120_COMPLETE_OR_INVALID_TICKETS')

    def test_invalid_ticket_or_odds_denied(self):
        self.assertEqual(summarize_odds(120,119,120,120,0,0),'NOT_120_COMPLETE_OR_INVALID_TICKETS')

    def test_nonfinal_and_mixed_distinguished(self):
        self.assertEqual(summarize_odds(120,120,120,0,120,0),'120_RECORDED_NONFINAL_FLAG_NOT_CLOSING_PROOF')
        self.assertEqual(summarize_odds(120,120,120,60,60,0),'FINAL_FLAG_MIXED_OR_NULL')
        self.assertEqual(summarize_odds(0,0,0,0,0,0),'NO_ROWS_FOR_SAMPLED_RACE')

    def test_no_database_url_rejected_preconnect(self):
        with patch.dict(os.environ,{'V5_READONLY_ODDS_AUDIT':'YES_READ_ONLY','V5_AUDIT_RACE_IDS':RID},clear=True):
            with self.assertRaisesRegex(RuntimeError,'DATABASE_URL_REQUIRED'):run_sample_audit()

    def fake_run(self, configure=None):
        holder=[]
        def connect(*args,**kwargs):
            c=Connection(**kwargs);holder.append(c)
            if configure:configure(c)
            return c
        lib=types.ModuleType('psycopg'); lib.connect=connect
        rows=types.ModuleType('psycopg.rows');rows.dict_row=object();lib.rows=rows
        env={'V5_READONLY_ODDS_AUDIT':'YES_READ_ONLY','V5_AUDIT_RACE_IDS':RID,
             'DATABASE_URL':'mock-no-network'}
        with patch.dict(sys.modules,{'psycopg':lib,'psycopg.rows':rows}),patch.dict(os.environ,env,clear=True):
            result=run_sample_audit()
        self.assertEqual(holder[0].commands[0][0],'BEGIN READ ONLY')
        self.assertEqual(holder[0].commands[-1][0],'ROLLBACK')
        self.assertTrue(all(not re.match(r'^(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)',x[0]) for x in holder[0].commands))
        self.assertTrue(all(len(x[1])==1 and x[1][0]==[RID] for x in holder[0].commands
                            if x[1] is not None and x[0].startswith('SELECT race_id')))
        return result

    def test_fake_db_120_final_flags_not_source_proof(self):
        r=self.fake_run()
        self.assertEqual(r['sample'][0]['odds_shape_verdict'],
                         '120_RECORDED_FINAL_FLAG_CANDIDATE_NOT_SOURCE_PROOF')
        self.assertEqual(r['sample'][0]['flying_lanes'],1)
        for flag in ('before_deadline_odds_verified','source_authenticated','v5_roi_verified',
                     'forward_eligible','buy_eligible'):
            self.assertFalse(r[flag])

    def test_fake_db_duplicate_detected(self):
        r=self.fake_run(lambda c:setattr(c,'distinct',119))
        self.assertEqual(r['sample'][0]['odds_shape_verdict'],'NOT_120_COMPLETE_OR_INVALID_TICKETS')

    def test_missing_columns_fails_closed(self):
        r=self.fake_run(lambda c:setattr(c,'no_columns',True))
        self.assertEqual(r['status'],'REQUIRED_COLUMNS_UNAVAILABLE')

    def test_no_race_id_index_fails_closed(self):
        r=self.fake_run(lambda c:setattr(c,'no_index',True))
        self.assertEqual(r['status'],'RACE_ID_LEADING_INDEX_UNVERIFIED')

if __name__=='__main__':unittest.main()
