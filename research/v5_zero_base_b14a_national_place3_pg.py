# -*- coding: utf-8 -*-
"""
V5 zero-base B14A backtest: national place-2 rate only.

Feature
-------
Only v2_race_entries.national_place3_rate is used.

Fixed estimator (no tuning):
    p_i = national_place3_rate_i / sum(national_place3_rate_1..6)

The field is used only as a relative pre-race strength signal. No lane,
racer class, national win rate, local rate, motor, ST, venue, exhibition,
weather, odds, selector, or V4 prediction logic is used.

Only completed races with exactly six valid lane entries and six finite,
non-negative national_place3_rate values with positive total are scored.

Defaults:
START_DATE=2025-07-01
END_DATE=2026-10-05

Safety:
- DB read-only only.
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
EPS = 1e-15

B0_LOGLOSS = -math.log(1.0 / 6.0)
B0_BRIER_SUM = 5.0 / 6.0


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


def _float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def load_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result_cols = _table_columns("v2_results")
    entry_cols = _table_columns("v2_race_entries")
    if "national_place3_rate" not in entry_cols:
        raise RuntimeError("v2_race_entries.national_place3_rate is unavailable")

    winner = _winner_expr(result_cols)
    filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in result_cols:
        filters.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in result_cols:
        filters.append("coalesce(rs.race_status,'official')='official'")

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
        select e.race_id, e.lane, e.national_place3_rate
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by e.race_id, e.lane
        """,
        (START_DATE, END_DATE),
    )
    return results, entries


def main() -> None:
    results, entries = load_rows()
    if not results:
        raise RuntimeError("B14A: no completed races")

    by_race: defaultdict[str, dict[int, float]] = defaultdict(dict)
    invalid_entry_rows = 0

    for e in entries:
        rid = str(e["race_id"])
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid_entry_rows += 1
            continue
        rate = _float(e.get("national_place3_rate"))
        if not (1 <= lane <= 6) or rate is None or rate < 0:
            invalid_entry_rows += 1
            continue
        by_race[rid][lane] = rate

    ll_total = 0.0
    br_total = 0.0
    top_hits = 0
    unique_top = 0
    scored = 0
    skipped_incomplete6 = 0
    skipped_nonpositive_total = 0
    winner_counts: Counter[int] = Counter()
    top_lane_counts: Counter[int] = Counter()

    for r in results:
        rid = str(r["race_id"])
        winner = int(r["winner_lane"])
        vals = by_race.get(rid, {})

        if len(vals) != 6 or any(lane not in vals for lane in range(1, 7)):
            skipped_incomplete6 += 1
            continue

        rates = [vals[lane] for lane in range(1, 7)]
        total = sum(rates)
        if total <= 0:
            skipped_nonpositive_total += 1
            continue

        probs = [x / total for x in rates]

        ll_total += -math.log(max(probs[winner - 1], EPS))
        y = [0.0] * 6
        y[winner - 1] = 1.0
        br_total += sum((probs[i] - y[i]) ** 2 for i in range(6))

        max_p = max(probs)
        tops = [i + 1 for i, p in enumerate(probs) if abs(p - max_p) < 1e-15]
        if len(tops) == 1:
            unique_top += 1
            top_lane_counts[tops[0]] += 1
            if tops[0] == winner:
                top_hits += 1

        winner_counts[winner] += 1
        scored += 1

    if scored == 0:
        raise RuntimeError("B14A: zero scoreable races")

    logloss = ll_total / scored
    brier = br_total / scored

    report = {
        "contract": "V5_ZERO_BASE_B14A_NATIONAL_PLACE3_RATE_ONLY_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "racer_national_place3_rate_only",
            "inputs": ["v2_race_entries.national_place3_rate"],
            "lane_number_as_predictor": False,
            "racer_class_used": False,
            "national_win_rate_used": False,
            "venue_used": False,
            "v4_prediction_logic_used": False,
            "odds_used": False,
            "selector_used": False,
        },
        "estimator": {
            "method": "within-race direct proportional normalization",
            "formula": "p_i = national_place3_rate_i / sum_6",
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
            "brier_multiclass_sum": brier,
            "brier_per_class": brier / 6.0,
            "top1_accuracy_unique_only": (
                top_hits / unique_top if unique_top else None
            ),
            "unique_top_races": unique_top,
            "b0_logloss_same_subset": B0_LOGLOSS,
            "b0_brier_multiclass_sum_same_subset": B0_BRIER_SUM,
            "delta_logloss_vs_b0": logloss - B0_LOGLOSS,
            "delta_brier_sum_vs_b0": brier - B0_BRIER_SUM,
            "improved_logloss_vs_b0": logloss < B0_LOGLOSS,
            "improved_brier_vs_b0": brier < B0_BRIER_SUM,
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print(
        "V5_B14A_NATIONAL_PLACE3_RESULT="
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )


if __name__ == "__main__":
    main()
