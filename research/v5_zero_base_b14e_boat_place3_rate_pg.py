# -*- coding: utf-8 -*-
"""
V5 zero-base B14E backtest: boat place-2 rate only.

Feature
-------
Only v2_race_entries.boat_place3_rate is used.

Fixed estimator (no tuning):
    p_i = boat_place3_rate_i / sum(boat_place3_rate_1..6)

No lane, racer class, national/local rates, avg_st, boat rate, venue bias,
exhibition, weather, odds, selector, or V4 prediction logic is used.
Venue is evaluation stratum only.

Defaults:
START_DATE=2025-07-01
END_DATE=2026-10-05
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
B0_LL = -math.log(1.0 / 6.0)
B0_BR = 5.0 / 6.0


def _cols(table: str) -> set[str]:
    rows = fetch_all(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=%s",
        (table,),
    )
    return {str(r["column_name"]) for r in rows}


def _winner_expr(cols: set[str]) -> str:
    if "first_lane" in cols:
        return "rs.first_lane::int"
    if "trifecta_ticket" in cols:
        return (
            "nullif(substring(regexp_replace(rs.trifecta_ticket::text,"
            " '[^0-9]', '', 'g') from 1 for 1), '')::int"
        )
    raise RuntimeError("winner field unavailable")


def _venue_expr(cols: set[str]) -> str:
    if "venue_id" in cols and "venue_code" in cols:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in cols:
        return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in cols:
        return "lpad(r.venue_code::text,2,'0')"
    return "'NA'"


def _float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load():
    rc = _cols("v2_results")
    rr = _cols("v2_races")
    ec = _cols("v2_race_entries")
    if "boat_place3_rate" not in ec:
        raise RuntimeError("v2_race_entries.boat_place3_rate unavailable")

    winner = _winner_expr(rc)
    venue = _venue_expr(rr)
    filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in rc:
        filters.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in rc:
        filters.append("coalesce(rs.race_status,'official')='official'")

    results = fetch_all(
        f"""
        select r.race_id,{venue} venue_code,{winner} winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_id
        """,
        (START_DATE, END_DATE),
    )
    entries = fetch_all(
        """
        select e.race_id,e.lane,e.boat_place3_rate
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s and r.race_date <= %s
        order by e.race_id,e.lane
        """,
        (START_DATE, END_DATE),
    )
    return results, entries


def score(p, winner):
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
    hit = 1 if len(tops) == 1 and tops[0] == winner else 0
    return ll, br, hit


def main():
    results, entries = load()
    by_race = defaultdict(dict)
    invalid = 0

    for e in entries:
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid += 1
            continue
        x = _float(e.get("boat_place3_rate"))
        if not (1 <= lane <= 6) or x is None or x < 0 or x > 100:
            invalid += 1
            continue
        by_race[str(e["race_id"])][lane] = x

    ll = br = 0.0
    hits = unique = scored = 0
    skip6 = skip0 = 0
    per_venue = defaultdict(lambda: {"n": 0, "ll": 0.0, "br": 0.0})
    top_counts = Counter()

    for r in results:
        rid = str(r["race_id"])
        vals = by_race.get(rid, {})
        if len(vals) != 6 or any(i not in vals for i in range(1, 7)):
            skip6 += 1
            continue
        raw = [vals[i] for i in range(1, 7)]
        s = sum(raw)
        if s <= 0:
            skip0 += 1
            continue
        p = [x / s for x in raw]
        winner = int(r["winner_lane"])
        a, b, h = score(p, winner)
        ll += a
        br += b
        scored += 1

        m = max(p)
        tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
        if len(tops) == 1:
            unique += 1
            top_counts[tops[0]] += 1
            hits += h

        v = str(r["venue_code"])
        per_venue[v]["n"] += 1
        per_venue[v]["ll"] += a
        per_venue[v]["br"] += b

    if scored == 0:
        raise RuntimeError("zero scoreable races")

    mean_ll = ll / scored
    mean_br = br / scored
    venues_better_ll = venues_better_br = 0
    venue_metrics = {}

    for v in sorted(per_venue):
        s = per_venue[v]
        vn = int(s["n"])
        vl = s["ll"] / vn
        vb = s["br"] / vn
        venue_metrics[v] = {
            "races": vn,
            "logloss": vl,
            "brier": vb,
            "delta_logloss_vs_b0": vl - B0_LL,
            "delta_brier_vs_b0": vb - B0_BR,
        }
        venues_better_ll += int(vl < B0_LL)
        venues_better_br += int(vb < B0_BR)

    report = {
        "contract": "V5_ZERO_BASE_B14E_BOAT_PLACE3_RATE_ONLY_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "boat_place3_rate_only",
            "inputs": ["v2_race_entries.boat_place3_rate"],
            "parameter_search": False,
            "learned_coefficients": False,
            "lane_number_as_predictor": False,
            "racer_class_used": False,
            "national_local_rates_used": False,
            "avg_st_used": False,
            "boat_rate_used": False,
            "venue_bias_used": False,
            "v4_prediction_logic_used": False,
        },
        "coverage": {
            "completed_result_races": len(results),
            "scored_complete6_races": scored,
            "coverage_pct": 100.0 * scored / len(results),
            "skipped_incomplete6": skip6,
            "skipped_nonpositive_total": skip0,
            "invalid_entry_rows": invalid,
            "venue_count": len(per_venue),
        },
        "metrics": {
            "logloss": mean_ll,
            "brier_multiclass_sum": mean_br,
            "brier_per_class": mean_br / 6.0,
            "top1_accuracy_unique_only": hits / unique if unique else None,
            "unique_top_races": unique,
            "delta_logloss_vs_b0": mean_ll - B0_LL,
            "delta_brier_vs_b0": mean_br - B0_BR,
            "improved_logloss_vs_b0": mean_ll < B0_LL,
            "improved_brier_vs_b0": mean_br < B0_BR,
            "venues_better_logloss_vs_b0": venues_better_ll,
            "venues_better_brier_vs_b0": venues_better_br,
        },
        "venue_metrics": venue_metrics,
        "top_predicted_lane_counts_audit_only": {
            str(i): top_counts.get(i, 0) for i in range(1, 7)
        },
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print("V5_B14E_BOAT_PLACE3_RATE_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
