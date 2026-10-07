# -*- coding: utf-8 -*-
"""
V5 incremental ablation: B1 lane-only vs B1+venue.

Predictors
----------
B1 baseline:
- lane number only
- previous-days GLOBAL empirical lane win rates
- Laplace alpha=1

Candidate:
- lane number + venue
- previous-days VENUE-SPECIFIC empirical lane win rates
- Laplace alpha=1
- before a venue has any prior-day history, fall back to the B1 global lane probabilities

No same-day outcomes are used for same-day predictions.
No tuning, V4 coefficients, racer/motor/ST/exhibition/weather/odds/selector data.

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
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
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


def probs(counts: Counter[int], n: int) -> list[float]:
    denom = n + 6.0 * ALPHA
    return [(counts.get(lane, 0) + ALPHA) / denom for lane in range(1, 7)]


def score_one(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], 1e-15))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    mx = max(p)
    tops = [i + 1 for i, v in enumerate(p) if abs(v - mx) < 1e-15]
    hit = 1 if len(tops) == 1 and tops[0] == winner else 0
    return ll, br, hit


def main() -> None:
    rows = load_completed_races()
    if not rows:
        raise RuntimeError("no completed races")

    by_day: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_day[_iso_date(r["race_date"])].append(r)

    global_counts: Counter[int] = Counter()
    global_n = 0
    venue_counts: defaultdict[str, Counter[int]] = defaultdict(Counter)
    venue_n: Counter[str] = Counter()

    totals = {
        "b1_ll": 0.0,
        "b1_br": 0.0,
        "b1_hit": 0,
        "cand_ll": 0.0,
        "cand_br": 0.0,
        "cand_hit": 0,
        "n": 0,
        "venue_fallback_races": 0,
    }

    per_venue: defaultdict[str, dict[str, float]] = defaultdict(
        lambda: {
            "n": 0,
            "b1_ll": 0.0,
            "cand_ll": 0.0,
            "b1_br": 0.0,
            "cand_br": 0.0,
        }
    )

    for ds in sorted(by_day):
        global_p = probs(global_counts, global_n)

        day_global_wins: Counter[int] = Counter()
        day_venue_wins: defaultdict[str, Counter[int]] = defaultdict(Counter)

        for r in by_day[ds]:
            venue = str(r["venue_code"])
            winner = int(r["winner_lane"])

            b1_p = global_p

            if venue_n[venue] > 0:
                cand_p = probs(venue_counts[venue], venue_n[venue])
            else:
                cand_p = b1_p
                totals["venue_fallback_races"] += 1

            b1_ll, b1_br, b1_hit = score_one(b1_p, winner)
            c_ll, c_br, c_hit = score_one(cand_p, winner)

            totals["b1_ll"] += b1_ll
            totals["b1_br"] += b1_br
            totals["b1_hit"] += b1_hit
            totals["cand_ll"] += c_ll
            totals["cand_br"] += c_br
            totals["cand_hit"] += c_hit
            totals["n"] += 1

            pv = per_venue[venue]
            pv["n"] += 1
            pv["b1_ll"] += b1_ll
            pv["cand_ll"] += c_ll
            pv["b1_br"] += b1_br
            pv["cand_br"] += c_br

            day_global_wins[winner] += 1
            day_venue_wins[venue][winner] += 1

        # Only after the full day has been scored do we add that day's outcomes.
        global_counts.update(day_global_wins)
        global_n += sum(day_global_wins.values())

        for venue, vc in day_venue_wins.items():
            venue_counts[venue].update(vc)
            venue_n[venue] += sum(vc.values())

    n = int(totals["n"])
    if n == 0:
        raise RuntimeError("zero scored races")

    b1_ll = totals["b1_ll"] / n
    b1_br = totals["b1_br"] / n
    cand_ll = totals["cand_ll"] / n
    cand_br = totals["cand_br"] / n

    venue_report = {}
    venues_better_ll = 0
    venues_better_br = 0
    for venue in sorted(per_venue):
        st = per_venue[venue]
        vn = int(st["n"])
        vb1ll = st["b1_ll"] / vn
        vcll = st["cand_ll"] / vn
        vb1br = st["b1_br"] / vn
        vcbr = st["cand_br"] / vn
        if vcll < vb1ll:
            venues_better_ll += 1
        if vcbr < vb1br:
            venues_better_br += 1
        venue_report[venue] = {
            "races": vn,
            "b1_logloss": vb1ll,
            "lane_plus_venue_logloss": vcll,
            "delta_logloss": vcll - vb1ll,
            "b1_brier": vb1br,
            "lane_plus_venue_brier": vcbr,
            "delta_brier": vcbr - vb1br,
        }

    report = {
        "contract": "V5_B1_PLUS_VENUE_INCREMENTAL_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "baseline": {
            "name": "B1_lane_only",
            "method": "previous-days global lane win rates",
            "laplace_alpha": ALPHA,
        },
        "candidate": {
            "name": "lane_plus_venue",
            "method": "previous-days venue-specific lane win rates",
            "laplace_alpha": ALPHA,
            "cold_start_fallback": "B1 global lane probabilities",
            "parameter_search": False,
            "same_day_results_used_for_same_day_prediction": False,
            "other_features_used": False,
        },
        "coverage": {
            "completed_races": n,
            "venue_count": len(per_venue),
            "venue_cold_start_fallback_races": int(totals["venue_fallback_races"]),
        },
        "metrics": {
            "b1_logloss": b1_ll,
            "lane_plus_venue_logloss": cand_ll,
            "delta_logloss_vs_b1": cand_ll - b1_ll,
            "b1_brier_multiclass_sum": b1_br,
            "lane_plus_venue_brier_multiclass_sum": cand_br,
            "delta_brier_vs_b1": cand_br - b1_br,
            "b1_top1_accuracy": totals["b1_hit"] / n,
            "lane_plus_venue_top1_accuracy": totals["cand_hit"] / n,
            "improved_logloss_vs_b1": cand_ll < b1_ll,
            "improved_brier_vs_b1": cand_br < b1_br,
            "venues_better_logloss": venues_better_ll,
            "venues_better_brier": venues_better_br,
        },
        "venue_metrics": venue_report,
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B1_PLUS_VENUE_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
