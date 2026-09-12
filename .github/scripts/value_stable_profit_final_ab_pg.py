# -*- coding: utf-8 -*-
"""Read-only timing-safe A_STABLE/B_PROFIT audit on Production final_ab odds."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import v24_pre_candidate_notifier_pg as v24

START_DATE = date.fromisoformat(os.getenv("VALUE_FINAL_AB_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_FINAL_AB_END", "2026-09-12"))
MAX_SPREAD_SECONDS = 60.0
UNIT_YEN = 100
OUTPUT = Path(os.getenv("VALUE_FINAL_AB_OUTPUT", "value-stable-profit-final-ab.json"))
RULES = (
    {"id": "A_STABLE", "prob_rank": (11, 25), "market_rank": (2, 5), "odds": (3.0, 6.0), "race_nos": tuple(range(7, 13))},
    {"id": "B_PROFIT", "prob_rank": (11, 20), "market_rank": (2, 5), "odds": (3.0, 6.0), "race_nos": tuple(range(7, 11))},
)
CONFIG = {
    "contract": "phase4_ab_final_ab_timing_safe_v1",
    "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
    "snapshot_label": "final_ab",
    "complete_rows": 120,
    "distinct_tickets": 120,
    "all_odds_gt": 1.0,
    "max_spread_seconds": MAX_SPREAD_SECONDS,
    "deadline_gate": "last_snapshot_at<=deadline_at",
    "rules": [{**{k: v for k, v in r.items() if k != "race_nos"}, "race_nos": list(r["race_nos"])} for r in RULES],
    "unit_yen": UNIT_YEN,
}
CONFIG_SHA256 = hashlib.sha256(json.dumps(CONFIG, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    p = (len(ys) - 1) * q
    lo, hi = math.floor(p), math.ceil(p)
    if lo == hi:
        return round(ys[lo], 4)
    w = p - lo
    return round(ys[lo] * (1 - w) + ys[hi] * w, 4)


def select_candidate(ranked: list[dict[str, Any]], rule: dict[str, Any], race_no: int) -> dict[str, Any] | None:
    if race_no not in rule["race_nos"]:
        return None
    rows = [
        r for r in ranked
        if rule["prob_rank"][0] <= si(r.get("prob_rank"), 999) <= rule["prob_rank"][1]
        and rule["market_rank"][0] <= si(r.get("market_rank"), 999) <= rule["market_rank"][1]
        and rule["odds"][0] <= sf(r.get("odds")) < rule["odds"][1]
    ]
    return max(rows, key=lambda r: (sf(r.get("raw_ev")), sf(r.get("prob")))) if rows else None


def summarize(rows: list[dict[str, Any]], days: int) -> dict[str, Any]:
    rr = sorted(rows, key=lambda r: (r["race_date"], r["race_id"]))
    ev = [r for r in rr if r["evaluated"]]
    hits = sum(bool(r["hit"]) for r in ev)
    ret = sum(si(r["return_yen"]) for r in ev)
    inv = len(ev) * UNIT_YEN
    hit_returns = sorted((si(r["return_yen"]) for r in ev if r["hit"]), reverse=True)
    streak = cur = 0
    equity = peak = max_dd = 0
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in ev:
        if r["hit"]:
            cur = 0
        else:
            cur += 1
            streak = max(streak, cur)
        equity += si(r["return_yen"]) - UNIT_YEN
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        by_month[r["race_date"][:7]].append(r)
    monthly = {}
    for m, xs in sorted(by_month.items()):
        mi = len(xs) * UNIT_YEN
        mr = sum(si(x["return_yen"]) for x in xs)
        monthly[m] = {"evaluated": len(xs), "hits": sum(bool(x["hit"]) for x in xs), "profit_yen": mr-mi, "roi_pct": round(mr/mi*100, 4) if mi else None}
    return {
        "candidate_rows": len(rr),
        "candidates_per_30_calendar_days": round(len(rr) / days * 30, 4) if days else None,
        "evaluated": len(ev), "pending": len(rr)-len(ev), "hits": hits,
        "hit_rate_pct": round(hits/len(ev)*100, 4) if ev else None,
        "investment_yen": inv, "return_yen": ret, "profit_yen": ret-inv,
        "roi_pct": round(ret/inv*100, 4) if inv else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0]/ret*100, 4) if hit_returns and ret else 0.0,
        "max_losing_streak": streak, "max_drawdown_yen": max_dd, "by_month": monthly,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print(f"VALUE_FINAL_AB_CONFIG_SHA256={CONFIG_SHA256}", flush=True)
    print(f"VALUE_FINAL_AB_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_FINAL_AB_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("""
                with c as (
                  select race_id,race_date,coalesce(nullif(venue_id,''),nullif(venue_code,'')) as venue_id,race_no,deadline_at
                  from v2_races where race_date between %s and %s and deadline_at is not null
                ), g as (
                  select c.race_id,c.race_date,c.venue_id,c.race_no,c.deadline_at,
                         count(*)::bigint row_count,count(distinct o.ticket)::bigint ticket_count,
                         count(*) filter(where o.odds is not null and o.odds>1.0)::bigint positive_count,
                         min(o.snapshot_at) first_snapshot_at,max(o.snapshot_at) last_snapshot_at
                  from c join v2_realtime_odds_snapshots o on o.race_id=c.race_id
                  where o.snapshot_label='final_ab'
                  group by c.race_id,c.race_date,c.venue_id,c.race_no,c.deadline_at
                ), valid as (
                  select *,extract(epoch from(last_snapshot_at-first_snapshot_at)) spread_seconds
                  from g where row_count=120 and ticket_count=120 and positive_count=120
                    and last_snapshot_at<=deadline_at
                    and extract(epoch from(last_snapshot_at-first_snapshot_at))<=%s
                )
                select v.*,o.ticket,o.odds,
                       (select count(*)::bigint from c) total_races,
                       (select count(*)::bigint from g) final_ab_races
                from valid v join v2_realtime_odds_snapshots o on o.race_id=v.race_id and o.snapshot_label='final_ab'
                order by v.race_date,v.race_id,o.ticket
            """, (START_DATE, END_DATE, MAX_SPREAD_SECONDS))
            odds_rows = [dict(r) for r in cur.fetchall()]
            meta: dict[str, dict[str, Any]] = {}
            odds_by: dict[str, dict[str, float]] = defaultdict(dict)
            total_races = final_ab_races = 0
            for row in odds_rows:
                rid = str(row["race_id"])
                total_races = max(total_races, si(row.get("total_races")))
                final_ab_races = max(final_ab_races, si(row.get("final_ab_races")))
                meta.setdefault(rid, {k: row.get(k) for k in ("race_id","race_date","venue_id","race_no","deadline_at","first_snapshot_at","last_snapshot_at","spread_seconds")})
                t = v24._norm_ticket(row.get("ticket"))
                if t:
                    odds_by[rid][t] = sf(row.get("odds"))
            race_ids = sorted(meta)
            entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
            results: dict[str, tuple[str, int]] = {}
            if race_ids:
                cur.execute("""select race_id,lane,racer_number,racer_class,racer_name,national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,motor_no,boat_no,avg_st from v2_race_entries where race_id=any(%s) order by race_id,lane""", (race_ids,))
                for row in cur.fetchall(): entries[str(row["race_id"])].append(dict(row))
                cur.execute("select race_id,trifecta_ticket,trifecta_payout_yen from v2_results where race_id=any(%s)", (race_ids,))
                for row in cur.fetchall():
                    ticket = v24._norm_ticket(row.get("trifecta_ticket")); payout = si(row.get("trifecta_payout_yen"))
                    if ticket and payout>0: results[str(row["race_id"])] = (ticket,payout)
        conn.rollback()

    gaps=[]; entry_ready=result_ready=0
    candidates={r["id"]: [] for r in RULES}
    for rid,m in sorted(meta.items(), key=lambda x:(str(x[1]["race_date"]),x[0])):
        deadline,last=m["deadline_at"],m["last_snapshot_at"]
        gaps.append((deadline-last).total_seconds()/60)
        if len(odds_by[rid])!=120 or len(v24._entry_by_lane(entries.get(rid,[])))!=6: continue
        entry_ready+=1
        ranked=v24._rank_candidates(entries[rid],str(m.get("venue_id") or "").zfill(2),odds_by[rid])
        result=results.get(rid)
        if result: result_ready+=1
        for rule in RULES:
            pick=select_candidate(ranked,rule,si(m.get("race_no")))
            if not pick: continue
            rt,payout=result if result else ("",0); ticket=v24._norm_ticket(pick.get("ticket")); evaluated=bool(result); hit=bool(evaluated and ticket==rt)
            candidates[rule["id"]].append({"race_id":rid,"race_date":str(m["race_date"])[:10],"ticket":ticket,"evaluated":evaluated,"hit":hit if evaluated else None,"return_yen":payout if hit else (0 if evaluated else None)})

    days=(END_DATE-START_DATE).days+1
    summaries={k:summarize(v,days) for k,v in candidates.items()}
    a={(r["race_id"],r["ticket"]) for r in candidates["A_STABLE"]}; b={(r["race_id"],r["ticket"]) for r in candidates["B_PROFIT"]}
    audit={"total_races_with_deadline":total_races,"races_with_final_ab_rows":final_ab_races,"complete_predeadline_final_ab_races":len(meta),"entry_ready":entry_ready,"result_ready":result_ready}
    timing={"n":len(gaps),"min":round(min(gaps),4) if gaps else None,"p05":percentile(gaps,.05),"median":percentile(gaps,.5),"p95":percentile(gaps,.95),"max":round(max(gaps),4) if gaps else None}
    out={"config":CONFIG,"config_sha256":CONFIG_SHA256,"audit":audit,"minutes_to_deadline":timing,"variants":summaries,"overlap":{"same_race_ticket":len(a&b),"a_only":len(a-b),"b_only":len(b-a)},"mutation_performed":False,"production_behavior_changed":False,"promotion_allowed":False}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n",encoding="utf-8")
    print("VALUE_FINAL_AB_AUDIT="+json.dumps(audit,sort_keys=True),flush=True)
    print("VALUE_FINAL_AB_TIMING="+json.dumps(timing,sort_keys=True),flush=True)
    for rid,s in summaries.items():
        print(f"VALUE_FINAL_AB_VARIANT={rid} candidates:{s['candidate_rows']} per30d:{s['candidates_per_30_calendar_days']} evaluated:{s['evaluated']} hits:{s['hits']} roi:{s['roi_pct']} profit:{s['profit_yen']} single_hit_share:{s['single_hit_share_pct']} lose_streak:{s['max_losing_streak']} max_dd:{s['max_drawdown_yen']}",flush=True)
        print("VALUE_FINAL_AB_MONTHLY="+rid+":"+json.dumps(s["by_month"],sort_keys=True),flush=True)
    print("VALUE_FINAL_AB_OVERLAP="+json.dumps(out["overlap"],sort_keys=True),flush=True)
    print("VALUE_FINAL_AB_PROMOTION_ALLOWED=0",flush=True)
    print("VALUE_FINAL_AB_RESULT=PASS_READ_ONLY",flush=True)

if __name__ == "__main__": main()
