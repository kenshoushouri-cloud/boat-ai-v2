# -*- coding: utf-8 -*-
"""
V5 B1 venue-stratified audit.

Purpose
-------
Re-score the already defined B1 lane-only model and report performance by venue.
Venue is NOT used as a predictor here; it is only an evaluation stratum.

B1 estimator remains:
- lane number only
- previous-days empirical lane win rate
- Laplace alpha=1
- same-day results are scored before being added to history

This separates:
1) model stability by venue (this script), from
2) venue information as a predictive feature (a later separate ablation).

Defaults:
START_DATE=2025-07-01
END_DATE=2026-10-05

Safety: read-only DB access only.
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


def _venue_expr(race_cols: set[str]) -> str:
    if "venue_id" in race_cols and "venue_code" in race_cols:
        return "lpad(coalesce(nullif(r.venue_id::text,''), nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in race_cols:
        return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in race_cols:
        return "lpad(r.venue_code::text,2,'0')"
    raise RuntimeError("v2_races has neither venue_id nor venue_code")


def load_completed_races() -> list[dict[str, Any]]:
    result_cols = _table_columns("v2_results")
    race_cols = _table_columns("v2_races")
    if not result_cols or not race_cols:
        raise RuntimeError("required tables unavailable")

    winner = _winner_expr(result_cols)
    venue = _venue_expr(race_cols)

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
        select r.race_id, r.race_date, {venue} as venue_code, {winner} as winner_lane
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
        raise RuntimeError("no completed races")

    by_day: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_day[_iso_date(r["race_date"])].append(r)

    win_counts: Counter[int] = Counter()
    history_n = 0

    venue_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"n": 0, "ll": 0.0, "br": 0.0, "top_hits": 0.0}
    )

    for ds in sorted(by_day):
        probs = probs_from_history(win_counts, history_n)
        max_p = max(probs)
        top_lanes = [i + 1 for i, p in enumerate(probs) if abs(p - max_p) < 1e-15]
        unique_top = len(top_lanes) == 1
        top_lane = top_lanes[0] if unique_top else None

        day_wins: Counter[int] = Counter()

        for r in by_day[ds]:
            venue = str(r["venue_code"])
            winner = int(r["winner_lane"])
            p = probs[winner - 1]

            st = venue_stats[venue]
            st["n"] += 1
            st["ll"] += -math.log(max(p, 1e-15))

            y = [0.0] * 6
            y[winner - 1] = 1.0
            st["br"] += sum((probs[i] - y[i]) ** 2 for i in range(6))

            if unique_top and winner == top_lane:
                st["top_hits"] += 1

            day_wins[winner] += 1

        win_counts.update(day_wins)
        history_n += sum(day_wins.values())

    out = {}
    for venue in sorted(venue_stats):
        st = venue_stats[venue]
        n = int(st["n"])
        out[venue] = {
            "races": n,
            "logloss": st["ll"] / n,
            "brier_multiclass_sum": st["br"] / n,
            "top1_accuracy_unique_only": st["top_hits"] / n,
        }

    logloss_vals = [v["logloss"] for v in out.values()]
    brier_vals = [v["brier_multiclass_sum"] for v in out.values()]

    report = {
        "contract": "V5_B1_LANE_ONLY_VENUE_AUDIT_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "predictor": {
            "feature_family": "lane_number_only",
            "venue_used_as_predictor": False,
            "same_b1_formula": True,
        },
        "coverage": {
            "completed_races": len(rows),
            "venue_count": len(out),
        },
        "venue_metrics": out,
        "stability_summary": {
            "min_logloss": min(logloss_vals),
            "max_logloss": max(logloss_vals),
            "range_logloss": max(logloss_vals) - min(logloss_vals),
            "min_brier": min(brier_vals),
            "max_brier": max(brier_vals),
            "range_brier": max(brier_vals) - min(brier_vals),
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B1_VENUE_AUDIT_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
