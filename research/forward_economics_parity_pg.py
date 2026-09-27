# -*- coding: utf-8 -*-
"""Read-only parity audit: existing N02 semantics vs common Forward economics."""
from __future__ import annotations

import json
import os
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.forward_economics import coverage, metrics, risk

END_DATE = "2026-09-27"
UNIT_YEN = 100
RULE_PERIODS = {
    "N02": "2026-08-18",
    "S03": "2026-09-13",
}


def si(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def legacy_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if str(r.get("evaluation_status") or "") == "evaluated"]
    hits = 0
    investment = 0
    returned = 0
    max_payout = 0
    for row in evaluated:
        inv = si(row.get("investment_yen"), UNIT_YEN)
        if inv <= 0:
            inv = UNIT_YEN
        ret = si(row.get("return_yen"), 0)
        investment += inv
        returned += ret
        if bool(row.get("hit")):
            hits += 1
            payout = si(row.get("payout_yen"), ret)
            max_payout = max(max_payout, payout)

    return {
        "evaluated": len(evaluated),
        "hits": hits,
        "investment_yen": investment,
        "return_yen": returned,
        "profit_yen": returned - investment,
        "roi_pct": round(returned / investment * 100.0, 4) if investment else None,
        "largest_hit_yen": max_payout,
        "largest_hit_share_pct": (
            round(max_payout / returned * 100.0, 4) if returned else 0.0
        ),
    }


def legacy_risk(rows: list[dict[str, Any]]) -> dict[str, int]:
    evaluated = [r for r in rows if str(r.get("evaluation_status") or "") == "evaluated"]
    streak = max_streak = 0
    equity = peak = 0
    peak_idx = 0
    max_dd = 0
    max_dd_bets = 0

    for i, row in enumerate(evaluated, 1):
        if bool(row.get("hit")):
            streak = 0
        else:
            streak += 1
            max_streak = max(max_streak, streak)

        inv = si(row.get("investment_yen"), UNIT_YEN)
        if inv <= 0:
            inv = UNIT_YEN
        ret = si(row.get("return_yen"), 0)
        equity += ret - inv

        if equity > peak:
            peak = equity
            peak_idx = i

        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_bets = i - peak_idx

    return {
        "max_drawdown_yen": max_dd,
        "max_drawdown_bets": max_dd_bets,
        "max_losing_streak": max_streak,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("FORWARD_ECON_PARITY_POLICY=N02_READ_ONLY_EXISTING_SEMANTICS", flush=True)
    print("FORWARD_ECON_PARITY_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            for rule_id, start_date in RULE_PERIODS.items():
                cur.execute(
                    """
                    select race_id,race_date,evaluation_status,investment_yen,
                           hit,return_yen,payout_yen
                      from v2_candidate_filter_shadow
                     where rule_id=%s
                       and race_date between %s and %s
                     order by race_date,snapshot_at,race_id,id
                    """,
                    (rule_id, start_date, END_DATE),
                )
                rows = [dict(r) for r in cur.fetchall()]

                old_m = legacy_metrics(rows)
                new_m = metrics(rows, unit_yen=UNIT_YEN)
                old_r = legacy_risk(rows)
                new_r = risk(rows, unit_yen=UNIT_YEN)
                cov = coverage(rows)

                comparable_new = {
                    "evaluated": new_m["evaluated"],
                    "hits": new_m["hits"],
                    "investment_yen": new_m["investment_yen"],
                    "return_yen": new_m["return_yen"],
                    "profit_yen": new_m["profit_yen"],
                    "roi_pct": new_m["roi_pct"],
                    "largest_hit_yen": new_m["largest_hit_yen"],
                    "largest_hit_share_pct": new_m["largest_hit_share_pct"],
                }
                if old_m != comparable_new:
                    raise RuntimeError(
                        f"{rule_id} metrics parity failure: "
                        + json.dumps(
                            {"legacy": old_m, "common": comparable_new},
                            sort_keys=True,
                        )
                    )
                if old_r != new_r:
                    raise RuntimeError(
                        f"{rule_id} risk parity failure: "
                        + json.dumps(
                            {"legacy": old_r, "common": new_r},
                            sort_keys=True,
                        )
                    )

                print(
                    f"FORWARD_ECON_PARITY_{rule_id}_COVERAGE="
                    + json.dumps(cov, sort_keys=True),
                    flush=True,
                )
                print(
                    f"FORWARD_ECON_PARITY_{rule_id}_METRICS="
                    + json.dumps(old_m, sort_keys=True),
                    flush=True,
                )
                print(
                    f"FORWARD_ECON_PARITY_{rule_id}_RISK="
                    + json.dumps(old_r, sort_keys=True),
                    flush=True,
                )
        conn.rollback()

    print("FORWARD_ECON_PARITY_RESULT=PASS_EXACT_N02_S03", flush=True)


if __name__ == "__main__":
    main()
