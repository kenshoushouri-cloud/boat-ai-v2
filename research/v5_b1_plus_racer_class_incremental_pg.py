# -*- coding: utf-8 -*-
"""
V5 incremental test: B1 lane-only vs lane + racer class.

Question
--------
Does racer class add predictive value after lane number is already known?

Estimator (fixed, no tuning)
----------------------------
For each target day, using PREVIOUS DAYS ONLY:
1) B1 baseline = global empirical win probability by lane, Laplace alpha=1.
2) For each lane, estimate class-specific win-per-start rates.
3) Empirical-Bayes shrink each lane×class rate toward that lane's B1 rate:
       w = tau^2 / (tau^2 + sampling_variance)
       q = w * cell_rate + (1-w) * lane_rate
   where tau^2 is method-of-moments between-class variance for that lane.
4) For each race, normalize the six q values to sum to 1.
5) Score the whole day before adding that day's outcomes.

Venue is used only as an evaluation stratum, never as a predictor.

No national win/place rate, motor, ST, exhibition, weather, odds,
selector, venue predictor, or V4 prediction logic is used.

Defaults:
START_DATE=2025-07-01
END_DATE=2026-10-05
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
EPS = 1e-12


def _iso_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


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


def _winner_expr(cols: set[str]) -> str:
    if "first_lane" in cols:
        return "rs.first_lane::int"
    if "trifecta_ticket" in cols:
        return (
            "nullif(substring(regexp_replace(rs.trifecta_ticket::text,"
            " '[^0-9]', '', 'g') from 1 for 1), '')::int"
        )
    raise RuntimeError("v2_results has neither first_lane nor trifecta_ticket")


def _venue_expr(cols: set[str]) -> str:
    if "venue_id" in cols and "venue_code" in cols:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in cols:
        return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in cols:
        return "lpad(r.venue_code::text,2,'0')"
    return "'NA'"


def _clean_class(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    return s or None


def load_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rc = _table_columns("v2_results")
    rr = _table_columns("v2_races")
    ec = _table_columns("v2_race_entries")
    if "racer_class" not in ec:
        raise RuntimeError("v2_race_entries.racer_class is unavailable")

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
        select r.race_id, r.race_date, {venue} as venue_code, {winner} as winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(filters)}
        order by r.race_date, r.race_id
        """,
        (START_DATE, END_DATE),
    )

    entries = fetch_all(
        """
        select e.race_id, e.lane, e.racer_class
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by e.race_id, e.lane
        """,
        (START_DATE, END_DATE),
    )
    return results, entries


def lane_probs(lane_wins: Counter[int], n: int) -> list[float]:
    d = n + 6.0 * ALPHA
    return [(lane_wins.get(i, 0) + ALPHA) / d for i in range(1, 7)]


def score(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, x in enumerate(p) if abs(x - m) < 1e-15]
    hit = 1 if len(tops) == 1 and tops[0] == winner else 0
    return ll, br, hit


def cell_rate(
    lane: int,
    cls: str,
    starts: dict[int, Counter[str]],
    wins: dict[int, Counter[str]],
    lane_prior: float,
) -> tuple[float, int]:
    n = starts[lane].get(cls, 0)
    w = wins[lane].get(cls, 0)
    # Prior mean is exactly the B1 lane probability, prior strength 2 only for
    # finite cold-start behavior. Final empirical-Bayes weight below controls
    # how much the observed cell can deviate from lane baseline.
    r = (w + 2.0 * lane_prior) / (n + 2.0)
    return r, n


def adjusted_probs(
    classes: dict[int, str],
    lp: list[float],
    starts: dict[int, Counter[str]],
    wins: dict[int, Counter[str]],
) -> tuple[list[float], list[float]]:
    raw: list[float] = []
    ws: list[float] = []

    for lane in range(1, 7):
        prior = lp[lane - 1]
        observed_classes = sorted(starts[lane].keys())

        vals: list[float] = []
        svars: list[float] = []
        for c in observed_classes:
            r, n = cell_rate(lane, c, starts, wins, prior)
            if n <= 0:
                continue
            vals.append(r)
            svars.append(max(r * (1.0 - r) / n, EPS))

        tau2 = 0.0
        if len(vals) >= 2:
            mean = sum(vals) / len(vals)
            sample_var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
            mean_svar = sum(svars) / len(svars)
            tau2 = max(0.0, sample_var - mean_svar)

        r, n = cell_rate(lane, classes[lane], starts, wins, prior)
        if n <= 0 or tau2 <= 0:
            wgt = 0.0
        else:
            svar = max(r * (1.0 - r) / n, EPS)
            wgt = tau2 / (tau2 + svar)

        q = wgt * r + (1.0 - wgt) * prior
        raw.append(max(q, EPS))
        ws.append(wgt)

    total = sum(raw)
    return [x / total for x in raw], ws


def main() -> None:
    results, entries = load_rows()
    if not results:
        raise RuntimeError("no completed races")

    winner_by_race = {str(r["race_id"]): int(r["winner_lane"]) for r in results}
    date_by_race = {str(r["race_id"]): _iso_date(r["race_date"]) for r in results}
    venue_by_race = {str(r["race_id"]): str(r["venue_code"]) for r in results}

    classes_by_race: defaultdict[str, dict[int, str]] = defaultdict(dict)
    invalid_entry_rows = 0
    for e in entries:
        rid = str(e["race_id"])
        if rid not in winner_by_race:
            continue
        try:
            lane = int(e["lane"])
        except (TypeError, ValueError):
            invalid_entry_rows += 1
            continue
        cls = _clean_class(e.get("racer_class"))
        if not (1 <= lane <= 6) or cls is None:
            invalid_entry_rows += 1
            continue
        classes_by_race[rid][lane] = cls

    races_by_day: defaultdict[str, list[str]] = defaultdict(list)
    skipped_incomplete6 = 0
    for rid in winner_by_race:
        cc = classes_by_race.get(rid, {})
        if len(cc) == 6 and all(i in cc for i in range(1, 7)):
            races_by_day[date_by_race[rid]].append(rid)
        else:
            skipped_incomplete6 += 1

    lane_wins: Counter[int] = Counter()
    global_n = 0
    class_starts = {i: Counter() for i in range(1, 7)}
    class_wins = {i: Counter() for i in range(1, 7)}

    total = {
        "n": 0,
        "b1_ll": 0.0,
        "b1_br": 0.0,
        "b1_hit": 0,
        "cand_ll": 0.0,
        "cand_br": 0.0,
        "cand_hit": 0,
        "weight_sum": 0.0,
        "weight_count": 0,
    }
    per_venue = defaultdict(
        lambda: {"n": 0, "b1_ll": 0.0, "cand_ll": 0.0, "b1_br": 0.0, "cand_br": 0.0}
    )

    for ds in sorted(races_by_day):
        lp = lane_probs(lane_wins, global_n)
        day_lane_wins: Counter[int] = Counter()
        day_class_starts = {i: Counter() for i in range(1, 7)}
        day_class_wins = {i: Counter() for i in range(1, 7)}

        for rid in races_by_day[ds]:
            winner = winner_by_race[rid]
            classes = classes_by_race[rid]
            cp, weights = adjusted_probs(classes, lp, class_starts, class_wins)

            b1_ll, b1_br, b1_hit = score(lp, winner)
            c_ll, c_br, c_hit = score(cp, winner)

            total["n"] += 1
            total["b1_ll"] += b1_ll
            total["b1_br"] += b1_br
            total["b1_hit"] += b1_hit
            total["cand_ll"] += c_ll
            total["cand_br"] += c_br
            total["cand_hit"] += c_hit
            total["weight_sum"] += sum(weights)
            total["weight_count"] += len(weights)

            v = venue_by_race[rid]
            pv = per_venue[v]
            pv["n"] += 1
            pv["b1_ll"] += b1_ll
            pv["cand_ll"] += c_ll
            pv["b1_br"] += b1_br
            pv["cand_br"] += c_br

            for lane in range(1, 7):
                day_class_starts[lane][classes[lane]] += 1
            day_class_wins[winner][classes[winner]] += 1
            day_lane_wins[winner] += 1

        lane_wins.update(day_lane_wins)
        global_n += sum(day_lane_wins.values())
        for lane in range(1, 7):
            class_starts[lane].update(day_class_starts[lane])
            class_wins[lane].update(day_class_wins[lane])

    n = int(total["n"])
    if n == 0:
        raise RuntimeError("zero scoreable races")

    b1_ll = total["b1_ll"] / n
    b1_br = total["b1_br"] / n
    cand_ll = total["cand_ll"] / n
    cand_br = total["cand_br"] / n

    better_ll = 0
    better_br = 0
    venue_delta_ll: dict[str, float] = {}
    venue_delta_br: dict[str, float] = {}
    for v in sorted(per_venue):
        s = per_venue[v]
        vn = int(s["n"])
        dll = s["cand_ll"] / vn - s["b1_ll"] / vn
        dbr = s["cand_br"] / vn - s["b1_br"] / vn
        venue_delta_ll[v] = dll
        venue_delta_br[v] = dbr
        better_ll += int(dll < 0)
        better_br += int(dbr < 0)

    report = {
        "contract": "V5_B1_PLUS_RACER_CLASS_INCREMENTAL_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "candidate": {
            "name": "lane_plus_racer_class_empirical_bayes",
            "added_information": ["v2_race_entries.racer_class"],
            "baseline_information": ["lane_number"],
            "parameter_search": False,
            "same_day_results_used_for_same_day_prediction": False,
            "venue_used_as_predictor": False,
            "national_win_rate_used": False,
            "national_place2_rate_used": False,
            "v4_prediction_logic_used": False,
        },
        "coverage": {
            "completed_result_races": len(results),
            "scored_complete6_races": n,
            "coverage_pct": 100.0 * n / len(results),
            "skipped_incomplete6": skipped_incomplete6,
            "invalid_entry_rows": invalid_entry_rows,
            "venue_count": len(per_venue),
        },
        "metrics": {
            "b1_logloss": b1_ll,
            "lane_plus_class_logloss": cand_ll,
            "delta_logloss_vs_b1": cand_ll - b1_ll,
            "b1_brier": b1_br,
            "lane_plus_class_brier": cand_br,
            "delta_brier_vs_b1": cand_br - b1_br,
            "b1_top1_accuracy": total["b1_hit"] / n,
            "lane_plus_class_top1_accuracy": total["cand_hit"] / n,
            "improved_logloss_vs_b1": cand_ll < b1_ll,
            "improved_brier_vs_b1": cand_br < b1_br,
            "mean_cell_shrinkage_weight": (
                total["weight_sum"] / total["weight_count"]
                if total["weight_count"] else 0.0
            ),
            "venues_better_logloss": better_ll,
            "venues_better_brier": better_br,
        },
        "venue_delta_logloss": venue_delta_ll,
        "venue_delta_brier": venue_delta_br,
        "safety": {
            "db_write": False,
            "production_model_change": False,
            "line_change": False,
            "purchase_change": False,
            "stake_change": False,
        },
    }

    print(
        "V5_B1_PLUS_RACER_CLASS_RESULT="
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )


if __name__ == "__main__":
    main()
