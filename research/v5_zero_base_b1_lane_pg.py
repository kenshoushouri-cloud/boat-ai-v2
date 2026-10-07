# -*- coding: utf-8 -*-
"""
V5 zero-base B1 backtest: lane number only.

Prediction source
-----------------
Only the official lane number (1..6) is used.

For every target day, lane win probabilities are estimated from completed
races on PREVIOUS DAYS ONLY. Results from the current day are scored first,
then added to history. This prevents within-day ordering assumptions and
target/future leakage.

Fixed estimator (not tuned):
    Laplace smoothing alpha = 1.0 per lane.

Defaults:
    START_DATE=2025-07-01
    END_DATE=2026-10-05

Safety:
- DB read-only queries only.
- No V4/V5 prediction code, selector, odds, ticket logic, or feature builder.
- No Production/LINE/purchase/stake/model/settings changes.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from db_pg import fetch_all

VERSION = "2026-10-08-v1"
START_DATE = os.getenv("START_DATE", "2025-07-01")
END_DATE = os.getenv("END_DATE", "2026-10-05")
ALPHA = 1.0
B0_LOGLOSS = -math.log(1.0 / 6.0)
B0_BRIER_SUM = (1.0 - 1.0 / 6.0) ** 2 + 5.0 * ((1.0 / 6.0) ** 2)


def _iso_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _table_columns(table: str) -> set[str]:
    rows = fetch_all(
        """
        select column_name
        from information_schema.columns
        where table_schema='public' and table_name=%s
        """,
        (table,),
    )
    return {str(r["column_name"]) for r in rows}


def _winner_expr(result_cols: set[str]) -> str:
    if "first_lane" in result_cols:
        return "rs.first_lane::int"
    if "trifecta_ticket" in result_cols:
        return (
            "nullif(substring(regexp_replace(rs.trifecta_ticket::text,"
            " '[^0-9]', '', 'g') from 1 for 1), '')::int"
        )
    raise RuntimeError("v2_results has neither first_lane nor trifecta_ticket")


def load_completed_races() -> list[dict[str, Any]]:
    result_cols = _table_columns("v2_results")
    race_cols = _table_columns("v2_races")
    if not result_cols or not race_cols:
        raise RuntimeError("required tables v2_races/v2_results are unavailable")

    winner = _winner_expr(result_cols)
    filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in result_cols:
        filters.append("coalesce(rs.result_status,'official') = 'official'")
    if "race_status" in result_cols:
        filters.append("coalesce(rs.race_status,'official') = 'official'")

    return fetch_all(
        f"""
        select
            r.race_id,
            r.race_date,
            {winner} as winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_date, r.race_id
        """,
        (START_DATE, END_DATE),
    )


def probs_from_history(win_counts: Counter[int], history_n: int) -> list[float]:
    denom = history_n + 6.0 * ALPHA
    return [(win_counts.get(lane, 0) + ALPHA) / denom for lane in range(1, 7)]


def main() -> None:
    rows = load_completed_races()
    if not rows:
        raise RuntimeError("B1: no completed races in target period")

    by_day: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_day[_iso_date(r["race_date"])].append(r)

    win_counts: Counter[int] = Counter()
    history_n = 0

    logloss_total = 0.0
    brier_sum_total = 0.0
    top1_hits = 0
    scored = 0
    day_count = 0
    first_day_probs = None
    last_day_probs = None

    for ds in sorted(by_day):
        probs = probs_from_history(win_counts, history_n)
        if first_day_probs is None:
            first_day_probs = probs[:]
        last_day_probs = probs[:]

        max_p = max(probs)
        top_lanes = [i + 1 for i, p in enumerate(probs) if abs(p - max_p) < 1e-15]
        unique_top = len(top_lanes) == 1
        top_lane = top_lanes[0] if unique_top else None

        day_wins: Counter[int] = Counter()
        for r in by_day[ds]:
            winner = int(r["winner_lane"])
            p = probs[winner - 1]
            logloss_total += -math.log(max(p, 1e-15))

            y = [0.0] * 6
            y[winner - 1] = 1.0
            brier_sum_total += sum((probs[i] - y[i]) ** 2 for i in range(6))

            if unique_top and winner == top_lane:
                top1_hits += 1

            day_wins[winner] += 1
            scored += 1

        win_counts.update(day_wins)
        history_n += sum(day_wins.values())
        day_count += 1

    logloss = logloss_total / scored
    brier_sum = brier_sum_total / scored

    report = {
        "contract": "V5_ZERO_BASE_B1_LANE_ONLY_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "lane_number_only",
            "inputs": ["official lane number 1..6"],
            "v4_prediction_logic_used": False,
            "odds_used": False,
            "selector_used": False,
        },
        "estimator": {
            "method": "previous-days empirical lane win rate",
            "laplace_alpha": ALPHA,
            "same_day_results_used_for_same_day_prediction": False,
            "parameter_search": False,
        },
        "coverage": {
            "completed_races": scored,
            "days": day_count,
            "final_history_races": history_n,
            "winner_lane_counts_audit_only": {
                str(i): win_counts.get(i, 0) for i in range(1, 7)
            },
        },
        "metrics": {
            "logloss": logloss,
            "brier_multiclass_sum": brier_sum,
            "brier_per_class": brier_sum / 6.0,
            "top1_accuracy_unique_only": top1_hits / scored,
            "b0_logloss": B0_LOGLOSS,
            "b0_brier_multiclass_sum": B0_BRIER_SUM,
            "delta_logloss_vs_b0": logloss - B0_LOGLOSS,
            "delta_brier_sum_vs_b0": brier_sum - B0_BRIER_SUM,
            "improved_logloss_vs_b0": logloss < B0_LOGLOSS,
            "improved_brier_vs_b0": brier_sum < B0_BRIER_SUM,
        },
        "probability_audit": {
            "first_target_day_probs": first_day_probs,
            "last_target_day_probs": last_day_probs,
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B1_LANE_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
