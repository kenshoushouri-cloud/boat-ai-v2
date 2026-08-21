# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all

VERSION = "2026-08-21 v24-motor2-forward-robustness-v1"
JST = timezone(timedelta(hours=9))
END_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
START_DATE = (os.getenv("MOTOR2_FORWARD_REPORT_START_DATE") or "2026-08-20").strip()
UNIT_YEN = max(
    1,
    int(os.getenv("MOTOR2_FORWARD_UNIT_YEN", os.getenv("UNIT_YEN", "100"))),
)


def sf(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except Exception:
        return default


def si(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except Exception:
        return default


def fetch_rows() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        SELECT *
        FROM v2_v24_motor2_forward_shadow
        WHERE race_date >= %s
          AND race_date <= %s
          AND evaluated_at IS NOT NULL
          AND result_ticket IS NOT NULL
          AND payout_yen > 0
        ORDER BY race_date, snapshot_at, id
        """,
        (START_DATE, END_DATE),
    )


def latest_race_ticket(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate overlapping observations by race/ticket, keeping latest snapshot."""
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("race_id") or ""), str(row.get("ticket") or ""))
        if key not in out or str(row.get("snapshot_at") or "") >= str(
            out[key].get("snapshot_at") or ""
        ):
            out[key] = row
    return list(out.values())


def candidate_kind(row: Dict[str, Any]) -> str:
    low = bool(row.get("motor2_low_candidate"))
    mid = bool(row.get("motor2_mid_candidate"))
    if low and mid:
        return "LOW+MID"
    if low:
        return "LOW"
    if mid:
        return "MID"
    return "NONE"


def is_motor2_candidate(row: Dict[str, Any]) -> bool:
    return candidate_kind(row) != "NONE"


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
    if odds < 40:
        return "30-40"
    if odds < 50:
        return "40-50"
    return "50+"


def month_key(row: Dict[str, Any]) -> str:
    return str(row.get("race_date") or "")[:7] or "UNKNOWN"


def venue_key(row: Dict[str, Any]) -> str:
    return str(row.get("venue_id") or row.get("venue_code") or "").zfill(2)


def new_stat() -> Dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_payouts": [],
    }


def add(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    if not is_motor2_candidate(row):
        return
    payout = si(row.get("payout_yen"), 0)
    hit = str(row.get("ticket") or "") == str(row.get("result_ticket") or "")
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN
    if hit:
        stat["hits"] += 1
        stat["return"] += payout
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
        "hit_rate": hits / bets * 100 if bets else 0.0,
        "roi": returned / investment * 100 if investment else 0.0,
        "profit": returned - investment,
        "max_payout": max_payout,
        "single_hit_share": max_payout / returned * 100 if returned else 0.0,
        "top3_hit_share": top3_return / returned * 100 if returned else 0.0,
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


def print_grouped(
    title: str,
    rows: Iterable[Dict[str, Any]],
    key_fn,
) -> None:
    groups: Dict[str, Dict[str, Any]] = defaultdict(new_stat)
    for row in rows:
        if is_motor2_candidate(row):
            add(groups[str(key_fn(row))], row)

    print(f"=== {title} ===")
    if not groups:
        print("groups=0")
        return

    for key in sorted(groups):
        print(fmt(key, groups[key]))


def print_phase(label: str, rows: List[Dict[str, Any]]) -> None:
    selected = [row for row in rows if is_motor2_candidate(row)]
    overall = new_stat()
    for row in selected:
        add(overall, row)

    print(f"=== {label} OVERALL ===")
    print(f"unique_rows={len(rows)} candidate_rows={len(selected)}")
    print(fmt("MOTOR2", overall))

    print_grouped(
        f"{label} BY CANDIDATE_KIND",
        selected,
        candidate_kind,
    )
    print_grouped(
        f"{label} BY VENUE",
        selected,
        venue_key,
    )
    print_grouped(
        f"{label} BY ODDS_BUCKET",
        selected,
        lambda row: odds_bucket(row.get("odds")),
    )
    print_grouped(
        f"{label} BY MONTH",
        selected,
        month_key,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    print(f"OK report_v24_motor2_forward_robustness_pg.py VERSION {VERSION}")
    print(f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN}")
    print("READ_ONLY=1 PROD_CHANGE=0 LINE=0 BUY=0")

    raw = fetch_rows()
    pre_observations = [
        row
        for row in raw
        if str(row.get("window_name") or "") in {"morning", "day", "night"}
    ]
    final_observations = [
        row for row in raw if str(row.get("window_name") or "") == "final"
    ]

    pre = latest_race_ticket(pre_observations)
    final = latest_race_ticket(final_observations)

    print(
        f"raw_rows={len(raw)} "
        f"pre_observations={len(pre_observations)} pre_unique={len(pre)} "
        f"final_observations={len(final_observations)} final_unique={len(final)}"
    )

    print_phase("PRE UNIQUE", pre)
    print_phase("FINAL UNIQUE", final)

    print("RESULT=PASS")


if __name__ == "__main__":
    main()
