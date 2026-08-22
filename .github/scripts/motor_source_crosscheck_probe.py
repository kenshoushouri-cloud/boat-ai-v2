# -*- coding: utf-8 -*-
"""HTTP read-only cross-check of BOAT RACE official motor use-start text and 艇国DB motor aggregate start dates.
No DB writes and no response persistence.
"""
from __future__ import annotations
import re
import time
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

def fetch_text(url,s,label,venue,retries=3):
 last=None
 for attempt in range(1,retries+1):
  try:
   r=s.get(url,timeout=(12,30)); r.raise_for_status()
   print(f'MOTOR_XCHECK_HTTP=venue:{venue} source:{label} attempt:{attempt} status:{r.status_code}',flush=True)
   return BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
  except requests.RequestException as e:
   last=e
   print(f'MOTOR_XCHECK_HTTP=venue:{venue} source:{label} attempt:{attempt} error:{type(e).__name__}',flush=True)
   if attempt<retries: time.sleep(2*attempt)
 raise last

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
 comparable=exact=near=official_ok=teikoku_ok=0
 for v,hd,mno in CASES:
  ou=f'https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={v}'
  du=f'https://boatrace-db.net/stadium/mdetail/pid/{int(v)}/mno/{mno}/'
  ot=dt=None
  try:
   ot=fetch_text(ou,s,'official',v); official_ok+=1
  except Exception as e:
   print(f'MOTOR_XCHECK_SOURCE_FAIL=venue:{v} source:official type:{type(e).__name__}',flush=True)
  try:
   dt=fetch_text(du,s,'teikoku',v); teikoku_ok+=1
  except Exception as e:
   print(f'MOTOR_XCHECK_SOURCE_FAIL=venue:{v} source:teikoku type:{type(e).__name__}',flush=True)
  od=official(ot,hd) if ot else None
  dd=teikoku(dt) if dt else None
  state='not_comparable'; delta='NA'
  if od and dd:
   comparable+=1; n=abs((od-dd).days); delta=str(n)
   if n==0: exact+=1; state='exact'
   elif n<=14: near+=1; state='near_14d'
   else: state='different'
  print(f'MOTOR_XCHECK=venue:{v} official:{od or "UNKNOWN"} teikoku:{dd or "UNKNOWN"} delta_days:{delta} state:{state}',flush=True)
 print(f'MOTOR_XCHECK_SOURCE_SUMMARY=official_http_ok:{official_ok}/{len(CASES)} teikoku_http_ok:{teikoku_ok}/{len(CASES)}',flush=True)
 print(f'MOTOR_XCHECK_SUMMARY=comparable:{comparable} exact:{exact} near14:{near} cases:{len(CASES)}',flush=True)
 print('MOTOR_XCHECK_POLICY=teikoku_is_secondary_not_official_truth',flush=True)
 if comparable == 0:
  print('MOTOR_XCHECK_RESULT=FAIL_NO_COMPARABLE_CASES',flush=True)
  raise SystemExit(2)
 print('MOTOR_XCHECK_RESULT=PASS_READ_ONLY',flush=True)
if __name__=='__main__':main()
