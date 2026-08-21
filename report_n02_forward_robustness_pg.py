# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

VERSION = "2026-08-21 n02-forward-robustness-v1"
JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("N02_FORWARD_START_DATE", "2026-08-18")
UNIT_YEN = max(1, int(os.getenv("N02_FORWARD_UNIT_YEN", "100")))


def si(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except Exception:
        return default


def sf(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except Exception:
        return default


def fetch_rows() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select id,race_id,race_date,venue_id,race_no,window_name,rule_id,ticket,odds,
               prob,prob_rank,market_rank,raw_ev,snapshot_at,investment_yen,
               result_ticket,payout_yen,hit,return_yen,evaluated_at,
               evaluation_status,evaluation_note
        from v2_candidate_filter_shadow
        where rule_id = 'N02'
          and race_date >= %s
          and race_date <= %s
          and evaluation_status = 'evaluated'
        order by race_date,snapshot_at,race_id,id;
        """,
        (START_DATE, TARGET_DATE),
    )


def latest_race_ticket(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: Dict[tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("race_id") or ""), str(row.get("ticket") or ""))
        if key not in out or str(row.get("snapshot_at") or "") >= str(
            out[key].get("snapshot_at") or ""
        ):
            out[key] = row
    return list(out.values())


def odds_bucket(value: Any) -> str:
    odds = sf(value, 0.0)
    if odds < 3.0:
        return "<3"
    if odds < 4.0:
        return "3-4"
    if odds < 5.0:
        return "4-5"
    if odds < 6.0:
        return "5-6"
    if odds < 10.0:
        return "6-10"
    return "10+"


def new_stat() -> Dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_payouts": [],
    }


def add(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    inv = si(row.get("investment_yen"), UNIT_YEN)
    if inv <= 0:
        inv = UNIT_YEN
    ret = si(row.get("return_yen"), 0)

    stat["bets"] += 1
    stat["investment"] += inv
    stat["return"] += ret

    if bool(row.get("hit")):
        stat["hits"] += 1
        payout = si(row.get("payout_yen"), ret)
        if payout > 0:
            stat["hit_payouts"].append(payout)


def metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    bets = int(stat["bets"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    payouts = sorted((int(x) for x in stat["hit_payouts"]), reverse=True)
    max_payout = payouts[0] if payouts else 0
    top3_return = sum(payouts[:3])
    return {
        "hit_rate": hits / bets * 100.0 if bets else 0.0,
        "roi": returned / investment * 100.0 if investment else 0.0,
        "profit": returned - investment,
        "max_payout": max_payout,
        "single_hit_share": max_payout / returned * 100.0 if returned else 0.0,
        "top3_hit_share": top3_return / returned * 100.0 if returned else 0.0,
    }


def fmt(label: str, stat: Dict[str, Any]) -> str:
    m = metrics(stat)
    return (
        f"{label}: bets={stat['bets']} hits={stat['hits']} "
        f"hit_rate={m['hit_rate']:.2f}% investment={stat['investment']} "
        f"return={stat['return']} profit={int(m['profit'])} ROI={m['roi']:.2f}% "
        f"max_payout={int(m['max_payout'])} "
        f"single_hit_share={m['single_hit_share']:.2f}% "
        f"top3_hit_share={m['top3_hit_share']:.2f}%"
    )


def grouped(title: str, rows: List[Dict[str, Any]], key_fn) -> None:
    groups: Dict[str, Dict[str, Any]] = defaultdict(new_stat)
    for row in rows:
        add(groups[str(key_fn(row))], row)

    print(f"=== {title} ===")
    if not groups:
        print("groups=0")
        return
    for key in sorted(groups):
        print(fmt(key, groups[key]))


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    print(f"OK report_n02_forward_robustness_pg.py VERSION {VERSION}")
    print(f"PERIOD={START_DATE}..{TARGET_DATE} UNIT_YEN={UNIT_YEN}")
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 PROD_CHANGE=0 N02_RULE_CHANGE=0")

    raw = fetch_rows()
    rows = latest_race_ticket(raw)
    overall = new_stat()
    for row in rows:
        add(overall, row)

    print(f"raw_evaluated_rows={len(raw)} unique_race_ticket_rows={len(rows)}")
    print("=== N02 UNIQUE OVERALL ===")
    print(fmt("N02", overall))

    grouped(
        "N02 BY VENUE",
        rows,
        lambda row: str(row.get("venue_id") or "").zfill(2),
    )
    grouped(
        "N02 BY ODDS BUCKET",
        rows,
        lambda row: odds_bucket(row.get("odds")),
    )
    grouped(
        "N02 BY RACE NO",
        rows,
        lambda row: f"R{si(row.get('race_no'), 0):02d}",
    )
    grouped(
        "N02 BY MONTH",
        rows,
        lambda row: str(row.get("race_date") or "")[:7] or "UNKNOWN",
    )

    print("RESULT=PASS")


if __name__ == "__main__":
    main()
