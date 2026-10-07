# -*- coding: utf-8 -*-
"""
V5 zero-base B0 backtest.

Purpose
-------
True zero-information baseline for V5 research.

Prediction for every completed six-boat race:
    P(win) = 1/6 for lanes 1..6

This script intentionally does NOT import or call any V4/V5 prediction code,
feature builder, selector, odds logic, ticket logic, or model parameters.

Defaults:
    START_DATE=2025-07-01
    END_DATE=2026-10-05

Safety:
- DB read-only queries only.
- No Production/LINE/purchase/stake/model/settings changes.
- No odds read.
- No feature read.
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


def _iso_date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
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
        # Ticket forms in this repository are normally 1-2-3 / 123.
        # Strip non-digits and take only the first boat.
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

    # Status filters are added only when the columns exist. This avoids silently
    # excluding older valid historical rows from schemas that predate status fields.
    filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in result_cols:
        filters.append("coalesce(rs.result_status,'official') = 'official'")
    if "race_status" in result_cols:
        filters.append("coalesce(rs.race_status,'official') = 'official'")

    sql = f"""
        select
            r.race_id,
            r.race_date,
            {winner} as winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_date, r.race_id
    """
    return fetch_all(sql, (START_DATE, END_DATE))


def main() -> None:
    rows = load_completed_races()
    if not rows:
        raise RuntimeError("B0: no completed races in target period")

    p = 1.0 / 6.0
    per_race_logloss = -math.log(p)

    # Multiclass Brier score: sum_k (p_k - y_k)^2.
    brier_multiclass_sum = (1.0 - p) ** 2 + 5.0 * (p**2)
    brier_per_class = brier_multiclass_sum / 6.0

    lane_counts: Counter[int] = Counter()
    month_counts: defaultdict[str, int] = defaultdict(int)

    for r in rows:
        lane = int(r["winner_lane"])
        lane_counts[lane] += 1
        ds = _iso_date(r["race_date"])
        month_counts[ds[:7]] += 1

    n = len(rows)

    report = {
        "contract": "V5_ZERO_BASE_B0_V1",
        "version": VERSION,
        "period": {
            "start": START_DATE,
            "end": END_DATE,
        },
        "prediction": {
            "lanes": 6,
            "win_probability_each": p,
            "feature_families_used": [],
            "v4_prediction_logic_used": False,
            "odds_used": False,
            "selector_used": False,
        },
        "coverage": {
            "completed_races": n,
            "winner_lane_counts_audit_only": {
                str(i): lane_counts.get(i, 0) for i in range(1, 7)
            },
            "races_by_month": dict(sorted(month_counts.items())),
        },
        "metrics": {
            "logloss": per_race_logloss,
            "brier_multiclass_sum": brier_multiclass_sum,
            "brier_per_class": brier_per_class,
            "top1_accuracy": None,
            "top1_accuracy_note": (
                "Undefined for B0 because all six boats are tied at probability 1/6; "
                "no arbitrary tie-break is scored."
            ),
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B0_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
