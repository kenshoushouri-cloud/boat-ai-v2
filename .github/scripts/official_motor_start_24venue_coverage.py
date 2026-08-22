# -*- coding: utf-8 -*-
"""HTTP read-only coverage audit for official motor use-start dates across 24 venues.
No DB writes and no raw HTML persistence.
"""
from __future__ import annotations
import re, time
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup

VENUES=[f"{i:02d}" for i in range(1,25)]
TODAY=date(2026,8,22)
PATTERNS=[
 re.compile(r"(?:現行の)?モーター(?:は|の)?[^。]{0,50}?使用開始(?:が|は)?\s*(\d{1,2})月(\d{1,2})日"),
 re.compile(r"モーター(?:は|の)?[^。]{0,40}?(\d{1,2})月(\d{1,2})日から使用"),
 re.compile(r"(?:使用開始|使用開始日)[^0-9]{0,15}(\d{1,2})月(\d{1,2})日"),
]
def resolve_year(hd,m,d):
 e=date(int(hd[:4]),int(hd[4:6]),int(hd[6:8])); c=date(e.year,m,d)
 return date(e.year-1,m,d) if c>e else c
def parse(text,hd):
 t=re.sub(r"\s+","",text)
 for i,p in enumerate(PATTERNS,1):
  m=p.search(t)
  if m:
   try:return resolve_year(hd,int(m.group(1)),int(m.group(2))),i
   except ValueError:pass
 return None,None
def main():
 print("MOTOR_24V_MODE=http_read_only_no_persistence",flush=True)
 s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0"})
 explicit=unknown=http_fail=0
 # Probe a small recent date window; stop at first HTTP-200 page with meaningful motor table text per venue.
 for v in VENUES:
  found_page=False
  for back in range(0,15):
   d=TODAY-timedelta(days=back); hd=d.strftime("%Y%m%d")
   url=f"https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={v}"
   try:r=s.get(url,timeout=20)
   except requests.RequestException:
    continue
   if r.status_code!=200: continue
   text=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
   # Avoid treating generic/error pages as a venue observation.
   if "モーター" not in text or len(text)<500: continue
   found_page=True; dt,pat=parse(text,hd)
   if dt:
    explicit+=1; print(f"MOTOR_24V=venue:{v} hd:{hd} state:explicit start:{dt} pattern:{pat}",flush=True)
   else:
    unknown+=1; print(f"MOTOR_24V=venue:{v} hd:{hd} state:unknown",flush=True)
   break
  if not found_page:
   http_fail+=1; print(f"MOTOR_24V=venue:{v} state:no_recent_page",flush=True)
  time.sleep(.15)
 print(f"MOTOR_24V_SUMMARY=explicit:{explicit} unknown:{unknown} no_recent_page:{http_fail} venues:{len(VENUES)}",flush=True)
 print("MOTOR_24V_RESULT=PASS_READ_ONLY",flush=True)
if __name__=='__main__': main()
