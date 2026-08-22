# -*- coding: utf-8 -*-
"""HTTP read-only cross-check of BOAT RACE official motor use-start text and 艇国DB motor aggregate start dates.
No DB writes and no response persistence.
"""
from __future__ import annotations
import re
from datetime import date
import requests
from bs4 import BeautifulSoup

CASES=[
 # venue, official event date known to expose explicit start, representative motor number for 艇国DB
 ('06','20260526','1'),
 ('13','20260609','1'),
 ('24','20260617','1'),
]
OFFICIAL_PATTERNS=[
 re.compile(r'(?:現行の)?モーター(?:は|の)?[^。]{0,50}?使用開始(?:が|は)?\s*(\d{1,2})月(\d{1,2})日'),
 re.compile(r'モーター(?:は|の)?[^。]{0,40}?(\d{1,2})月(\d{1,2})日から使用'),
 re.compile(r'(?:使用開始|使用開始日)[^0-9]{0,15}(\d{1,2})月(\d{1,2})日'),
]
DB_PATTERNS=[
 re.compile(r'集計期間[：:]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日'),
 re.compile(r'集計期間[：:]?\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})'),
]
def text(url,s):
 r=s.get(url,timeout=25); r.raise_for_status(); return BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
def official(t,hd):
 x=re.sub(r'\s+','',t); e=date(int(hd[:4]),int(hd[4:6]),int(hd[6:8]))
 for p in OFFICIAL_PATTERNS:
  m=p.search(x)
  if m:
   d=date(e.year,int(m.group(1)),int(m.group(2)))
   return date(e.year-1,d.month,d.day) if d>e else d
 return None
def teikoku(t):
 x=re.sub(r'\s+','',t)
 for p in DB_PATTERNS:
  m=p.search(x)
  if m:return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
 return None
def main():
 print('MOTOR_XCHECK_MODE=http_read_only_no_persistence',flush=True)
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0'})
 comparable=exact=near=0
 for v,hd,mno in CASES:
  ou=f'https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={v}'
  du=f'https://boatrace-db.net/stadium/mdetail/pid/{int(v)}/mno/{mno}/'
  try:
   od=official(text(ou,s),hd); dd=teikoku(text(du,s))
  except Exception as e:
   print(f'MOTOR_XCHECK=venue:{v} state:http_error type:{type(e).__name__}',flush=True); continue
  state='not_comparable'; delta='NA'
  if od and dd:
   comparable+=1; n=abs((od-dd).days); delta=str(n)
   if n==0: exact+=1; state='exact'
   elif n<=14: near+=1; state='near_14d'
   else: state='different'
  print(f'MOTOR_XCHECK=venue:{v} official:{od or "UNKNOWN"} teikoku:{dd or "UNKNOWN"} delta_days:{delta} state:{state}',flush=True)
 print(f'MOTOR_XCHECK_SUMMARY=comparable:{comparable} exact:{exact} near14:{near} cases:{len(CASES)}',flush=True)
 print('MOTOR_XCHECK_POLICY=teikoku_is_secondary_not_official_truth',flush=True)
 print('MOTOR_XCHECK_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
