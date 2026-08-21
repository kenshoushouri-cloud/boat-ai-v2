# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

VERSION = "2026-08-21 exhibition-shadow-robustness-v1"
JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SHADOW_REPORT_DAYS = max(1, int(os.getenv("SHADOW_REPORT_DAYS", "30")))
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"


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
    if odds < 5:
        return "3-5"
    if odds < 10:
        return "5-10"
    if odds < 20:
        return "10-20"
    if odds < 30:
        return "20-30"
    if odds < 50:
        return "30-50"
    return "50+"


def fetch_rows() -> List[Dict[str, Any]]:
    end_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=SHADOW_REPORT_DAYS - 1)
    return fetch_all(
        """
        select
            r.*,
            d.odds,
            d.market_rank,
            d.exhibition_weight,
            d.head_lane,
            d.head_exhibition_rank
        from v2_exhibition_shadow_results r
        left join v2_exhibition_shadow_decisions d
          on d.race_id = r.race_id
         and d.snapshot_label = r.snapshot_label
         and d.selector_mode = r.selector_mode
         and d.ticket = r.ticket
        where r.race_date >= %s
          and r.race_date <= %s
          and r.snapshot_label = %s
          and r.selector_mode = %s
        order by r.race_date,r.race_id,r.ticket;
        """,
        (str(start_date), str(end_date), SNAPSHOT_LABEL, SELECTOR_MODE),
    )


def new_stat() -> Dict[str, Any]:
    return {
        "candidates": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
    }


def add(stat: Dict[str, Any], row: Dict[str, Any], prefix: str) -> None:
    investment = si(row.get(f"{prefix}_investment_yen"), 0)
    if investment <= 0:
        return
    returned = si(row.get(f"{prefix}_return_yen"), 0)
    stat["candidates"] += 1
    stat["investment"] += investment
    stat["return"] += returned
    if bool(row.get("ticket_hit")):
        stat["hits"] += 1
        if returned > 0:
            stat["hit_returns"].append(returned)


def metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    candidates = int(stat["candidates"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    hit_returns = sorted((int(x) for x in stat["hit_returns"]), reverse=True)
    max_hit = hit_returns[0] if hit_returns else 0
    top3_return = sum(hit_returns[:3])
    return {
        "hit_rate": hits / candidates * 100.0 if candidates else 0.0,
        "roi": returned / investment * 100.0 if investment else 0.0,
        "profit": returned - investment,
        "max_hit": max_hit,
        "single_hit_share": max_hit / returned * 100.0 if returned else 0.0,
        "top3_hit_share": top3_return / returned * 100.0 if returned else 0.0,
    }


def fmt(label: str, stat: Dict[str, Any]) -> str:
    m = metrics(stat)
    return (
        f"{label}: candidates={stat['candidates']} hits={stat['hits']} "
        f"hit_rate={m['hit_rate']:.2f}% investment={stat['investment']} "
        f"return={stat['return']} profit={int(m['profit'])} ROI={m['roi']:.2f}% "
        f"max_hit={int(m['max_hit'])} "
        f"single_hit_share={m['single_hit_share']:.2f}% "
        f"top3_hit_share={m['top3_hit_share']:.2f}%"
    )


def grouped(title: str, rows: List[Dict[str, Any]], key_fn) -> None:
    baseline: Dict[str, Dict[str, Any]] = defaultdict(new_stat)
    shadow: Dict[str, Dict[str, Any]] = defaultdict(new_stat)
    keys = set()

    for row in rows:
        key = str(key_fn(row))
        keys.add(key)
        add(baseline[key], row, "baseline")
        add(shadow[key], row, "shadow")

    print(f"=== {title} ===")
    if not keys:
        print("groups=0")
        return

    for key in sorted(keys):
        print(fmt(f"{key} BASE", baseline[key]))
        print(fmt(f"{key} SHADOW", shadow[key]))
        base_roi = metrics(baseline[key])["roi"]
        shadow_roi = metrics(shadow[key])["roi"]
        print(f"{key} ROI_DELTA={shadow_roi - base_roi:+.2f}pt")


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    print(f"OK report_exhibition_shadow_robustness_pg.py VERSION {VERSION}")
    print(
        f"TARGET_DATE={TARGET_DATE} SHADOW_REPORT_DAYS={SHADOW_REPORT_DAYS} "
        f"SNAPSHOT_LABEL={SNAPSHOT_LABEL} SELECTOR_MODE={SELECTOR_MODE}"
    )
    print("READ_ONLY=1 DB_UPDATE=0 LINE=0 PROD_CHANGE=0 SHADOW_RULE_CHANGE=0")

    rows = fetch_rows()
    baseline = new_stat()
    shadow = new_stat()
    for row in rows:
        add(baseline, row, "baseline")
        add(shadow, row, "shadow")

    print(f"evaluated_rows={len(rows)}")
    print("=== OVERALL ===")
    print(fmt("BASELINE", baseline))
    print(fmt("SHADOW", shadow))
    print(
        f"ROI_DELTA={metrics(shadow)['roi'] - metrics(baseline)['roi']:+.2f}pt"
    )

    grouped(
        "BY CANDIDATE CHANGE",
        rows,
        lambda row: str(row.get("candidate_change") or "none"),
    )
    grouped(
        "BY VENUE",
        rows,
        lambda row: str(row.get("venue_id") or "").zfill(2),
    )
    grouped(
        "BY ODDS BUCKET",
        rows,
        lambda row: odds_bucket(row.get("odds")),
    )
    grouped(
        "BY RACE NO",
        rows,
        lambda row: f"R{si(row.get('race_no'), 0):02d}",
    )
    grouped(
        "BY MONTH",
        rows,
        lambda row: str(row.get("race_date") or "")[:7] or "UNKNOWN",
    )

    print("RESULT=PASS")


if __name__ == "__main__":
    main()
