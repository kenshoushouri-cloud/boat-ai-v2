# -*- coding: utf-8 -*-
"""Read-only breakdown of actual PRE candidate shadow rows.

This uses only already-observed PRE Shadow selections. It is descriptive and
hypothesis-generating; no subgroup is authorized for Production from this file.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row

DAYS = int(os.getenv("VALUE_PRE_BREAKDOWN_DAYS", "30"))
END_DATE = date.fromisoformat(os.getenv("VALUE_PRE_BREAKDOWN_END", date.today().isoformat()))
START_DATE = END_DATE - timedelta(days=DAYS - 1)
OUTPUT = Path(os.getenv("VALUE_PRE_BREAKDOWN_OUTPUT", "value-candidate-pre-shadow-breakdown.json"))
RULES = ("S02", "S03")
UNIT_YEN = 100


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


def bucket_odds(v: Any) -> str:
    x = sf(v, 0.0)
    if x < 20: return "<20"
    if x < 25: return "20-25"
    if x < 30: return "25-30"
    if x < 35: return "30-35"
    if x < 40: return "35-40"
    if x < 45: return "40-45"
    if x < 50: return "45-50"
    return "50+"


def bucket_rank(v: Any) -> str:
    x = si(v, 999)
    if x <= 5: return "01-05"
    if x <= 10: return "06-10"
    if x <= 15: return "11-15"
    if x <= 20: return "16-20"
    if x <= 25: return "21-25"
    if x <= 30: return "26-30"
    return "31+"


def stat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eval_rows = [r for r in rows if r.get("hit") is not None and r.get("return_yen") is not None]
    bets = len(eval_rows)
    hits = sum(1 for r in eval_rows if bool(r.get("hit")))
    ret = sum(si(r.get("return_yen"), 0) for r in eval_rows)
    inv = sum(si(r.get("investment_yen"), UNIT_YEN) or UNIT_YEN for r in eval_rows)
    hit_returns = sorted((si(r.get("return_yen"), 0) for r in eval_rows if bool(r.get("hit"))), reverse=True)
    return {
        "rows": len(rows),
        "evaluated": bets,
        "pending_or_invalid": len(rows) - bets,
        "hits": hits,
        "hit_rate_pct": round(hits / bets * 100.0, 4) if bets else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / ret * 100.0, 4) if hit_returns and ret else 0.0,
    }


def group(rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row))].append(row)
    return {k: stat(v) for k, v in sorted(groups.items())}


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"VALUE_PRE_BREAKDOWN_PERIOD={START_DATE}..{END_DATE} days:{DAYS}", flush=True)
    print("VALUE_PRE_BREAKDOWN_RULES=S02,S03", flush=True)
    print("VALUE_PRE_BREAKDOWN_MODE=actual_PRE_shadow_read_only_descriptive", flush=True)
    print("VALUE_PRE_BREAKDOWN_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute(
                """select race_id,race_date,venue_id,race_no,window_name,rule_id,ticket,
                          odds,prob,prob_rank,market_rank,raw_ev,venue_style,event_category,
                          event_day_no,snapshot_at,investment_yen,result_ticket,payout_yen,
                          hit,return_yen,evaluated_at,evaluation_status,evaluation_note
                     from v2_candidate_filter_shadow
                    where race_date between %s and %s
                      and rule_id = any(%s)
                    order by race_date,race_id,rule_id""",
                (START_DATE, END_DATE, list(RULES)),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.rollback()

    out: dict[str, Any] = {
        "contract": "candidate_pre_shadow_breakdown_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat(), "days": DAYS},
        "rules": {},
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }

    for rule_id in RULES:
        rr = [r for r in rows if str(r.get("rule_id")) == rule_id]
        payload = {
            "overall": stat(rr),
            "by_race_no": group(rr, lambda r: f"R{si(r.get('race_no')):02d}"),
            "by_odds": group(rr, lambda r: bucket_odds(r.get("odds"))),
            "by_prob_rank": group(rr, lambda r: bucket_rank(r.get("prob_rank"))),
            "by_market_rank": group(rr, lambda r: f"MR{si(r.get('market_rank')):02d}"),
            "by_window": group(rr, lambda r: str(r.get("window_name") or "unknown")),
            "by_month": group(rr, lambda r: str(r.get("race_date"))[:7]),
            "by_venue": group(rr, lambda r: str(r.get("venue_id") or "unknown").zfill(2)),
            "by_event_day": group(rr, lambda r: f"D{si(r.get('event_day_no'))}"),
        }
        out["rules"][rule_id] = payload
        o = payload["overall"]
        print(
            f"VALUE_PRE_BREAKDOWN_RULE={rule_id} rows:{o['rows']} eval:{o['evaluated']} "
            f"hits:{o['hits']} roi:{o['roi_pct']} profit:{o['profit_yen']} single_hit_share:{o['single_hit_share_pct']}",
            flush=True,
        )
        for axis in ("by_race_no", "by_odds", "by_prob_rank", "by_market_rank", "by_window", "by_month"):
            for key, s in payload[axis].items():
                print(
                    f"VALUE_PRE_BREAKDOWN={rule_id}/{axis}/{key} eval:{s['evaluated']} hits:{s['hits']} roi:{s['roi_pct']} profit:{s['profit_yen']} single_hit_share:{s['single_hit_share_pct']}",
                    flush=True,
                )

    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print("VALUE_PRE_BREAKDOWN_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_PRE_BREAKDOWN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
