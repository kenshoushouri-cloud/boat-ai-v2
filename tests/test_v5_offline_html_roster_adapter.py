"""Focused adapter test; existing GitHub racelist/exhibition parsers are STUBBED.

BS4 parses actual fictional HTML in the adapter, but this does not test the
real site's markup, source authenticity, or the full real parser dependencies.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib
import re
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from bs4 import BeautifulSoup
from v5.offline_paper_roster_gate import MockFrozenPage

JST = timezone(timedelta(hours=9))
T = datetime(2026, 10, 10, 10, tzinfo=JST)
RID = '20261010_03_04'

# Provide minimal faithful API stubs so adapter logic runs in local isolated
# test workspace, without claiming real dependency/parser integration.
roster_mod = types.ModuleType('v5.official_racelist_readback')
before_mod = types.ModuleType('historical_beforeinfo_parser_v3')

class RacelistNotVerified(ValueError):
    pass

def parse_roster(raw):
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    tables = [t for t in soup.find_all('table') if '登録番号/級別' in t.get_text(' ', strip=True)]
    if len(tables) != 1:
        raise RacelistNotVerified('unstructured')
    out=[]
    for tr in tables[0].find_all('tr'):
        cells=[x.get_text(' ',strip=True) for x in tr.find_all('td', recursive=False)]
        if len(cells)!=2:
            continue
        m=re.fullmatch(r'([1-6])', cells[0]); n=re.fullmatch(r'(\d{4}) / (A1|A2|B1|B2)',cells[1])
        if not (m and n):
            raise RacelistNotVerified('unparsed')
        out.append(dict(lane=int(m[1]), racer_number=int(n[1]), active_verified=False))
    if len(out)!=6 or sorted(x['lane'] for x in out)!=list(range(1,7)) or len({x['racer_number'] for x in out})!=6:
        raise RacelistNotVerified('duplicate')
    return out

def cells(tr):
    return [x.get_text(' ',strip=True) for x in tr.find_all(['td','th'],recursive=False)]

def lane_of(values):
    return int(values[0]) if values and values[0] in set('123456') else None

def inspect(html):
    soup=BeautifulSoup(html,'html.parser'); rows={}
    for tbody in soup.select('tbody.is-fs12'):
        tr=tbody.find('tr')
        if not tr:
            continue
        c=cells(tr); lane=lane_of(c)
        if lane is not None and len(c)>=6:
            try:
                time=float(c[4])
                if 6<=time<8:rows[lane]=time
            except ValueError:
                pass
    if len(rows)==6:
        return dict(status='complete',source='primary_structured_rows', valid_time_count=6, lanes=sorted(rows))
    return dict(status='partial',source='primary_structured_rows', valid_time_count=len(rows), lanes=sorted(rows))

roster_mod._extract_six_entrant_candidates=parse_roster
roster_mod.RacelistNotVerified=RacelistNotVerified
roster_mod.CANCEL_MARKERS=('欠場','出走取消','出場取消','取消','帰郷','不参加')
roster_mod._norm=lambda x:' '.join(x.split())
before_mod.inspect_exhibition_time_page=inspect
before_mod.EXHIBITION_STATUS_COMPLETE='complete'
before_mod._direct_cells=cells
before_mod._lane_from_cells=lane_of
with patch.dict(sys.modules, {'v5.official_racelist_readback':roster_mod,
                               'historical_beforeinfo_parser_v3':before_mod}):
    adapter=importlib.import_module('v5.offline_html_roster_adapter')


def html_roster(rows=None):
    if rows is None: rows=[(i,1000+i) for i in range(1,7)]
    return ('<table><tr><th>登録番号/級別</th></tr>'+''.join(
        f'<tr><td>{i}</td><td>{n} / A1</td></tr>' for i,n in rows)+'</table>').encode()

def html_before(lanes=None,withdraw=None,missing_time=None):
    if lanes is None:lanes=range(1,7)
    return ('<table>'+''.join(
        f'<tbody class="is-fs12"><tr><td>{i}</td><td>Image</td><td>Racer</td>'
        f'<td>52.0</td><td>{"" if i==missing_time else "6.53"}</td><td>0.0</td>'
        f'<td>{"欠場" if i==withdraw else ""}</td></tr></tbody>' for i in lanes)+'</table>').encode('utf-8')

def page(kind,raw=None,at=None):
    if raw is None:raw=html_roster() if kind=='racelist' else html_before()
    url=f'https://www.boatrace.jp/owpc/pc/race/{kind}?rno=4&jcd=03&hd=20261010'
    return MockFrozenPage(kind,url,url,raw,hashlib.sha256(raw).hexdigest(),
                          at or (T if kind=='racelist' else T+timedelta(minutes=1)),
                          T+timedelta(minutes=2))

class TestOfflineRealHtmlAdapterWithParserStubs(unittest.TestCase):
    def audit(self,a=None,b=None,reason='HTML_SIX_LANES_OBSERVED_RACER_BINDING_MISSING_HARD_HOLD', **kw):
        x,y=page('racelist'),page('beforeinfo')
        result=adapter.inspect_offline_html_roster(expected_race_id=kw.get('rid',RID),
             decision_cutoff_at=kw.get('cutoff',T+timedelta(minutes=5)),
             racelist=x if a is None else a, beforeinfo=y if b is None else b,
             enabled=kw.get('enabled',True))
        self.assertEqual(result.reason,reason)
        for key in ('beforeinfo_racer_numbers_bound','paper_shadow_shape_eligible',
                    'original_first_observation_verified','independently_authenticated_source',
                    'six_active_starts_confirmed','beforeinfo_first_write_eligible',
                    'selection_eligible','forward_eligible','buy_eligible'):
            self.assertIs(getattr(result,key),False)
        self.assertTrue(result.no_get_sql_write)
        if reason != 'HTML_SIX_LANES_OBSERVED_RACER_BINDING_MISSING_HARD_HOLD':
            self.assertEqual((result.matched_exhibition_lanes,result.race_id),(0,''))
        return result

    def test_matched_six_html_lanes_but_no_beforeinfo_ids(self):
        result=self.audit()
        self.assertTrue(result.lane_only_paper_observation)
        self.assertTrue(result.racelist_six_unique_racers)
        self.assertEqual(result.matched_exhibition_lanes,6)
        with self.assertRaises(dataclasses.FrozenInstanceError):result.buy_eligible=True

    def test_disabled_default_and_truthy_rejected(self):
        a,b=page('racelist'),page('beforeinfo')
        v=adapter.inspect_offline_html_roster(expected_race_id=RID,
            decision_cutoff_at=T+timedelta(minutes=5), racelist=a,beforeinfo=b)
        self.assertEqual(v.reason,'HTML_OFFLINE_OPT_IN_REQUIRED')
        for enabled in (1,False,None,'yes'):
            self.audit(enabled=enabled,reason='HTML_OFFLINE_OPT_IN_REQUIRED')

    def test_bad_race_day(self):
        self.audit(rid='20260230_03_04',reason='HTML_RACE_OR_CUTOFF_INVALID')
    def test_wrong_cutoff_day(self):
        self.audit(cutoff=T+timedelta(days=1),reason='HTML_RACE_OR_CUTOFF_INVALID')
    def test_missing_page(self):
        self.audit(b='wrong',reason='HTML_SOURCE_PAGES_REQUIRED')
    def test_race_url_mismatch(self):
        a=page('racelist')
        self.audit(a=dataclasses.replace(a,requested_url=a.requested_url.replace('rno=4','rno=5')),
                   reason='HTML_URL_IDENTITY_INVALID')
    def test_redirect_is_rejected(self):
        b=page('beforeinfo')
        self.audit(b=dataclasses.replace(b,final_url=b.final_url+'#x'),reason='HTML_URL_IDENTITY_INVALID')
    def test_first_write_promotion_rejected(self):
        a=page('racelist')
        self.audit(a=dataclasses.replace(a,first_write_confirmed=True),
                   reason='HTML_FORGED_AUTHORITY_OR_MUTABLE_SOURCE')
    def test_mutable_history_rejected(self):
        a=page('racelist')
        self.audit(a=dataclasses.replace(a,mutable_or_upsert_only=True),
                   reason='HTML_FORGED_AUTHORITY_OR_MUTABLE_SOURCE')
    def test_hash_mismatch_rejected(self):
        a=page('racelist')
        self.audit(a=dataclasses.replace(a,raw_sha256='a'*64),reason='HTML_BYTES_DIGEST_INVALID')
    def test_invalid_source_order(self):
        a=page('racelist',at=T+timedelta(minutes=2))
        self.audit(a=a,reason='HTML_SOURCE_CLOCK_ORDER_INVALID')
    def test_not_frozen_before_cutoff(self):
        self.audit(cutoff=T+timedelta(minutes=2),reason='HTML_NOT_FROZEN_BEFORE_CUTOFF')
    def test_duplicate_racelist_racers(self):
        a=page('racelist',raw=html_roster([(1,1001),(2,1002),(3,1003),(4,1004),(5,1005),(6,1005)]))
        self.audit(a=a,reason='HTML_RACELIST_SIX_RACER_PARSE_FAILED')
    def test_duplicate_beforeinfo_structured_lane(self):
        b=page('beforeinfo',raw=html_before(lanes=[1,2,3,4,5,5]))
        self.audit(b=b,reason='HTML_BEFOREINFO_STRUCTURED_SIX_LANES_UNVERIFIED')
    def test_withdrawal_denied(self):
        b=page('beforeinfo',raw=html_before(withdraw=3))
        self.audit(b=b,reason='HTML_BEFOREINFO_WITHDRAWAL_DISPLAYED')
    def test_missing_exhibition_rejected(self):
        b=page('beforeinfo',raw=html_before(missing_time=4))
        self.audit(b=b,reason='HTML_BEFOREINFO_EXHIBITION_INCOMPLETE_OR_FALLBACK')
    def test_invalid_utf8_rejected(self):
        b=page('beforeinfo',raw=b'\xff')
        self.audit(b=b,reason='HTML_BEFOREINFO_PARSE_FAILED')

if __name__=='__main__':unittest.main()
