# -*- coding: utf-8 -*-
"""
V5 zero-base B6A: recent form last-5 top3 only.

Source contract
---------------
v2_race_entries.recent_form was reconstructed from official_k_file with:
- strictly earlier calendar dates only;
- same-day results excluded;
- at most five prior races per racer;
- no target-race outcome, payout, or odds.

Feature
-------
For each lane, retain numeric finish_position 1..6 from at most five stored
prior races. Require >=3 valid finishes. Then use fixed Beta(1,1) smoothing:
    strength = (top3_count + 1) / (valid_finish_count + 2)
If fewer than 3 valid finishes, use neutral strength 0.5.
Normalize six strengths within the race.

No lane, racer class, national/local rates, avg_st, motor, boat, venue bias,
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
MIN_VALID = 3
MAX_HISTORY = 5
NEUTRAL = 0.5


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


def _parse_form(v: Any) -> list[dict[str, Any]]:
    if v is None:
        return []
    x = v
    if isinstance(v, str):
        try:
            x = json.loads(v)
        except Exception:
            return []
    if isinstance(x, dict):
        x = x.get("history") or x.get("recent_form") or []
    if not isinstance(x, list):
        return []
    return [dict(z) for z in x[:MAX_HISTORY] if isinstance(z, dict)]


def _feature(v: Any) -> tuple[float, int, int]:
    valid = []
    for item in _parse_form(v):
        try:
            fin = int(item.get("finish_position"))
        except (TypeError, ValueError):
            continue
        if 1 <= fin <= 6:
            valid.append(fin)
    if len(valid) < MIN_VALID:
        return NEUTRAL, len(valid), 0
    top3 = sum(1 for x in valid if x <= 3)
    return (top3 + 1.0) / (len(valid) + 2.0), len(valid), top3


def score(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
    return ll, br, int(len(tops) == 1 and tops[0] == winner)


def main() -> None:
    rc = _cols("v2_results")
    rr = _cols("v2_races")
    ec = _cols("v2_race_entries")
    if "recent_form" not in ec:
        raise RuntimeError("v2_race_entries.recent_form unavailable")

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
        select e.race_id,e.lane,e.recent_form
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s and r.race_date <= %s
        order by e.race_id,e.lane
        """,
        (START_DATE, END_DATE),
    )

    by_race = defaultdict(dict)
    lane_valid_hist = Counter()
    lane_feature_eligible = 0
    invalid_entry_rows = 0

    result_ids = {str(r["race_id"]) for r in results}
    for e in entries:
        rid = str(e["race_id"])
        if rid not in result_ids:
            continue
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid_entry_rows += 1
            continue
        if not 1 <= lane <= 6:
            invalid_entry_rows += 1
            continue
        strength, nvalid, top3 = _feature(e.get("recent_form"))
        by_race[rid][lane] = (strength, nvalid, top3)
        lane_valid_hist[str(nvalid)] += 1
        lane_feature_eligible += int(nvalid >= MIN_VALID)

    ll = br = 0.0
    scored = unique = hits = 0
    incomplete = 0
    races_with_any_feature = 0
    races_with_all6_feature = 0
    per_venue = defaultdict(lambda: {"n": 0, "ll": 0.0, "br": 0.0})

    for r in results:
        rid = str(r["race_id"])
        vals = by_race.get(rid, {})
        if len(vals) != 6 or any(i not in vals for i in range(1, 7)):
            incomplete += 1
            continue

        eligible = sum(1 for i in range(1, 7) if vals[i][1] >= MIN_VALID)
        races_with_any_feature += int(eligible > 0)
        races_with_all6_feature += int(eligible == 6)

        raw = [vals[i][0] for i in range(1, 7)]
        s = sum(raw)
        p = [x / s for x in raw]
        winner_lane = int(r["winner_lane"])
        a, b, h = score(p, winner_lane)
        ll += a
        br += b
        scored += 1

        m = max(p)
        tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
        if len(tops) == 1:
            unique += 1
            hits += h

        v = str(r["venue_code"])
        per_venue[v]["n"] += 1
        per_venue[v]["ll"] += a
        per_venue[v]["br"] += b

    if scored == 0:
        raise RuntimeError("zero scoreable races")

    mean_ll = ll / scored
    mean_br = br / scored
    venue_metrics = {}
    better_ll = better_br = 0
    for v in sorted(per_venue):
        s = per_venue[v]
        n = int(s["n"])
        vl = s["ll"] / n
        vb = s["br"] / n
        venue_metrics[v] = {
            "races": n,
            "logloss": vl,
            "brier": vb,
            "delta_logloss_vs_b0": vl - B0_LL,
            "delta_brier_vs_b0": vb - B0_BR,
        }
        better_ll += int(vl < B0_LL)
        better_br += int(vb < B0_BR)

    lane_obs = scored * 6
    report = {
        "contract": "V5_ZERO_BASE_B6A_RECENT_FORM_LAST5_TOP3_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "feature_family": {
            "name": "recent_form_last5_top3_only",
            "inputs": ["v2_race_entries.recent_form"],
            "source_contract": "BOATRACE_OFFICIAL_K_PRIOR_DAY_RECENT_FORM_V1",
            "strictly_prior_calendar_day": True,
            "same_day_results_used": False,
            "max_history": MAX_HISTORY,
            "min_valid_finishes": MIN_VALID,
            "estimator": "(top3+1)/(valid+2), missing_or_lt3_neutral_0.5",
            "parameter_search": False,
            "learned_coefficients": False,
            "lane_number_as_predictor": False,
            "racer_class_used": False,
            "national_local_rates_used": False,
            "avg_st_used": False,
            "motor_boat_used": False,
            "venue_bias_used": False,
            "v4_prediction_logic_used": False,
        },
        "coverage": {
            "completed_result_races": len(results),
            "scored_complete6_races": scored,
            "coverage_pct": 100.0 * scored / len(results),
            "incomplete_entry_races": incomplete,
            "lane_observations": lane_obs,
            "feature_eligible_lane_observations": lane_feature_eligible,
            "feature_eligible_lane_pct": 100.0 * lane_feature_eligible / lane_obs,
            "races_with_any_eligible_lane": races_with_any_feature,
            "races_with_all6_eligible_lanes": races_with_all6_feature,
            "valid_history_count_distribution": dict(sorted(lane_valid_hist.items())),
            "invalid_entry_rows": invalid_entry_rows,
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
            "venues_better_logloss_vs_b0": better_ll,
            "venues_better_brier_vs_b0": better_br,
        },
        "venue_metrics": venue_metrics,
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }
    print("V5_B6A_RECENT_FORM_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
