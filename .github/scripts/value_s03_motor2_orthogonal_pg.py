# -*- coding: utf-8 -*-
"""Read-only S03 actual-PRE diagnostic using independently frozen Motor2 signal.

The Motor2 formula and beta are NOT fit on S03 outcomes:
  score(ticket) = 1.0*z(motor2 first) + 0.6*z(second) + 0.3*z(third)
  factor = exp(0.06 * score)

Beta=0.06 comes from the independent Motor2 market-residual robustness work.
This script is descriptive / prospective-hypothesis research only. It cannot
promote or change S03, Production, LINE, BUY, or persistence.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

DAYS = int(os.getenv("VALUE_S03_M2_DAYS", "30"))
END_DATE = date.fromisoformat(os.getenv("VALUE_S03_M2_END", "2026-09-12"))
START_DATE = END_DATE - timedelta(days=DAYS - 1)
OUTPUT = Path(os.getenv("VALUE_S03_M2_OUTPUT", "value-s03-motor2-orthogonal.json"))
BETA = 0.06
POS_W = (1.0, 0.6, 0.3)
UNIT_YEN = 100

# Natural, predeclared score/factor views only. No S03-outcome fitting.
VIEWS = (
    ("ALL", lambda score, factor: True),
    ("M2_POSITIVE", lambda score, factor: score > 0.0),
    ("M2_FACTOR_GE_1_03", lambda score, factor: factor >= 1.03),
    ("M2_FACTOR_GE_1_06", lambda score, factor: factor >= 1.06),
)


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any, default: float | None = None) -> float | None:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def ticket_lanes(value: Any) -> tuple[int, int, int] | None:
    xs = [int(x) for x in re.findall(r"[1-6]", str(value or ""))]
    if len(xs) < 3 or len(set(xs[:3])) != 3:
        return None
    return xs[0], xs[1], xs[2]


def score_for(entries: list[dict[str, Any]], ticket: Any) -> float | None:
    lanes = ticket_lanes(ticket)
    if lanes is None:
        return None
    by = {si(e.get("lane")): e for e in entries}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not (0.0 <= x <= 100.0):
            return None
        vals.append(float(x))
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    z = {lane: (vals[lane - 1] - mu) / sd for lane in range(1, 7)}
    a, b, c = lanes
    return POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if r.get("hit") is not None and r.get("return_yen") is not None]
    bets = len(evaluated)
    hits = sum(1 for r in evaluated if bool(r.get("hit")))
    ret = sum(si(r.get("return_yen"), 0) for r in evaluated)
    inv = sum(si(r.get("investment_yen"), UNIT_YEN) or UNIT_YEN for r in evaluated)
    hit_returns = sorted((si(r.get("return_yen"), 0) for r in evaluated if bool(r.get("hit"))), reverse=True)
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in evaluated:
        by_month[str(r.get("race_date"))[:7]].append(r)
    monthly = {}
    for month, rr in sorted(by_month.items()):
        mi = sum(si(r.get("investment_yen"), UNIT_YEN) or UNIT_YEN for r in rr)
        mr = sum(si(r.get("return_yen"), 0) for r in rr)
        mh = sum(1 for r in rr if bool(r.get("hit")))
        monthly[month] = {
            "bets": len(rr), "hits": mh, "return_yen": mr,
            "profit_yen": mr - mi,
            "roi_pct": round(mr / mi * 100.0, 4) if mi else None,
        }
    return {
        "rows": len(rows),
        "evaluated": bets,
        "hits": hits,
        "hit_rate_pct": round(hits / bets * 100.0, 4) if bets else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / ret * 100.0, 4) if hit_returns and ret else 0.0,
        "by_month": monthly,
    }


def score_bucket(score: float) -> str:
    if score < -1.0:
        return "LT_-1"
    if score < 0.0:
        return "-1_TO_0"
    if score < 1.0:
        return "0_TO_1"
    return "GE_1"


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"VALUE_S03_M2_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_S03_M2_MODE=actual_PRE_shadow_read_only_independent_fixed_signal", flush=True)
    print(f"VALUE_S03_M2_BETA={BETA:.2f}", flush=True)
    print("VALUE_S03_M2_FORMULA=1.0*z(first)+0.6*z(second)+0.3*z(third)", flush=True)
    print("VALUE_S03_M2_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute(
                """select race_id,race_date,rule_id,ticket,odds,prob,prob_rank,market_rank,raw_ev,
                          venue_id,race_no,window_name,snapshot_at,investment_yen,hit,return_yen,evaluated_at
                     from v2_candidate_filter_shadow
                    where race_date between %s and %s
                      and rule_id='S03'
                    order by race_date,race_id""",
                (START_DATE, END_DATE),
            )
            shadow = [dict(r) for r in cur.fetchall()]
            race_ids = sorted({str(r["race_id"]) for r in shadow})
            entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if race_ids:
                cur.execute(
                    """select race_id,lane,motor_place2_rate
                         from v2_race_entries
                        where race_id = any(%s)
                        order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries[str(row["race_id"])].append(dict(row))
        conn.rollback()

    ready = []
    missing = 0
    for row in shadow:
        score = score_for(entries.get(str(row["race_id"]), []), row.get("ticket"))
        if score is None:
            missing += 1
            continue
        x = dict(row)
        x["motor2_score"] = score
        x["motor2_factor"] = math.exp(BETA * score)
        ready.append(x)

    base = summarize(ready)
    views = {}
    base_eval = int(base["evaluated"] or 0)
    for name, predicate in VIEWS:
        rr = [r for r in ready if predicate(float(r["motor2_score"]), float(r["motor2_factor"]))]
        s = summarize(rr)
        s["retained_eval_pct"] = round(s["evaluated"] / base_eval * 100.0, 4) if base_eval else None
        views[name] = s

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ready:
        buckets[score_bucket(float(row["motor2_score"]))].append(row)
    bucket_stats = {k: summarize(v) for k, v in sorted(buckets.items())}

    out = {
        "contract": "s03_motor2_orthogonal_actual_pre_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "independent_signal": {
            "feature": "motor_place2_rate",
            "position_weights": list(POS_W),
            "beta": BETA,
            "source": "independent Motor2 market-residual robustness; not fit on S03 outcomes",
        },
        "audit": {"shadow_rows": len(shadow), "motor_ready_rows": len(ready), "missing_motor_rows": missing},
        "views": views,
        "score_buckets": bucket_stats,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("VALUE_S03_M2_AUDIT=" + json.dumps(out["audit"], sort_keys=True), flush=True)
    for name in (x[0] for x in VIEWS):
        s = views[name]
        print(
            f"VALUE_S03_M2_VIEW={name} eval:{s['evaluated']} retained:{s['retained_eval_pct']}% "
            f"hits:{s['hits']} roi:{s['roi_pct']} profit:{s['profit_yen']} single_hit_share:{s['single_hit_share_pct']}",
            flush=True,
        )
    for name, s in bucket_stats.items():
        print(
            f"VALUE_S03_M2_BUCKET={name} eval:{s['evaluated']} hits:{s['hits']} roi:{s['roi_pct']} profit:{s['profit_yen']}",
            flush=True,
        )
    print("VALUE_S03_M2_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S03_M2_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
