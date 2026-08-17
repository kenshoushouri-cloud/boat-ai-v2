# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json
from repair_month_all_pg import _fetch, _official_url
from result_detail_pg import parse_result_detail

DATE=os.getenv("RESULT_DETAIL_PROBE_DATE","2026-08-16")
VENUE=os.getenv("RESULT_DETAIL_PROBE_VENUE","24").zfill(2)
RNO=int(os.getenv("RESULT_DETAIL_PROBE_RNO","12"))

def main():
    html=_fetch(_official_url("raceresult",DATE,VENUE,RNO))
    if not html: raise RuntimeError("fetch failed")
    d=parse_result_detail(html)
    print("✅ probe_result_detail_pg.py VERSION 2026-08-17 result-detail-v1", flush=True)
    print(f"winning_method={d.get('winning_method')} finish_order={d.get('finish_order')} finish_rows={d.get('finish_rows_count')} start_rows={d.get('start_rows_count')} start_course_complete={d.get('start_course_complete')}", flush=True)
    for row in d.get("entries",[]):
        print(f"lane={row.get('lane')} racer={row.get('racer_number')} finish={row.get('finish_position')} status={row.get('finish_status')} course={row.get('start_course')} ST={row.get('start_timing')} F={row.get('is_flying')} L={row.get('is_late')} time={row.get('race_time')}", flush=True)
    print("RAW="+json.dumps(d.get("raw"),ensure_ascii=False), flush=True)
if __name__=="__main__": main()