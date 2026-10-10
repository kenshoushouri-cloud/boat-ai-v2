# -*- coding: utf-8 -*-
"""Read-only current-V4 head-error attribution by actual start-course movement."""
from __future__ import annotations
import importlib.util, json, math, os, sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
import psycopg
from psycopg.rows import dict_row
from research import candidate_discovery_v4_contract as v4
from research.v4_course_entry_error_contract import (
    BLOCKS, END_DATE, EXPECTED_CONTROL_DAYS, OFFICIAL_RESULT_ENTRY_SOURCE,
    PURE_EVAL_START_BLOCK, START_DATE, contract_metadata,
)

VERSION="2026-09-27-v4-course-entry-error-diagnostic-v1"
PINNED_LONG_HELPER_SHA="ac91c9a2e9570d3af3589e2e98b6529a77c14756"
OUTPUT_JSON=Path(os.getenv("V4_COURSE_ERROR_OUTPUT_JSON","v4-course-entry-error-diagnostic.json"))
LONG_HELPER_PATH=Path(os.getenv("V4_LONG_HELPER_PATH",Path(__file__).resolve().parent/"v4_long_history_walkforward_pg.py"))
EPS=1e-15


def load_long_helper():
    spec=importlib.util.spec_from_file_location("v4_course_error_long_helper",LONG_HELPER_PATH)
    if spec is None or spec.loader is None: raise RuntimeError("cannot load long helper")
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def daterange(a: date,b: date)->Iterable[date]:
    d=a
    while d<=b:
        yield d
        d+=timedelta(days=1)


def split_blocks(days:list[str],blocks:int=BLOCKS)->list[list[str]]:
    q,r=divmod(len(days),blocks); out=[]; pos=0
    for i in range(blocks):
        n=q+(1 if i<r else 0); out.append(days[pos:pos+n]); pos+=n
    return out


def block_bounds(days:list[str])->list[dict[str,Any]]:
    return [{"block":i+1,"start":g[0],"end":g[-1],"days":len(g)}
            for i,g in enumerate(split_blocks(days)) if g]


def block_for(day:str,bounds:list[dict[str,Any]])->int:
    if not bounds: raise ValueError("block bounds required")
    for row in bounds:
        if day<=str(row["end"]): return int(row["block"])
    return int(bounds[-1]["block"])


def first_place_marginal(probs:Mapping[str,float])->dict[int,float]:
    out={i:0.0 for i in range(1,7)}
    for ticket,p in probs.items(): out[int(ticket.split("-",1)[0])]+=float(p)
    z=sum(out.values())
    return {i:out[i]/z for i in out}


def prediction_metrics(probs:Mapping[str,float],actual_ticket:str)->dict[str,Any]:
    head=first_place_marginal(probs); actual=int(actual_ticket.split("-",1)[0])
    predicted=min(range(1,7),key=lambda lane:(-head[lane],lane))
    pa=max(EPS,head[actual])
    return {
        "predicted_head":predicted,
        "actual_head":actual,
        "head_correct":predicted==actual,
        "head_log_loss":-math.log(pa),
        "head_brier":sum((head[l]-(1.0 if l==actual else 0.0))**2 for l in range(1,7)),
    }


def prepare_day(helper,cur,day):
    races,entries_by,course_by,opponent_by=helper.fetch_day_inputs(cur,day)
    cutoff=helper.cutoff_for(day); distributions={}; meta={}
    for race in races:
        rid=str(race.get("race_id") or ""); entries=entries_by.get(rid,[])
        deadline=helper.aware_jst(race.get("deadline_at"))
        if len(entries)!=6 or deadline is None: continue
        try: base=helper.base_raw(entries,str(race.get("venue_id") or ""))
        except Exception: continue
        course=helper.course_map(entries=entries,deadline=deadline,cutoff=cutoff,course_by=course_by)
        opponent=helper.opponent_delta(row=opponent_by.get(rid),race_day=day,deadline=deadline,cutoff=cutoff)
        motor=helper.motor_map(entries)
        distributions[rid]=v4.build_v4_distribution(
            base_raw=base,course_top3=course,motor_place2=motor,opponent_delta=opponent)
        meta[rid]={"deadline_at":deadline}
    selected=v4.select_daily(distributions,race_cap=v4.CORE_RACES,ticket_count=v4.CORE_TICKETS)
    return {"cutoff":cutoff,"distributions":distributions,"selected":selected,"meta":meta}


def fetch_course_cards(cur,race_ids:list[str])->dict[str,dict[int,int]]:
    if not race_ids:return {}
    cur.execute("""
      select race_id,lane,start_course
        from v2_result_entries
       where race_id=any(%s)
         and coalesce(source,'')=%s
       order by race_id,lane
    """,(race_ids,OFFICIAL_RESULT_ENTRY_SOURCE))
    grouped:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in cur.fetchall(): grouped[str(row["race_id"])].append(dict(row))
    out={}
    for rid,rows in grouped.items():
        card={int(x["lane"]):int(x["start_course"]) for x in rows
              if x.get("lane") is not None and x.get("start_course") is not None
              and 1<=int(x["lane"])<=6 and 1<=int(x["start_course"])<=6}
        if set(card)==set(range(1,7)) and set(card.values())==set(range(1,7)):
            out[rid]=card
    return out


def aggregate(rows:list[dict[str,Any]])->dict[str,Any]:
    n=len(rows)
    if not n:return {"days":0,"head_accuracy_percent":None,"head_log_loss":None,"head_brier":None}
    return {
        "days":n,
        "head_accuracy_percent":round(100*sum(bool(r["head_correct"]) for r in rows)/n,6),
        "head_log_loss":round(sum(float(r["head_log_loss"]) for r in rows)/n,9),
        "head_brier":round(sum(float(r["head_brier"]) for r in rows)/n,9),
    }


def summarize(rows:list[dict[str,Any]],bounds:list[dict[str,Any]])->dict[str,Any]:
    pure=[r for r in rows if block_for(r["date"],bounds)>=PURE_EVAL_START_BLOCK]
    strata={
      "all_course_known":pure,
      "no_course_change":[r for r in pure if not r["any_course_change"]],
      "any_course_change":[r for r in pure if r["any_course_change"]],
      "predicted_head_not_moved":[r for r in pure if not r["predicted_head_moved"]],
      "predicted_head_moved":[r for r in pure if r["predicted_head_moved"]],
      "lane1_not_displaced":[r for r in pure if not r["lane1_displaced"]],
      "lane1_displaced":[r for r in pure if r["lane1_displaced"]],
      "winner_not_moved":[r for r in pure if not r["winner_moved"]],
      "winner_moved":[r for r in pure if r["winner_moved"]],
    }
    return {
      "blocks_3_10":{k:aggregate(v) for k,v in strata.items()},
      "blocks":{
        str(b):{
          k:aggregate([r for r in v if block_for(r["date"],bounds)==b])
          for k,v in strata.items()
        } for b in range(1,BLOCKS+1)
      }
    }


def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db: raise RuntimeError("DATABASE_URL required")
    helper=load_long_helper(); start=date.fromisoformat(START_DATE); end=date.fromisoformat(END_DATE)
    rows=[]; status=Counter(); control_dates=[]; calendar=0
    print(f"V4_COURSE_ERROR_VERSION={VERSION}",flush=True)
    print("POLICY=READ_ONLY ERROR_ATTRIBUTION_ONLY ACTUAL_COURSE_NOT_PREDICTOR NO_ODDS NO_RETUNE PURCHASE_FALSE",flush=True)
    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
      with conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("set local statement_timeout='20min'")
        cur.execute("set local lock_timeout='10s'")
        cur.execute("set local max_parallel_workers_per_gather=0")
        for idx,day in enumerate(daterange(start,end),1):
          calendar+=1
          prepared=prepare_day(helper,cur,day)
          selected=prepared["selected"]
          ids=[str(x["race_id"]) for x in selected]
          if len(ids)!=v4.CORE_RACES or any(prepared["meta"][rid]["deadline_at"]<=prepared["cutoff"] for rid in ids):
            status["UNEVALUATED_CONTROL"]+=1; continue

          # Predictor and selection are frozen above. Only now access outcomes/course.
          results=helper.fetch_selected_results(cur,day,ids)
          if any(rid not in results for rid in ids):
            status["UNEVALUATED_RESULT"]+=1; continue
          control_dates.append(day.isoformat())
          rid=ids[0]
          course_cards=fetch_course_cards(cur,ids)
          card=course_cards.get(rid)
          if card is None:
            status["EVALUATED_RESULT_COURSE_UNKNOWN"]+=1; continue
          actual=helper.norm_ticket(results[rid].get("trifecta_ticket"))
          if actual is None: raise RuntimeError(f"malformed result {rid}")
          metrics=prediction_metrics(prepared["distributions"][rid],actual)
          pred=metrics["predicted_head"]; winner=metrics["actual_head"]
          row={
            "date":day.isoformat(),"race_id":rid,**metrics,
            "any_course_change":any(lane!=course for lane,course in card.items()),
            "predicted_head_moved":card[pred]!=pred,
            "winner_moved":card[winner]!=winner,
            "lane1_displaced":card[1]!=1,
            "predicted_head_start_course":card[pred],
            "winner_start_course":card[winner],
          }
          rows.append(row); status["EVALUATED_COURSE6"]+=1
          if idx%25==0: print(f"PROGRESS={day.isoformat()} control_days={len(control_dates)} course6={len(rows)}",flush=True)
      conn.rollback()

    if len(control_dates)!=EXPECTED_CONTROL_DAYS:
      raise RuntimeError(f"control evaluated-day drift: expected {EXPECTED_CONTROL_DAYS}, got {len(control_dates)}")
    bounds=block_bounds(control_dates)
    result={
      "contract":"v4_course_entry_error_attribution_v1",
      "version":VERSION,
      "pinned_long_helper_sha":PINNED_LONG_HELPER_SHA,
      "preregistered_contract":contract_metadata(),
      "policy":{
        "db_transaction_read_only":True,
        "actual_start_course_is_predictor_input":False,
        "result_and_course_query_after_selection_freeze":True,
        "odds_used":False,"threshold_search":False,"coefficient_retune":False,
        "production_change":False,"line":False,"purchase_action":False,
      },
      "coverage":{"calendar_days":calendar,"control_evaluated_days":len(control_dates),
                  "course6_rank1_days":len(rows),"status":dict(status)},
      "canonical_control_block_bounds":bounds,
      "summary":summarize(rows,bounds),
      "records":rows,
    }
    OUTPUT_JSON.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("=== BLOCKS_3_10 ===",flush=True)
    for name,m in result["summary"]["blocks_3_10"].items():
      print(f"{name} DAYS={m['days']} HEAD_ACC={m['head_accuracy_percent']} LOGLOSS={m['head_log_loss']} BRIER={m['head_brier']}",flush=True)
    print(f"OUTPUT_JSON={OUTPUT_JSON}",flush=True)
    print("RESULT=PASS_READ_ONLY",flush=True)


if __name__=="__main__": main()
