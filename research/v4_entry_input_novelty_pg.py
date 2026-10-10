# -*- coding: utf-8 -*-
"""Result-blind input-only novelty audit for unused V4 entry fields."""
from __future__ import annotations
import json, math, os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
import psycopg
from psycopg.rows import dict_row

START=date(2025,7,1)
END=date(2026,9,22)
OUT=Path(os.getenv("V4_ENTRY_NOVELTY_OUTPUT_JSON","v4-entry-input-novelty.json"))
VERSION="2026-09-27-v4-entry-input-novelty-v1"
PAIR_FIELDS=(
 ("national_place3_rate","national_place2_rate"),
 ("local_win_rate","local_place2_rate"),
 ("local_place3_rate","local_place2_rate"),
 ("motor_place3_rate","motor_place2_rate"),
 ("boat_place3_rate","boat_place2_rate"),
 ("boat_place2_rate","motor_place2_rate"),
)
FIELDS=(
 "national_place3_rate","national_place2_rate",
 "local_win_rate","local_place2_rate","local_place3_rate",
 "motor_place2_rate","motor_place3_rate",
 "boat_place2_rate","boat_place3_rate",
 "f_count","l_count",
)
REDUNDANT_ABS_CORR=0.95
MIN_FULL6_PCT=95.0
MIN_WITHIN_RACE_VARIATION_PCT=5.0

def fnum(v:Any)->float|None:
    if v is None: return None
    try: x=float(v)
    except Exception: return None
    return x if math.isfinite(x) else None

def pearson(xs:list[float],ys:list[float])->float|None:
    if len(xs)<2: return None
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    vx=sum((x-mx)**2 for x in xs); vy=sum((y-my)**2 for y in ys)
    if vx<=0 or vy<=0: return None
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(vx*vy)

def main():
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db: raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db,row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("""select column_name from information_schema.columns
                               where table_schema='public' and table_name='v2_race_entries'""")
                cols={str(r["column_name"]) for r in cur.fetchall()}
                missing=[f for f in FIELDS if f not in cols]
                if missing:
                    raise RuntimeError("missing fixed fields: "+",".join(missing))
                cur.execute(
                    """select r.race_date,e.race_id,e.lane,
                              e.national_place3_rate,e.national_place2_rate,
                              e.local_win_rate,e.local_place2_rate,e.local_place3_rate,
                              e.motor_place2_rate,e.motor_place3_rate,
                              e.boat_place2_rate,e.boat_place3_rate,
                              e.f_count,e.l_count
                         from v2_race_entries e
                         join v2_races r on r.race_id=e.race_id
                        where r.race_date between %s and %s
                        order by r.race_date,e.race_id,e.lane""",
                    (START,END),
                )
                rows=[dict(r) for r in cur.fetchall()]

    by_race=defaultdict(list)
    for row in rows: by_race[str(row["race_id"])].append(row)
    exact6={rid:rr for rid,rr in by_race.items() if len(rr)==6 and {int(r["lane"]) for r in rr}==set(range(1,7))}

    field_stats={}
    for field in FIELDS:
        full=[]
        varying=0
        positive_rows=0
        nonnull_rows=0
        distinct=set()
        for row in rows:
            x=fnum(row.get(field))
            if x is not None:
                nonnull_rows+=1; distinct.add(x)
                if x>0: positive_rows+=1
        for rid,rr in exact6.items():
            vals=[fnum(r.get(field)) for r in rr]
            if all(v is not None for v in vals):
                xs=[float(v) for v in vals]
                full.append(rid)
                if max(xs)-min(xs)>1e-12:
                    varying+=1
        field_stats[field]={
            "nonnull_rows":nonnull_rows,
            "row_coverage_pct":round(100.0*nonnull_rows/len(rows),6) if rows else 0.0,
            "full6_races":len(full),
            "full6_pct":round(100.0*len(full)/len(exact6),6) if exact6 else 0.0,
            "within_race_varying_races":varying,
            "within_race_variation_pct_of_full6":round(100.0*varying/len(full),6) if full else 0.0,
            "positive_rows":positive_rows,
            "positive_row_pct":round(100.0*positive_rows/nonnull_rows,6) if nonnull_rows else 0.0,
            "distinct_values":len(distinct),
        }

    pair_stats={}
    for a,b in PAIR_FIELDS:
        xs=[];ys=[]
        for row in rows:
            x=fnum(row.get(a)); y=fnum(row.get(b))
            if x is None or y is None: continue
            xs.append(x);ys.append(y)
        corr=pearson(xs,ys)
        pair_stats[f"{a}__{b}"]={
            "n":len(xs),
            "pair_coverage_pct":round(100.0*len(xs)/len(rows),6) if rows else 0.0,
            "pearson":round(corr,8) if corr is not None else None,
            "redundant_abs_corr_ge_095":bool(corr is not None and abs(corr)>=REDUNDANT_ABS_CORR),
        }

    fl_ready={}
    for field in ("f_count","l_count"):
        s=field_stats[field]
        fl_ready[field]=(
            s["full6_pct"]>=MIN_FULL6_PCT and
            s["within_race_variation_pct_of_full6"]>=MIN_WITHIN_RACE_VARIATION_PCT
        )

    report={
      "version":VERSION,
      "period":[START.isoformat(),END.isoformat()],
      "safety":{
        "transaction_read_only":True,"outcome_read":False,"odds_read":False,
        "payout_read":False,"prediction_performance_read":False,"db_write":False,
        "purchase_action":False,
      },
      "population":{"entry_rows":len(rows),"exact6_races":len(exact6)},
      "thresholds":{
        "redundant_abs_corr":REDUNDANT_ABS_CORR,
        "min_full6_pct":MIN_FULL6_PCT,
        "min_within_race_variation_pct":MIN_WITHIN_RACE_VARIATION_PCT,
      },
      "fields":field_stats,
      "pairs":pair_stats,
      "f_l_shape_ready":fl_ready,
      "classification":"INPUT_ONLY_NOVELTY_AUDIT_COMPLETE",
      "historical_predictive_test_authorized":False,
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"ENTRY_NOVELTY_ROWS={len(rows)}",flush=True)
    print(f"ENTRY_NOVELTY_EXACT6_RACES={len(exact6)}",flush=True)
    for f in FIELDS:
        s=field_stats[f]
        print(f"ENTRY_NOVELTY_FIELD={f} full6={s['full6_pct']} varying={s['within_race_variation_pct_of_full6']} positive={s['positive_row_pct']}",flush=True)
    for k,s in pair_stats.items():
        print(f"ENTRY_NOVELTY_PAIR={k} n={s['n']} corr={s['pearson']} redundant={int(s['redundant_abs_corr_ge_095'])}",flush=True)
    print(f"ENTRY_NOVELTY_F_READY={int(fl_ready['f_count'])}",flush=True)
    print(f"ENTRY_NOVELTY_L_READY={int(fl_ready['l_count'])}",flush=True)
    print("ENTRY_NOVELTY_OUTCOME_READ=0",flush=True)
    print("RESULT=PASS_READ_ONLY",flush=True)

if __name__=="__main__":
    main()
