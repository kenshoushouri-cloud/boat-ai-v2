# -*- coding: utf-8 -*-
"""
V5 zero-base B7A: racer-course compatibility only.

Definition
----------
- Historical source: v2_result_entries rows with racer_number, actual start_course
  and numeric finish_position.
- Target course proxy: current entry lane (pre-race known).
- Same-day outcomes are excluded: every target calendar day is scored first,
  then that day's results update history.
- For each course, build a population top3 prior from strictly earlier days.
- For each racer×course cell, estimate top3 rate and empirically shrink it
  toward the course population prior using a method-of-moments between-racer
  variance estimate. No coefficient or threshold search.
- Normalize the six adjusted top3 strengths within the target race.

This is a standalone screening test. It does not use lane probability directly,
racer class, national/local rates, avg_st, motor, recent_form, venue bias,
exhibition, weather, odds, selector, or V4 prediction logic.

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
START_DATE = date.fromisoformat(os.getenv("START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("END_DATE", "2026-10-05"))
EPS = 1e-12
B0_LL = -math.log(1.0 / 6.0)
B0_BR = 5.0 / 6.0


def _as_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


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


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def score(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
    return ll, br, int(len(tops) == 1 and tops[0] == winner)


def course_prior(course: int, starts: Counter[int], top3: Counter[int]) -> float:
    # Neutral Beta(1,1) only at the course-population level.
    return (top3.get(course, 0) + 1.0) / (starts.get(course, 0) + 2.0)


def cell_rate(
    racer: int,
    course: int,
    prior: float,
    rc_starts: dict[int, Counter[int]],
    rc_top3: dict[int, Counter[int]],
) -> tuple[float, int]:
    n = rc_starts[course].get(racer, 0)
    t = rc_top3[course].get(racer, 0)
    # Small fixed stabilization before method-of-moments shrinkage.
    return (t + 2.0 * prior) / (n + 2.0), n


def tau2_for_course(
    course: int,
    prior: float,
    rc_starts: dict[int, Counter[int]],
    rc_top3: dict[int, Counter[int]],
) -> float:
    vals: list[float] = []
    svars: list[float] = []
    for racer, n in rc_starts[course].items():
        if n <= 0:
            continue
        r, _ = cell_rate(racer, course, prior, rc_starts, rc_top3)
        vals.append(r)
        svars.append(max(r * (1.0 - r) / n, EPS))
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    sample_var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
    mean_svar = sum(svars) / len(svars)
    return max(0.0, sample_var - mean_svar)


def adjusted_strength(
    racer: int,
    course: int,
    cprior: float,
    tau2: float,
    rc_starts: dict[int, Counter[int]],
    rc_top3: dict[int, Counter[int]],
) -> tuple[float, int, float]:
    r, n = cell_rate(racer, course, cprior, rc_starts, rc_top3)
    if n <= 0 or tau2 <= 0.0:
        w = 0.0
    else:
        svar = max(r * (1.0 - r) / n, EPS)
        w = tau2 / (tau2 + svar)
    return max(w * r + (1.0 - w) * cprior, EPS), n, w


def main() -> None:
    race_cols = _cols("v2_races")
    entry_cols = _cols("v2_race_entries")
    result_cols = _cols("v2_results")
    re_cols = _cols("v2_result_entries")

    for req in ("racer_number", "lane"):
        if req not in entry_cols:
            raise RuntimeError(f"v2_race_entries.{req} unavailable")
    for req in ("racer_number", "start_course", "finish_position", "lane"):
        if req not in re_cols:
            raise RuntimeError(f"v2_result_entries.{req} unavailable")

    winner = _winner_expr(result_cols)
    venue = _venue_expr(race_cols)

    result_filters = [
        "r.race_date >= %s",
        "r.race_date <= %s",
        f"({winner}) between 1 and 6",
    ]
    if "result_status" in result_cols:
        result_filters.append("coalesce(rs.result_status,'official')='official'")
    if "race_status" in result_cols:
        result_filters.append("coalesce(rs.race_status,'official')='official'")

    races = fetch_all(
        f"""
        select r.race_id,r.race_date::date race_date,{venue} venue_code,
               {winner} winner_lane
        from v2_races r
        join v2_results rs on rs.race_id=r.race_id
        where {' and '.join(result_filters)}
        order by r.race_date,r.race_id
        """,
        (START_DATE, END_DATE),
    )

    entries = fetch_all(
        """
        select e.race_id,r.race_date::date race_date,e.lane,e.racer_number
        from v2_race_entries e
        join v2_races r on r.race_id=e.race_id
        where r.race_date >= %s and r.race_date <= %s
        order by r.race_date,e.race_id,e.lane
        """,
        (START_DATE, END_DATE),
    )

    hist = fetch_all(
        """
        select re.race_id,r.race_date::date race_date,re.lane,re.racer_number,
               re.start_course,re.finish_position
        from v2_result_entries re
        join v2_races r on r.race_id=re.race_id
        where r.race_date >= %s and r.race_date <= %s
          and re.racer_number is not null
        order by r.race_date,re.race_id,re.lane
        """,
        (START_DATE, END_DATE),
    )

    winner_by_race = {str(r["race_id"]): int(r["winner_lane"]) for r in races}
    date_by_race = {str(r["race_id"]): _as_date(r["race_date"]) for r in races}
    venue_by_race = {str(r["race_id"]): str(r["venue_code"]) for r in races}

    racers_by_race: defaultdict[str, dict[int, int]] = defaultdict(dict)
    invalid_entry_rows = 0
    for e in entries:
        rid = str(e["race_id"])
        if rid not in winner_by_race:
            continue
        lane = _int(e.get("lane"))
        racer = _int(e.get("racer_number"))
        if lane is None or racer is None or not (1 <= lane <= 6) or racer <= 0:
            invalid_entry_rows += 1
            continue
        racers_by_race[rid][lane] = racer

    hist_by_day: defaultdict[date, list[tuple[int, int, int]]] = defaultdict(list)
    invalid_history_rows = 0
    for h in hist:
        racer = _int(h.get("racer_number"))
        course = _int(h.get("start_course"))
        finish = _int(h.get("finish_position"))
        if (
            racer is None or racer <= 0
            or course is None or not (1 <= course <= 6)
            or finish is None or not (1 <= finish <= 6)
        ):
            invalid_history_rows += 1
            continue
        hist_by_day[_as_date(h["race_date"])].append((racer, course, finish))

    races_by_day: defaultdict[date, list[str]] = defaultdict(list)
    incomplete = 0
    for rid in winner_by_race:
        rr = racers_by_race.get(rid, {})
        if len(rr) == 6 and all(i in rr for i in range(1, 7)):
            races_by_day[date_by_race[rid]].append(rid)
        else:
            incomplete += 1

    course_starts: Counter[int] = Counter()
    course_top3: Counter[int] = Counter()
    rc_starts = {c: Counter() for c in range(1, 7)}
    rc_top3 = {c: Counter() for c in range(1, 7)}

    total = {"n": 0, "ll": 0.0, "br": 0.0, "hit": 0, "unique": 0}
    per_venue = defaultdict(lambda: {"n": 0, "ll": 0.0, "br": 0.0})
    no_prior_lane_obs = 0
    prior_lane_obs = 0
    weight_sum = 0.0
    weight_n = 0

    for day in sorted(races_by_day):
        cpriors = {c: course_prior(c, course_starts, course_top3) for c in range(1, 7)}
        taus = {c: tau2_for_course(c, cpriors[c], rc_starts, rc_top3) for c in range(1, 7)}

        for rid in races_by_day[day]:
            strengths: list[float] = []
            for lane in range(1, 7):
                racer = racers_by_race[rid][lane]
                s, nprior, w = adjusted_strength(
                    racer, lane, cpriors[lane], taus[lane], rc_starts, rc_top3
                )
                strengths.append(s)
                prior_lane_obs += 1
                no_prior_lane_obs += int(nprior == 0)
                weight_sum += w
                weight_n += 1

            denom = sum(strengths)
            p = [x / denom for x in strengths]
            winner_lane = winner_by_race[rid]
            ll, br, hit = score(p, winner_lane)
            total["n"] += 1
            total["ll"] += ll
            total["br"] += br

            m = max(p)
            tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
            if len(tops) == 1:
                total["unique"] += 1
                total["hit"] += hit

            v = venue_by_race[rid]
            per_venue[v]["n"] += 1
            per_venue[v]["ll"] += ll
            per_venue[v]["br"] += br

        # Strict prior-calendar-day update after all target races for this day.
        for racer, course, finish in hist_by_day.get(day, []):
            course_starts[course] += 1
            rc_starts[course][racer] += 1
            if finish <= 3:
                course_top3[course] += 1
                rc_top3[course][racer] += 1

    n = int(total["n"])
    if n == 0:
        raise RuntimeError("zero scoreable races")

    mean_ll = total["ll"] / n
    mean_br = total["br"] / n
    venue_metrics = {}
    better_ll = better_br = 0
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
        better_ll += int(vl < B0_LL)
        better_br += int(vb < B0_BR)

    report = {
        "contract": "V5_ZERO_BASE_B7A_RACER_COURSE_COMPATIBILITY_V1",
        "version": VERSION,
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "feature_family": {
            "name": "racer_course_compatibility_only",
            "target_course_proxy": "entry_lane",
            "history_course": "v2_result_entries.start_course",
            "history_outcome": "finish_position_top3",
            "strictly_prior_calendar_day": True,
            "same_day_results_used": False,
            "estimator": "method_of_moments_empirical_bayes_shrink_to_course_population_top3",
            "parameter_search": False,
            "learned_coefficients": False,
            "direct_lane_probability_used": False,
            "racer_class_used": False,
            "national_local_rates_used": False,
            "avg_st_used": False,
            "motor_recent_form_used": False,
            "venue_bias_used": False,
            "v4_prediction_logic_used": False,
        },
        "coverage": {
            "completed_result_races": len(races),
            "scored_complete6_races": n,
            "coverage_pct": 100.0 * n / len(races),
            "incomplete_entry_races": incomplete,
            "invalid_entry_rows": invalid_entry_rows,
            "invalid_history_rows": invalid_history_rows,
            "lane_observations": prior_lane_obs,
            "no_prior_racer_course_lane_observations": no_prior_lane_obs,
            "no_prior_pct": 100.0 * no_prior_lane_obs / prior_lane_obs if prior_lane_obs else None,
            "mean_empirical_bayes_weight": weight_sum / weight_n if weight_n else None,
            "venue_count": len(per_venue),
        },
        "metrics": {
            "logloss": mean_ll,
            "brier_multiclass_sum": mean_br,
            "brier_per_class": mean_br / 6.0,
            "top1_accuracy_unique_only": (
                total["hit"] / total["unique"] if total["unique"] else None
            ),
            "unique_top_races": total["unique"],
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

    print("V5_B7A_RACER_COURSE_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
