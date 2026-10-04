# -*- coding: utf-8 -*-
"""Read-only prospective audit for frozen S02_FORWARD_V1.

Freeze date: 2026-09-12 JST. Prospective start: 2026-09-13 JST.
The rule already exists in Candidate Filter Shadow; this script only observes
post-freeze rows and does not create/update any Production or Shadow data.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

CONTRACT = "S02_FORWARD_V1"
START_DATE = date(2026, 9, 13)
END_DATE = date.fromisoformat(os.environ["VALUE_S02_FORWARD_END"]) if os.getenv("VALUE_S02_FORWARD_END") else datetime.now(ZoneInfo("Asia/Tokyo")).date()
UNIT_YEN = 100
CHECKPOINTS = (30, 50, 100)
OUTPUT = Path(os.getenv("VALUE_S02_FORWARD_OUTPUT", "value-s02-forward-frozen.json"))

FROZEN_CONFIG = {
    "contract": CONTRACT,
    "prospective_start": START_DATE.isoformat(),
    "source_table": "v2_candidate_filter_shadow",
    "source_rule_id": "S02",
    "prob_rank": [16, 30],
    "market_rank": [6, 10],
    "odds": [20.0, 30.0],
    "race_nos": [7, 8, 9],
    "venue_style": "in_strong",
    "event_category": "ALL",
    "select_mode": "prob",
    "unit_yen": UNIT_YEN,
    "checkpoints": list(CHECKPOINTS),
}
FROZEN_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(FROZEN_CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def max_losing_streak(rows: list[dict[str, Any]]) -> int:
    current = best = 0
    for row in rows:
        if bool(row.get("hit")):
            current = 0
        else:
            current += 1
            best = max(best, current)
    return best


def max_drawdown_yen(rows: list[dict[str, Any]]) -> int:
    equity = peak = worst = 0
    for row in rows:
        equity += si(row.get("return_yen"), 0) - UNIT_YEN
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: (str(r.get("race_date")), str(r.get("race_id"))))
    evaluated = [r for r in ordered if r.get("evaluated_at") is not None and r.get("return_yen") is not None]
    pending = len(ordered) - len(evaluated)
    hits = sum(1 for r in evaluated if bool(r.get("hit")))
    returned = sum(si(r.get("return_yen"), 0) for r in evaluated)
    invested = len(evaluated) * UNIT_YEN
    hit_returns = sorted((si(r.get("return_yen"), 0) for r in evaluated if bool(r.get("hit"))), reverse=True)

    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated:
        by_month[str(row.get("race_date"))[:7]].append(row)
    monthly: dict[str, dict[str, Any]] = {}
    for month, rr in sorted(by_month.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(si(r.get("return_yen"), 0) for r in rr)
        monthly[month] = {
            "evaluated": len(rr),
            "hits": sum(1 for r in rr if bool(r.get("hit"))),
            "investment_yen": inv,
            "return_yen": ret,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        }

    return {
        "eligible_rows": len(ordered),
        "evaluated": len(evaluated),
        "pending": pending,
        "hits": hits,
        "hit_rate_pct": round(hits / len(evaluated) * 100.0, 4) if evaluated else None,
        "investment_yen": invested,
        "return_yen": returned,
        "profit_yen": returned - invested,
        "roi_pct": round(returned / invested * 100.0, 4) if invested else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / returned * 100.0, 4) if hit_returns and returned else 0.0,
        "max_losing_streak": max_losing_streak(evaluated),
        "max_drawdown_yen": max_drawdown_yen(evaluated),
        "by_month": monthly,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"VALUE_S02_FORWARD_CONTRACT={CONTRACT}", flush=True)
    print(f"VALUE_S02_FORWARD_CONFIG_SHA256={FROZEN_CONFIG_SHA256}", flush=True)
    print(f"VALUE_S02_FORWARD_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_S02_FORWARD_POLICY=frozen_existing_shadow_rule_no_retune", flush=True)
    print("VALUE_S02_FORWARD_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    rows: list[dict[str, Any]] = []
    if END_DATE >= START_DATE:
        with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("set local statement_timeout='60s'")
                cur.execute(
                    """
                    select race_id,race_date,venue_id,race_no,window_name,rule_id,
                           ticket,odds,prob,prob_rank,market_rank,raw_ev,
                           venue_style,event_category,snapshot_at,
                           hit,return_yen,evaluated_at
                      from v2_candidate_filter_shadow
                     where rule_id='S02'
                       and race_date between %s and %s
                     order by race_date,race_id
                    """,
                    (START_DATE, END_DATE),
                )
                rows = [dict(r) for r in cur.fetchall()]
            conn.rollback()

    stats = summarize(rows)
    checkpoints = {
        str(n): {
            "target_evaluated": n,
            "reached": int(stats["evaluated"]) >= n,
            "remaining": max(0, n - int(stats["evaluated"])),
        }
        for n in CHECKPOINTS
    }
    out = {
        "frozen_config": FROZEN_CONFIG,
        "frozen_config_sha256": FROZEN_CONFIG_SHA256,
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "forward": stats,
        "checkpoints": checkpoints,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print(
        "VALUE_S02_FORWARD_STATS="
        f"eligible:{stats['eligible_rows']} evaluated:{stats['evaluated']} pending:{stats['pending']} "
        f"hits:{stats['hits']} roi:{stats['roi_pct']} profit:{stats['profit_yen']} "
        f"single_hit_share:{stats['single_hit_share_pct']} lose_streak:{stats['max_losing_streak']} max_dd:{stats['max_drawdown_yen']}",
        flush=True,
    )
    for n in CHECKPOINTS:
        cp = checkpoints[str(n)]
        print(f"VALUE_S02_FORWARD_CHECKPOINT={n} reached:{int(cp['reached'])} remaining:{cp['remaining']}", flush=True)
    print("VALUE_S02_FORWARD_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S02_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
