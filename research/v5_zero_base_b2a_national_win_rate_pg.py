# -*- coding: utf-8 -*-
"""
V5 zero-base B2A backtest: national racer win-rate only.

Feature
-------
Only v2_race_entries.national_win_rate is used.

Fixed estimator (no tuning):
    p_i = national_win_rate_i / sum(national_win_rate_1..6)

national_win_rate is treated only as a relative pre-race strength measure.
No V4 coefficient, class, place rate, lane, motor, ST, venue, exhibition,
weather, odds, or selector information is used.

Coverage
--------
Only completed races with exactly six valid lane entries and six finite,
non-negative national_win_rate values with a positive total are scored.
The B0 comparator is the exact 1/6 baseline and is therefore identical on
any subset.

Defaults:
    START_DATE=2025-07-01
    END_DATE=2026-10-05

Safety:
- DB read-only.
- No Production/LINE/purchase/stake/model/settings changes.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from typing import Any

from db_pg import fetch_all

VERSION = "2026-10-08-v1"
START_DATE = os.getenv("START_DATE", "2025-07-01")
END_DATE = os.getenv("END_DATE", "2026-10-05")
NUMERIC_FLOOR = 1e-15

B0_LOGLOSS = -math.log(1.0 / 6.0)
B0_BRIER_SUM = (1.0 - 1.0 / 6.0) ** 2 + 5.0 * ((1.0 / 6.0) ** 2)


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


def load_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result_cols = _table_columns("v2_results")
    entry_cols = _table_columns("v2_race_entries")
    if not result_cols or "national_win_rate" not in entry_cols:
        raise RuntimeError("required result/entry columns are unavailable")

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

    results = fetch_all(
        f"""
        select r.race_id, r.race_date, {winner} as winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_date, r.race_id
        """,
        (START_DATE, END_DATE),
    )

    entries = fetch_all(
        """
        select e.race_id, e.lane, e.national_win_rate
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by e.race_id, e.lane
        """,
        (START_DATE, END_DATE),
    )
    return results, entries


def _float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def main() -> None:
    results, entries = load_rows()
    if not results:
        raise RuntimeError("B2A: no completed races in target period")

    by_race: defaultdict[str, dict[int, float]] = defaultdict(dict)
    invalid_entry_rows = 0

    for e in entries:
        rid = str(e["race_id"])
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid_entry_rows += 1
            continue
        rate = _float(e.get("national_win_rate"))
        if not (1 <= lane <= 6) or rate is None or rate < 0:
            invalid_entry_rows += 1
            continue
        by_race[rid][lane] = rate

    logloss_total = 0.0
    brier_total = 0.0
    top1_hits = 0
    scored = 0
    skipped_incomplete6 = 0
    skipped_nonpositive_total = 0
    winner_counts: Counter[int] = Counter()
    top_lane_counts: Counter[int] = Counter()

    for r in results:
        rid = str(r["race_id"])
        winner = int(r["winner_lane"])
        lane_rates = by_race.get(rid, {})

        if len(lane_rates) != 6 or any(lane not in lane_rates for lane in range(1, 7)):
            skipped_incomplete6 += 1
            continue

        rates = [lane_rates[lane] for lane in range(1, 7)]
        total = sum(rates)
        if total <= 0:
            skipped_nonpositive_total += 1
            continue

        probs = [x / total for x in rates]
        p_win = max(probs[winner - 1], NUMERIC_FLOOR)
        logloss_total += -math.log(p_win)

        y = [0.0] * 6
        y[winner - 1] = 1.0
        brier_total += sum((probs[i] - y[i]) ** 2 for i in range(6))

        max_p = max(probs)
        top_lanes = [i + 1 for i, p in enumerate(probs) if abs(p - max_p) < 1e-15]
        if len(top_lanes) == 1:
            top = top_lanes[0]
            top_lane_counts[top] += 1
            if top == winner:
                top1_hits += 1

        winner_counts[winner] += 1
        scored += 1

    if scored == 0:
        raise RuntimeError("B2A: zero scoreable races with complete national_win_rate")

    logloss = logloss_total / scored
    brier_sum = brier_total / scored

    report = {
        "contract": "V5_ZERO_BASE_B2A_NATIONAL_WIN_RATE_ONLY_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "racer_national_win_rate_only",
            "inputs": ["v2_race_entries.national_win_rate"],
            "lane_number_as_predictor": False,
            "racer_class_used": False,
            "national_place_rate_used": False,
            "v4_prediction_logic_used": False,
            "odds_used": False,
            "selector_used": False,
        },
        "estimator": {
            "method": "within-race direct proportional normalization",
            "formula": "p_i = national_win_rate_i / sum_6",
            "parameter_search": False,
            "learned_coefficients": False,
        },
        "coverage": {
            "completed_result_races": len(results),
            "scored_complete6_races": scored,
            "coverage_pct": 100.0 * scored / len(results),
            "skipped_incomplete6": skipped_incomplete6,
            "skipped_nonpositive_total": skipped_nonpositive_total,
            "invalid_entry_rows": invalid_entry_rows,
            "winner_lane_counts_audit_only": {
                str(i): winner_counts.get(i, 0) for i in range(1, 7)
            },
            "top_predicted_lane_counts_audit_only": {
                str(i): top_lane_counts.get(i, 0) for i in range(1, 7)
            },
        },
        "metrics": {
            "logloss": logloss,
            "brier_multiclass_sum": brier_sum,
            "brier_per_class": brier_sum / 6.0,
            "top1_accuracy": top1_hits / scored,
            "b0_logloss_same_subset": B0_LOGLOSS,
            "b0_brier_multiclass_sum_same_subset": B0_BRIER_SUM,
            "delta_logloss_vs_b0": logloss - B0_LOGLOSS,
            "delta_brier_sum_vs_b0": brier_sum - B0_BRIER_SUM,
            "improved_logloss_vs_b0": logloss < B0_LOGLOSS,
            "improved_brier_vs_b0": brier_sum < B0_BRIER_SUM,
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B2A_NATIONAL_WIN_RATE_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
