# -*- coding: utf-8 -*-
"""Read-only OOS audit for a Bao-style model-vs-market value layer.

Scope:
- v2_realtime_decisions joined to v2_results
- model probability is kept separate from market odds
- evaluate probability calibration, Brier score, and ROI by edge bucket
- use chronological train/test splits only

No DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime
from statistics import mean

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def sf(v, d=None):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_cols(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name=%s order by ordinal_position",
            (table,),
        )
        return [str(r["column_name"]) for r in cur.fetchall()]


def choose(cols: list[str], names: list[str]):
    for n in names:
        if n in cols:
            return n
    return None


def bin_prob(p: float) -> str:
    if p < .005: return "LT0.5%"
    if p < .01: return "0.5-1%"
    if p < .02: return "1-2%"
    if p < .03: return "2-3%"
    if p < .05: return "3-5%"
    if p < .08: return "5-8%"
    if p < .12: return "8-12%"
    return "GE12%"


def bin_edge(e: float) -> str:
    if e < .6: return "LT0.6"
    if e < .8: return "0.6-0.8"
    if e < 1.0: return "0.8-1.0"
    if e < 1.1: return "1.0-1.1"
    if e < 1.25: return "1.1-1.25"
    if e < 1.5: return "1.25-1.5"
    if e < 2.0: return "1.5-2.0"
    return "GE2.0"


def metrics(xs, prob_key="prob"):
    n = len(xs)
    if not n:
        return {"n":0,"hits":0,"hit":0.0,"roi":0.0,"brier":0.0,"mp":0.0,"me":0.0}
    hits = sum(int(x["hit"]) for x in xs)
    ret = sum(int(x["payout"]) for x in xs if x["hit"])
    brier = mean((float(x[prob_key]) - int(x["hit"])) ** 2 for x in xs)
    return {
        "n": n,
        "hits": hits,
        "hit": hits/n*100,
        "roi": ret/(n*100)*100,
        "brier": brier,
        "mp": mean(float(x[prob_key]) for x in xs),
        "me": mean(float(x["edge"]) for x in xs),
    }


def fmt(m):
    return (f"n:{m['n']} hits:{m['hits']} hit:{m['hit']:.2f}% ROI:{m['roi']:.1f}% "
            f"brier:{m['brier']:.6f} mean_prob:{m['mp']:.5f} mean_edge:{m['me']:.3f}")


def split_dates(days: list[str]):
    # Expanding-window splits. At least 6 distinct dates are required for a split.
    n = len(days)
    out = []
    for frac in (.50, .67, .80):
        k = max(1, min(n-1, int(n*frac)))
        train = days[:k]
        test = days[k:]
        if len(train) >= 3 and len(test) >= 2:
            out.append((frac, train[-1], test[0], test[-1]))
    # Remove duplicate boundaries when date count is small.
    uniq=[]; seen=set()
    for x in out:
        key=(x[1],x[2],x[3])
        if key not in seen:
            seen.add(key); uniq.append(x)
    return uniq


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    print("BAO_RT_MODE=read_only", flush=True)
    print("BAO_RT_PRINCIPLE=probability_separate_from_market_odds", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        dcols = table_cols(conn, "v2_realtime_decisions")
        rcols = table_cols(conn, "v2_results")
        pcol = choose(dcols, ["probability","prob"])
        ocol = choose(dcols, ["odds"])
        tcol = choose(dcols, ["ticket"])
        ridcol = choose(dcols, ["race_id"])
        tscol = choose(dcols, ["decision_at","created_at","updated_at","snapshot_at","saved_at","evaluated_at"])
        payoutcol = choose(rcols, ["trifecta_payout_yen","trifecta_payout"])
        resultticket = choose(rcols, ["trifecta_ticket"])
        print(f"BAO_RT_SCHEMA=prob:{pcol} odds:{ocol} ticket:{tcol} race:{ridcol} ts:{tscol} payout:{payoutcol}", flush=True)
        if not all([pcol,ocol,tcol,ridcol,payoutcol,resultticket]):
            raise SystemExit("required realtime-decision/result columns missing")

        order = f" order by d.{qident(ridcol)},d.{qident(tcol)},d.{qident(tscol)} desc nulls last" if tscol else f" order by d.{qident(ridcol)},d.{qident(tcol)}"
        # race_id starts with YYYYMMDD in this project. Keep only valid probability/odds rows.
        sql = f"""
          select distinct on (d.{qident(ridcol)}, d.{qident(tcol)})
                 d.{qident(ridcol)}::text race_id,
                 d.{qident(tcol)}::text ticket,
                 d.{qident(pcol)}::float8 prob,
                 d.{qident(ocol)}::float8 odds,
                 r.{qident(resultticket)}::text result_ticket,
                 coalesce(r.{qident(payoutcol)},0)::float8 payout
          from v2_realtime_decisions d
          join v2_results r on r.race_id=d.{qident(ridcol)}
          where d.{qident(pcol)} is not null
            and d.{qident(ocol)} is not null
            and d.{qident(pcol)}::float8 > 0 and d.{qident(pcol)}::float8 < 1
            and d.{qident(ocol)}::float8 > 1
            and d.{qident(ridcol)}::text ~ '^[0-9]{{8}}'
          {order}
        """
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='120s'")
            cur.execute(sql)
            raw=[dict(r) for r in cur.fetchall()]

    rows=[]
    for r in raw:
        rid=str(r["race_id"]); ds=f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}"
        try: date.fromisoformat(ds)
        except Exception: continue
        p=sf(r["prob"]); o=sf(r["odds"]); pay=sf(r["payout"],0) or 0
        if p is None or o is None: continue
        hit=str(r["ticket"] or "").strip()==str(r["result_ticket"] or "").strip()
        rows.append({"date":ds,"race_id":rid,"ticket":r["ticket"],"prob":p,"odds":o,
                     "edge":p*o,"hit":int(hit),"payout":int(round(pay))})

    days=sorted({x["date"] for x in rows})
    races=len({x["race_id"] for x in rows})
    print(f"BAO_RT_ROWS={len(rows)} races:{races} days:{len(days)}", flush=True)
    if days: print(f"BAO_RT_PERIOD={days[0]}..{days[-1]}", flush=True)
    if len(rows)<100:
        print("BAO_RT_RESULT=INSUFFICIENT_ROWS", flush=True); raise SystemExit(2)

    print("BAO_RT_ALL="+fmt(metrics(rows)), flush=True)
    byp=defaultdict(list); bye=defaultdict(list)
    for x in rows:
        byp[bin_prob(x["prob"])].append(x); bye[bin_edge(x["edge"])].append(x)
    for k in ["LT0.5%","0.5-1%","1-2%","2-3%","3-5%","5-8%","8-12%","GE12%"]:
        if byp[k]: print(f"BAO_RT_PROB_BIN={k} "+fmt(metrics(byp[k])), flush=True)
    for k in ["LT0.6","0.6-0.8","0.8-1.0","1.0-1.1","1.1-1.25","1.25-1.5","1.5-2.0","GE2.0"]:
        if bye[k]: print(f"BAO_RT_EDGE_BIN={k} "+fmt(metrics(bye[k])), flush=True)

    splits=split_dates(days)
    print(f"BAO_RT_SPLITS={len(splits)}", flush=True)
    for i,(_,train_end,test_start,test_end) in enumerate(splits,1):
        train=[x for x in rows if x["date"]<=train_end]
        test=[x for x in rows if test_start<=x["date"]<=test_end]
        # One-parameter calibration learned only from train. This is diagnostic,
        # not a production model. Bound it to avoid unstable tiny-sample scaling.
        sum_p=sum(x["prob"] for x in train); hits=sum(x["hit"] for x in train)
        scale=(hits/sum_p) if sum_p>0 else 1.0
        scale=max(.25,min(4.0,scale))
        for x in test:
            x["cal_prob"]=max(1e-6,min(.999999,x["prob"]*scale))
            x["cal_edge"]=x["cal_prob"]*x["odds"]
        rawm=metrics(test,"prob"); calm=metrics(test,"cal_prob")
        print(f"BAO_RT_SPLIT={i} train_end:{train_end} test:{test_start}..{test_end} train_n:{len(train)} test_n:{len(test)} scale:{scale:.4f}",flush=True)
        print(f"BAO_RT_SPLIT_RAW={i} "+fmt(rawm),flush=True)
        print(f"BAO_RT_SPLIT_CAL={i} "+fmt(calm),flush=True)
        for th in (0.8,1.0,1.1,1.25,1.5):
            xs=[x for x in test if x["cal_edge"]>=th]
            if xs:
                m=metrics(xs,"cal_prob")
                print(f"BAO_RT_SPLIT_EDGE={i} threshold:{th:.2f} "+fmt(m),flush=True)

    # Diagnostic readiness only. Do not promote a value rule from this audit.
    enough = len(days)>=6 and len(rows)>=500 and len(splits)>=2
    print(f"BAO_RT_OOS_READINESS={'READY' if enough else 'LIMITED'}", flush=True)
    print("BAO_RT_NEXT=full_market_probability_calibration_before_any_production_value_rule", flush=True)
    print("BAO_RT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
