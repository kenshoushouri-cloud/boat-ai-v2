# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all

VERSION = "2026-08-21 candidate-shadow-robustness-v1"
JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
REPORT_DAYS = max(1, int(os.getenv("CANDIDATE_SHADOW_REPORT_DAYS", "30")))
RULE_IDS = {"S01", "S02", "S03", "S04", "S05"}


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


def odds_bucket(value: Any) -> str:
    odds = sf(value, 0.0)
    if odds < 3:
        return "<3"
    if odds < 6:
        return "3-6"
    if odds < 10:
        return "6-10"
    if odds < 20:
        return "10-20"
    if odds < 30:
        return "20-30"
    if odds < 40:
        return "30-40"
    if odds < 50:
        return "40-50"
    return "50+"


def fetch_rows() -> List[Dict[str, Any]]:
    end_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=REPORT_DAYS - 1)
    return fetch_all(
        """
        select *
        from v2_candidate_filter_shadow
        where race_date >= %s
          and race_date <= %s
          and rule_id in ('S01','S02','S03','S04','S05')
          and evaluation_status = 'evaluated'
        order by race_date,race_id,rule_id,ticket,snapshot_at;
        """,
        (str(start_date), str(end_date)),
    )


def dedup_race_ticket(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Count the same race/ticket once when multiple S-rules selected it."""
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("race_id") or ""), str(row.get("ticket") or ""))
        current = out.get(key)
        if current is None or str(row.get("snapshot_at") or "") >= str(
            current.get("snapshot_at") or ""
        ):
            out[key] = row
    return list(out.values())


def new_stat() -> Dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
    }


def add(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    investment = si(row.get("investment_yen"), 100)
    if investment <= 0:
        investment = 100
    returned = si(row.get("return_yen"), 0)
    stat["bets"] += 1
    stat["investment"] += investment
    stat["return"] += returned
    if bool(row.get("hit")):
        stat["hits"] += 1
        if returned > 0:
            stat["hit_returns"].append(returned)


def metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    bets = int(stat["bets"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    hit_returns = sorted((int(x) for x in stat["hit_returns"]), reverse=True)
    max_hit = hit_returns[0] if hit_returns else 0
    top3_return = sum(hit_returns[:3])
    return {
        "hit_rate": hits / bets * 100.0 if bets else 0.0,
        "roi": returned / investment * 100.0 if investment else 0.0,
        "profit": returned - investment,
        "max_hit": max_hit,
        "single_hit_share": max_hit / returned * 100.0 if returned else 0.0,
        "top3_hit_share": top3_return / returned * 100.0 if returned else 0.0,
    }


def fmt(label: str, stat: Dict[str, Any]) -> str:
    m = metrics(stat)
    return (
        f"{label}: bets={stat['bets']} hits={stat['hits']} "
        f"hit_rate={m['hit_rate']:.2f}% investment={stat['investment']} "
        f"return={stat['return']} profit={int(m['profit'])} ROI={m['roi']:.2f}% "
        f"max_hit={int(m['max_hit'])} "
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

    print(f"OK report_candidate_filter_shadow_robustness_pg.py VERSION {VERSION}")
    print(f"TARGET_DATE={TARGET_DATE} REPORT_DAYS={REPORT_DAYS}")
    print("RULE_SCOPE=S01,S02,S03,S04,S05")
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 PROD_CHANGE=0 RULE_CHANGE=0")

    rule_rows = fetch_rows()
    unique_rows = dedup_race_ticket(rule_rows)

    overall = new_stat()
    for row in unique_rows:
        add(overall, row)

    print(
        f"evaluated_rule_rows={len(rule_rows)} "
        f"unique_race_ticket_rows={len(unique_rows)} "
        f"duplicate_rule_matches={len(rule_rows)-len(unique_rows)}"
    )
    print("=== DEDUP OVERALL ===")
    print(fmt("S01-S05", overall))

    grouped(
        "RULE ROWS BY RULE",
        rule_rows,
        lambda row: str(row.get("rule_id") or "UNKNOWN"),
    )
    grouped(
        "DEDUP BY VENUE",
        unique_rows,
        lambda row: str(row.get("venue_id") or "").zfill(2),
    )
    grouped(
        "DEDUP BY ODDS BUCKET",
        unique_rows,
        lambda row: odds_bucket(row.get("odds")),
    )
    grouped(
        "DEDUP BY RACE NO",
        unique_rows,
        lambda row: f"R{si(row.get('race_no'), 0):02d}",
    )
    grouped(
        "DEDUP BY MONTH",
        unique_rows,
        lambda row: str(row.get("race_date") or "")[:7] or "UNKNOWN",
    )

    print("RESULT=PASS")


if __name__ == "__main__":
    main()
