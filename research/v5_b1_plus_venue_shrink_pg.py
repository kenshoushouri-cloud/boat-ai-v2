# -*- coding: utf-8 -*-
"""
V5 incremental ablation: B1 lane-only vs lane+venue with empirical-Bayes shrinkage.

Goal
----
Stabilize venue-specific lane tendencies without hand-tuned weights.

For each target day:
1) Build GLOBAL lane probabilities from previous days only (B1 baseline).
2) For each lane, estimate between-venue variance from previous-day history.
3) Shrink each venue's lane rate toward the global lane rate using:
       w = tau^2 / (tau^2 + sampling_variance)
       p_shrunk = w * p_venue + (1-w) * p_global
4) Normalize the six shrunk lane values to sum to 1.
5) Score the whole target day, then add that day's outcomes to history.

No parameter grid/search. No same-day/future leakage.
Venue is the only added information beyond lane number.

Defaults:
START_DATE=2025-07-01
END_DATE=2026-10-05

Safety: DB read-only only.
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
    raise RuntimeError("v2_races has neither venue_id nor venue_code")


def load_rows() -> list[dict[str, Any]]:
    rc = _table_columns("v2_results")
    rr = _table_columns("v2_races")
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
    d = n + 6.0 * ALPHA
    return [(counts.get(i, 0) + ALPHA) / d for i in range(1, 7)]


def score(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, x in enumerate(p) if abs(x - m) < 1e-15]
    hit = 1 if len(tops) == 1 and tops[0] == winner else 0
    return ll, br, hit


def shrunk_probs(
    venue: str,
    global_p: list[float],
    venue_counts: dict[str, Counter[int]],
    venue_n: Counter[str],
) -> tuple[list[float], list[float]]:
    n_v = venue_n.get(venue, 0)
    if n_v <= 0:
        return global_p[:], [0.0] * 6

    active = [v for v, n in venue_n.items() if n > 0]
    if len(active) < 2:
        return global_p[:], [0.0] * 6

    raw = probs(venue_counts[venue], n_v)
    out = []
    weights = []

    for li in range(6):
        # Previous-days venue proportions for this lane.
        vals = []
        sampling_vars = []
        for v in active:
            nv = venue_n[v]
            pv = probs(venue_counts[v], nv)[li]
            vals.append(pv)
            sampling_vars.append(max(pv * (1.0 - pv) / max(nv, 1), EPS))

        mean = sum(vals) / len(vals)
        if len(vals) > 1:
            sample_var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
        else:
            sample_var = 0.0
        mean_sampling_var = sum(sampling_vars) / len(sampling_vars)
        tau2 = max(0.0, sample_var - mean_sampling_var)

        pv = raw[li]
        s2 = max(pv * (1.0 - pv) / max(n_v, 1), EPS)
        w = tau2 / (tau2 + s2) if tau2 > 0 else 0.0

        # Shrink toward the B1 global lane probability.
        q = w * pv + (1.0 - w) * global_p[li]
        out.append(max(q, EPS))
        weights.append(w)

    s = sum(out)
    out = [x / s for x in out]
    return out, weights


def main() -> None:
    rows = load_rows()
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
        "n": 0,
        "b1_ll": 0.0,
        "b1_br": 0.0,
        "b1_hit": 0,
        "shr_ll": 0.0,
        "shr_br": 0.0,
        "shr_hit": 0,
        "fallback": 0,
        "weight_sum": 0.0,
        "weight_count": 0,
    }
    per_venue: defaultdict[str, dict[str, float]] = defaultdict(
        lambda: {"n": 0, "b1_ll": 0.0, "shr_ll": 0.0, "b1_br": 0.0, "shr_br": 0.0}
    )

    for ds in sorted(by_day):
        gp = probs(global_counts, global_n)

        day_global: Counter[int] = Counter()
        day_venue: defaultdict[str, Counter[int]] = defaultdict(Counter)

        for r in by_day[ds]:
            v = str(r["venue_code"])
            wlane = int(r["winner_lane"])

            if venue_n.get(v, 0) <= 0:
                totals["fallback"] += 1

            sp, ws = shrunk_probs(v, gp, venue_counts, venue_n)
            totals["weight_sum"] += sum(ws)
            totals["weight_count"] += len(ws)

            b1_ll, b1_br, b1_hit = score(gp, wlane)
            sh_ll, sh_br, sh_hit = score(sp, wlane)

            totals["n"] += 1
            totals["b1_ll"] += b1_ll
            totals["b1_br"] += b1_br
            totals["b1_hit"] += b1_hit
            totals["shr_ll"] += sh_ll
            totals["shr_br"] += sh_br
            totals["shr_hit"] += sh_hit

            st = per_venue[v]
            st["n"] += 1
            st["b1_ll"] += b1_ll
            st["shr_ll"] += sh_ll
            st["b1_br"] += b1_br
            st["shr_br"] += sh_br

            day_global[wlane] += 1
            day_venue[v][wlane] += 1

        global_counts.update(day_global)
        global_n += sum(day_global.values())
        for v, c in day_venue.items():
            venue_counts[v].update(c)
            venue_n[v] += sum(c.values())

    n = int(totals["n"])
    b1_ll = totals["b1_ll"] / n
    b1_br = totals["b1_br"] / n
    sh_ll = totals["shr_ll"] / n
    sh_br = totals["shr_br"] / n

    venue_report = {}
    better_ll = 0
    better_br = 0
    for v in sorted(per_venue):
        st = per_venue[v]
        vn = int(st["n"])
        vb1ll = st["b1_ll"] / vn
        vshll = st["shr_ll"] / vn
        vb1br = st["b1_br"] / vn
        vshbr = st["shr_br"] / vn
        better_ll += int(vshll < vb1ll)
        better_br += int(vshbr < vb1br)
        venue_report[v] = {
            "races": vn,
            "b1_logloss": vb1ll,
            "shrunk_logloss": vshll,
            "delta_logloss": vshll - vb1ll,
            "b1_brier": vb1br,
            "shrunk_brier": vshbr,
            "delta_brier": vshbr - vb1br,
        }

    report = {
        "contract": "V5_B1_PLUS_VENUE_EMPIRICAL_BAYES_V1",
        "version": VERSION,
        "period": {"start": START_DATE, "end": END_DATE},
        "candidate": {
            "name": "lane_plus_venue_empirical_bayes_shrinkage",
            "parameter_search": False,
            "same_day_results_used_for_same_day_prediction": False,
            "venue_only_added_information": True,
            "shrinkage_rule": "method-of-moments between-venue variance vs sampling variance",
        },
        "coverage": {
            "completed_races": n,
            "venue_count": len(per_venue),
            "cold_start_fallback_races": int(totals["fallback"]),
        },
        "metrics": {
            "b1_logloss": b1_ll,
            "shrunk_logloss": sh_ll,
            "delta_logloss_vs_b1": sh_ll - b1_ll,
            "b1_brier": b1_br,
            "shrunk_brier": sh_br,
            "delta_brier_vs_b1": sh_br - b1_br,
            "b1_top1_accuracy": totals["b1_hit"] / n,
            "shrunk_top1_accuracy": totals["shr_hit"] / n,
            "improved_logloss_vs_b1": sh_ll < b1_ll,
            "improved_brier_vs_b1": sh_br < b1_br,
            "venues_better_logloss": better_ll,
            "venues_better_brier": better_br,
            "mean_lane_shrinkage_weight": (
                totals["weight_sum"] / totals["weight_count"] if totals["weight_count"] else 0.0
            ),
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

    print("V5_B1_PLUS_VENUE_SHRINK_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
