# -*- coding: utf-8 -*-
"""V5 exhibition forward provenance audit. Read only."""
from __future__ import annotations
import json, os
from datetime import datetime
from db_pg import fetch_all

START=os.getenv("START_DATE","2025-07-01")
END=os.getenv("END_DATE","2026-10-05")
TABLE="v2_bao_exhibition_shadow_snapshots"

def main():
    exists=fetch_all("select to_regclass('public.'||%s) tbl",(TABLE,))
    if not exists or not exists[0].get("tbl"):
        print("V5_EXHIBITION_FORWARD_PROVENANCE_RESULT="+json.dumps({
          "contract":"V5_EXHIBITION_FORWARD_PROVENANCE_V1",
          "table_exists":False,
          "decision":"NOT_READY_NO_TABLE"
        },sort_keys=True))
        return

    rows=fetch_all(f"""
      select x.race_id,x.race_date,x.venue_id,x.race_no,x.captured_at,x.deadline_at,
             x.minutes_before,x.exhibition_times,x.exhibition_time_ranks,x.source,
             exists(select 1 from v2_results rs where rs.race_id=x.race_id) has_result
      from {TABLE} x
      where x.race_date between %s and %s
      order by x.race_date,x.deadline_at,x.race_id
    """,(START,END))

    bad_capture=bad_window=bad_times=bad_ranks=bad_source=bad_minutes=0
    result_rows=0
    dates=set();venues=set();mins=[]
    examples=[]
    for r in rows:
        dates.add(str(r["race_date"])); venues.add(str(r["venue_id"]))
        cap=r["captured_at"]; dl=r["deadline_at"]
        mb=float(r["minutes_before"])
        mins.append(mb)
        result_rows += int(bool(r.get("has_result")))
        ok_capture=cap is not None and dl is not None and cap < dl
        ok_window=8.0 <= mb <= 15.0
        times=list(r.get("exhibition_times") or [])
        ranks=[int(x) for x in (r.get("exhibition_time_ranks") or [])]
        ok_times=len(times)==6 and all(x is not None and float(x)>0 for x in times)
        ok_ranks=len(ranks)==6 and sorted(ranks)==[1,2,3,4,5,6]
        ok_source=str(r.get("source") or "")=="official_beforeinfo"
        calc=None
        if cap is not None and dl is not None:
            calc=(dl-cap).total_seconds()/60.0
        ok_minutes=calc is not None and abs(calc-mb)<=0.05
        bad_capture += int(not ok_capture)
        bad_window += int(not ok_window)
        bad_times += int(not ok_times)
        bad_ranks += int(not ok_ranks)
        bad_source += int(not ok_source)
        bad_minutes += int(not ok_minutes)
        if len(examples)<5 and not (ok_capture and ok_window and ok_times and ok_ranks and ok_source and ok_minutes):
            examples.append({
              "race_id":str(r["race_id"]),"race_date":str(r["race_date"]),
              "minutes_before":mb,"capture_before_deadline":ok_capture,
              "time6":ok_times,"rank_permutation6":ok_ranks,"official_source":ok_source,
              "minutes_consistent":ok_minutes
            })

    n=len(rows)
    valid=n-(bad_capture+0)
    all_safe=(n>0 and bad_capture==0 and bad_window==0 and bad_times==0 and bad_ranks==0 and bad_source==0 and bad_minutes==0)
    out={
      "contract":"V5_EXHIBITION_FORWARD_PROVENANCE_V1",
      "period":{"start":START,"end":END},
      "table_exists":True,
      "rows":n,
      "result_available_rows":result_rows,
      "distinct_dates":len(dates),
      "distinct_venues":len(venues),
      "first_date":min(dates) if dates else None,
      "last_date":max(dates) if dates else None,
      "minutes_before_min":min(mins) if mins else None,
      "minutes_before_max":max(mins) if mins else None,
      "violations":{
        "capture_not_before_deadline":bad_capture,
        "outside_frozen_8_15_window":bad_window,
        "not_six_positive_times":bad_times,
        "rank_not_permutation_1_6":bad_ranks,
        "source_not_official_beforeinfo":bad_source,
        "stored_minutes_mismatch":bad_minutes
      },
      "all_rows_safe_contract":all_safe,
      "enough_rows_for_100_observation_gate":result_rows>=100,
      "examples":examples,
      "decision":(
        "SAFE_FORWARD_EVIDENCE_READY"
        if all_safe and result_rows>=100
        else "SAFE_BUT_MORE_FORWARD_ROWS_NEEDED"
        if all_safe and n>0
        else "NOT_READY"
      ),
      "safety":{"db_write":False,"production_model_change":False,"line_change":False,
                "purchase_change":False,"stake_change":False}
    }
    print("V5_EXHIBITION_FORWARD_PROVENANCE_RESULT="+json.dumps(out,ensure_ascii=False,sort_keys=True,default=str))

if __name__=="__main__":main()
