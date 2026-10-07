# -*- coding: utf-8 -*-
"""
V5 zero-base B5B: motor prior top2 history, official-generation subset only.

Purpose
-------
Evaluate motor performance while handling exchange-initial uncertainty safely.

Only venues with an already verified official current-generation start date are
included. DB first-seen is NEVER used as an exchange date.

For each target calendar day:
- score every race using history from STRICTLY EARLIER DAYS only;
- for each (venue, motor_no), estimate prior top2 rate:
      (prior_top2 + 1) / (prior_starts + 2)
  which is fixed Laplace/Beta(1,1) smoothing with no tuning;
- unseen/new motors therefore begin at the same neutral 0.5 strength;
- normalize the six motor strengths to race win probabilities;
- only after the full day is scored, update motor history from that day's
  official finish positions.

No lane effect, racer ability, national/local rates, avg_st, race-card
motor_place2_rate, boat rate, venue bias, exhibition, weather, odds, selector,
or V4 prediction logic is used.

Verified official generation starts:
03 2026-05-11
05 2026-04-18
12 2026-03-23
14 2026-04-11
23 2025-09-05

Default END_DATE=2026-10-05.
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
END_DATE = date.fromisoformat(os.getenv("END_DATE", "2026-10-05"))
EPS = 1e-15
B0_LL = -math.log(1.0 / 6.0)
B0_BR = 5.0 / 6.0

MOTOR_GENERATION_START = {
    "03": date(2026, 5, 11),
    "05": date(2026, 4, 18),
    "12": date(2026, 3, 23),
    "14": date(2026, 4, 11),
    "23": date(2025, 9, 5),
}


def _iso_date(v: Any) -> date:
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


def _venue_expr(cols: set[str]) -> str:
    if "venue_id" in cols and "venue_code" in cols:
        return "lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')"
    if "venue_id" in cols:
        return "lpad(r.venue_id::text,2,'0')"
    if "venue_code" in cols:
        return "lpad(r.venue_code::text,2,'0')"
    raise RuntimeError("venue id/code unavailable")


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load():
    rc = _cols("v2_races")
    ec = _cols("v2_race_entries")
    rec = _cols("v2_result_entries")
    need_e = {"race_id", "lane", "motor_no"}
    need_re = {"race_id", "lane", "finish_position"}
    if need_e - ec:
        raise RuntimeError(f"missing v2_race_entries columns: {sorted(need_e-ec)}")
    if need_re - rec:
        raise RuntimeError(f"missing v2_result_entries columns: {sorted(need_re-rec)}")

    venue = _venue_expr(rc)
    starts = list(MOTOR_GENERATION_START.values())
    start_all = min(starts)
    venues = sorted(MOTOR_GENERATION_START)

    races = fetch_all(
        f"""
        select r.race_id, r.race_date::date race_date, r.race_no::int race_no,
               {venue} venue_code
        from v2_races r
        where r.race_date between %s and %s
          and {venue} = any(%s)
        order by r.race_date, r.race_no, r.race_id
        """,
        (start_all, END_DATE, venues),
    )

    entries = fetch_all(
        f"""
        select r.race_id, r.race_date::date race_date, {venue} venue_code,
               e.lane, e.motor_no
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        where r.race_date between %s and %s
          and {venue} = any(%s)
        order by r.race_date, r.race_no, e.lane
        """,
        (start_all, END_DATE, venues),
    )

    results = fetch_all(
        f"""
        select r.race_id, r.race_date::date race_date, {venue} venue_code,
               re.lane, re.finish_position
        from v2_races r
        join v2_result_entries re on re.race_id=r.race_id
        where r.race_date between %s and %s
          and {venue} = any(%s)
        order by r.race_date, r.race_no, re.lane
        """,
        (start_all, END_DATE, venues),
    )
    return races, entries, results


def score(p: list[float], winner: int) -> tuple[float, float, int]:
    ll = -math.log(max(p[winner - 1], EPS))
    y = [0.0] * 6
    y[winner - 1] = 1.0
    br = sum((p[i] - y[i]) ** 2 for i in range(6))
    m = max(p)
    tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
    hit = 1 if len(tops) == 1 and tops[0] == winner else 0
    return ll, br, hit


def bucket(n: int) -> str:
    if n == 0:
        return "P00"
    if n <= 5:
        return "P01_05"
    if n <= 20:
        return "P06_20"
    return "P21_PLUS"


def main() -> None:
    races, entries, results = load()

    race_meta: dict[str, tuple[date, str]] = {}
    for r in races:
        rid = str(r["race_id"])
        race_meta[rid] = (_iso_date(r["race_date"]), str(r["venue_code"]))

    motors: defaultdict[str, dict[int, int]] = defaultdict(dict)
    invalid_entry_rows = 0
    for e in entries:
        rid = str(e["race_id"])
        if rid not in race_meta:
            continue
        lane = _int(e.get("lane"))
        motor = _int(e.get("motor_no"))
        if lane is None or motor is None or not (1 <= lane <= 6) or motor <= 0:
            invalid_entry_rows += 1
            continue
        motors[rid][lane] = motor

    finishes: defaultdict[str, dict[int, int]] = defaultdict(dict)
    invalid_result_rows = 0
    for re in results:
        rid = str(re["race_id"])
        if rid not in race_meta:
            continue
        lane = _int(re.get("lane"))
        fin = _int(re.get("finish_position"))
        if lane is None or fin is None or not (1 <= lane <= 6) or not (1 <= fin <= 6):
            invalid_result_rows += 1
            continue
        finishes[rid][lane] = fin

    races_by_day: defaultdict[date, list[str]] = defaultdict(list)
    pre_start = incomplete = 0
    for rid, (rd, venue) in race_meta.items():
        if rd < MOTOR_GENERATION_START[venue]:
            pre_start += 1
            continue
        if (
            len(motors.get(rid, {})) == 6
            and len(finishes.get(rid, {})) == 6
            and all(i in motors[rid] for i in range(1, 7))
            and all(i in finishes[rid] for i in range(1, 7))
        ):
            races_by_day[rd].append(rid)
        else:
            incomplete += 1

    starts: Counter[tuple[str, int]] = Counter()
    top2: Counter[tuple[str, int]] = Counter()

    total = {
        "n": 0,
        "ll": 0.0,
        "br": 0.0,
        "hit": 0,
        "unique": 0,
    }
    per_venue = defaultdict(lambda: {"n": 0, "ll": 0.0, "br": 0.0})
    prior_bucket_lane_obs = Counter()
    prior_bucket_race_min = Counter()
    prior_sum = 0
    zero_prior_lane_obs = 0

    for rd in sorted(races_by_day):
        day_updates: list[tuple[str, int, int]] = []

        for rid in races_by_day[rd]:
            venue = race_meta[rid][1]
            ms = motors[rid]
            fs = finishes[rid]

            raw: list[float] = []
            priors: list[int] = []
            for lane in range(1, 7):
                key = (venue, ms[lane])
                n = starts[key]
                s2 = top2[key]
                strength = (s2 + 1.0) / (n + 2.0)
                raw.append(strength)
                priors.append(n)
                prior_bucket_lane_obs[bucket(n)] += 1
                prior_sum += n
                zero_prior_lane_obs += int(n == 0)

            s = sum(raw)
            p = [x / s for x in raw]

            winner = next((lane for lane in range(1, 7) if fs[lane] == 1), None)
            if winner is None:
                continue

            ll, br, hit = score(p, winner)
            total["n"] += 1
            total["ll"] += ll
            total["br"] += br
            m = max(p)
            tops = [i + 1 for i, q in enumerate(p) if abs(q - m) < 1e-15]
            if len(tops) == 1:
                total["unique"] += 1
                total["hit"] += hit

            v = per_venue[venue]
            v["n"] += 1
            v["ll"] += ll
            v["br"] += br
            prior_bucket_race_min[bucket(min(priors))] += 1

            for lane in range(1, 7):
                day_updates.append((venue, ms[lane], fs[lane]))

        # Strict previous-calendar-day contract: update only after all races on day scored.
        for venue, motor, fin in day_updates:
            key = (venue, motor)
            starts[key] += 1
            if fin <= 2:
                top2[key] += 1

    n = int(total["n"])
    if n == 0:
        raise RuntimeError("zero scoreable races")

    mean_ll = total["ll"] / n
    mean_br = total["br"] / n
    venue_metrics = {}
    venues_better_ll = venues_better_br = 0
    for venue in sorted(per_venue):
        s = per_venue[venue]
        vn = int(s["n"])
        vl = s["ll"] / vn
        vb = s["br"] / vn
        venue_metrics[venue] = {
            "races": vn,
            "logloss": vl,
            "brier": vb,
            "delta_logloss_vs_b0": vl - B0_LL,
            "delta_brier_vs_b0": vb - B0_BR,
        }
        venues_better_ll += int(vl < B0_LL)
        venues_better_br += int(vb < B0_BR)

    lane_obs = n * 6
    report = {
        "contract": "V5_ZERO_BASE_B5B_MOTOR_PRIOR_TOP2_OFFICIAL_GENERATION_V1",
        "version": VERSION,
        "period": {
            "end": END_DATE.isoformat(),
            "per_venue_start": {k: v.isoformat() for k, v in MOTOR_GENERATION_START.items()},
        },
        "feature_family": {
            "name": "motor_prior_top2_history_only",
            "inputs": [
                "v2_race_entries.motor_no",
                "v2_result_entries.finish_position from strictly earlier calendar days",
            ],
            "race_card_motor_place2_rate_used": False,
            "db_first_seen_as_exchange_date": False,
            "official_generation_start_required": True,
            "estimator": "(prior_top2+1)/(prior_starts+2), normalized within race",
            "parameter_search": False,
            "learned_coefficients": False,
            "same_day_results_used_for_same_day_prediction": False,
            "lane_number_as_predictor": False,
            "racer_ability_used": False,
            "venue_bias_used": False,
            "v4_prediction_logic_used": False,
        },
        "coverage": {
            "verified_venues": sorted(MOTOR_GENERATION_START),
            "venue_count": len(per_venue),
            "scoreable_races": n,
            "pre_official_generation_races_excluded": pre_start,
            "incomplete_races_excluded": incomplete,
            "invalid_entry_rows": invalid_entry_rows,
            "invalid_result_rows": invalid_result_rows,
        },
        "maturity_audit": {
            "lane_observations": lane_obs,
            "zero_prior_lane_observations": zero_prior_lane_obs,
            "zero_prior_lane_pct": 100.0 * zero_prior_lane_obs / lane_obs,
            "mean_prior_starts_per_lane_observation": prior_sum / lane_obs,
            "lane_observation_prior_buckets": dict(sorted(prior_bucket_lane_obs.items())),
            "race_min_prior_buckets": dict(sorted(prior_bucket_race_min.items())),
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
            "venues_better_logloss_vs_b0": venues_better_ll,
            "venues_better_brier_vs_b0": venues_better_br,
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
    print("V5_B5B_MOTOR_PRIOR_TOP2_RESULT=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
