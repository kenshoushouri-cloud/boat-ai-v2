# -*- coding: utf-8 -*-
"""Read-only normal-prediction audit: motor actual-rate benefit by prior observations.

This complements the official-generation age audit without treating DB first-seen
as a motor generation start. Only five venues with externally verified official
current-generation start dates are used. For each motor, `prior_appearances` is
the number of race-card appearances already present earlier in the verified
current generation, strictly before the race being evaluated.

Fixed diagnostic only:
- same v24 formula / coefficients / PROB_TEMP;
- BASE uses fixed motor2=33.0;
- MOTOR uses race-card motor_place2_rate;
- boat2 remains fixed at 34.0;
- fixed race-level bins by the minimum prior appearances among the six motors;
- no coefficient/threshold/shrinkage search;
- Railway PostgreSQL read-only; no Production/LINE/Railway changes.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-25 motor-prior-appearance-maturity-v1"
END_DATE = date.fromisoformat(os.getenv("MOTOR_PRIOR_END_DATE", "2026-08-15"))

# Officially verified current-generation start dates from the existing #193 audit.
MOTOR_GENERATION_START: Dict[str, date] = {
    "03": date(2026, 5, 11),
    "05": date(2026, 4, 18),
    "12": date(2026, 3, 23),
    "14": date(2026, 4, 11),
    "23": date(2025, 9, 5),
}

# Predeclared bins on race-level minimum prior observations across all six motors.
PRIOR_BINS: Tuple[Tuple[str, int, int | None], ...] = (
    ("P00_02", 0, 3),
    ("P03_05", 3, 6),
    ("P06_10", 6, 11),
    ("P11_20", 11, 21),
    ("P21_PLUS", 21, None),
)
EPS = 1e-15


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


def lane_strength(entry: Dict[str, Any], lane: int, venue_id: str, use_actual_motor: bool) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    mot2 = sf(entry.get("motor_place2_rate"), 33.0) if use_actual_motor else 33.0
    boat2 = 34.0
    avg_st = sf(entry.get("avg_st"), 0.18)
    course_bias = v24.VENUE_COURSE_BIAS.get(venue_id, v24.DEFAULT_COURSE_BIAS).get(
        lane, v24.DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        cls_w * 1.00
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probs(entries: List[Dict[str, Any]], venue_id: str, use_actual_motor: bool) -> Dict[str, float]:
    by = v24._entry_by_lane(entries)
    raw = {lane: lane_strength(by[lane], lane, venue_id, use_actual_motor) for lane in range(1, 7)}
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    out: Dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        tb = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / tb
            tc = tb - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / tc)
    return out


def rank_of(probs: Dict[str, float], ticket: str) -> int:
    p = probs.get(ticket, -1.0)
    if p < 0:
        return 999
    return 1 + sum(1 for x in probs.values() if x > p)


def bin_for(n: int) -> str:
    for label, lo, hi in PRIOR_BINS:
        if n >= lo and (hi is None or n < hi):
            return label
    return "UNKNOWN"


def new_stat() -> Dict[str, float]:
    return {"n": 0.0, "ll_b": 0.0, "ll_m": 0.0, "br_b": 0.0, "br_m": 0.0,
            "rk_b": 0.0, "rk_m": 0.0, "min_prior": 0.0, "mean_prior": 0.0}


def add_stat(s: Dict[str, float], base: Dict[str, float], motor: Dict[str, float], actual: str,
             min_prior: int, mean_prior: float) -> None:
    pb = max(base.get(actual, 0.0), EPS)
    pm = max(motor.get(actual, 0.0), EPS)
    s["n"] += 1
    s["ll_b"] += -math.log(pb)
    s["ll_m"] += -math.log(pm)
    s["rk_b"] += rank_of(base, actual)
    s["rk_m"] += rank_of(motor, actual)
    s["br_b"] += sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in base.items())
    s["br_m"] += sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in motor.items())
    s["min_prior"] += min_prior
    s["mean_prior"] += mean_prior


def emit(label: str, s: Dict[str, float]) -> None:
    n = int(s["n"])
    if not n:
        print(f"MOTOR_PRIOR={label} n:0", flush=True)
        return
    print(
        f"MOTOR_PRIOR={label} n:{n} "
        f"base_ll:{s['ll_b']/n:.8f} motor_ll:{s['ll_m']/n:.8f} delta_ll:{(s['ll_m']-s['ll_b'])/n:+.8f} "
        f"delta_brier:{(s['br_m']-s['br_b'])/n:+.8f} delta_rank:{(s['rk_m']-s['rk_b'])/n:+.4f} "
        f"avg_min_prior:{s['min_prior']/n:.2f} avg_mean_prior:{s['mean_prior']/n:.2f}",
        flush=True,
    )


def norm_ticket(v: Any) -> str:
    xs = [x for x in str(v or "").replace("-", " ").split() if x in {"1","2","3","4","5","6"}]
    if len(xs) >= 3:
        return "-".join(xs[:3])
    digits = [c for c in str(v or "") if c in "123456"]
    return "-".join(digits[:3]) if len(digits) >= 3 else ""


def main() -> None:
    print(f"MOTOR_PRIOR_MODE=read_only_normal_prediction_fixed_formula version:{VERSION}", flush=True)
    print("MOTOR_PRIOR_POLICY=official_generation_subset_db_first_seen_forbidden_no_tuning_no_writes_no_production_no_line", flush=True)
    print("MOTOR_PRIOR_DEFINITION=prior_appearances_strictly_before_race_within_verified_generation", flush=True)
    print("MOTOR_PRIOR_BINS=" + ",".join(x[0] for x in PRIOR_BINS), flush=True)

    starts = [d for d in MOTOR_GENERATION_START.values()]
    start_all = min(starts)
    venues = sorted(MOTOR_GENERATION_START)
    races = fetch_all(
        """select race_id,race_date::date race_date,race_no::int race_no,
                  lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
             from v2_races
            where race_date between %s and %s
              and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') = any(%s)
            order by race_date,race_no,race_id""",
        (start_all, END_DATE, venues),
    )
    entries = fetch_all(
        """select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                  e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
             from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
            order by r.race_date,r.race_no,e.lane""",
        (start_all, END_DATE, venues),
    )
    results = fetch_all(
        """select res.race_id,res.trifecta_ticket
             from v2_results res join v2_races r on r.race_id=res.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
              and coalesce(res.result_status,'')='official'""",
        (start_all, END_DATE, venues),
    )

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): norm_ticket(x.get("trifecta_ticket")) for x in results}

    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    overall = new_stat()
    by_bin: Dict[str, Dict[str, float]] = defaultdict(new_stat)
    by_venue: Dict[str, Dict[str, float]] = defaultdict(new_stat)
    by_venue_bin: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(new_stat)
    evaluated = skipped = pre_start = 0

    for r0 in races:
        r = dict(r0)
        rid = str(r["race_id"])
        venue = str(r["venue"])
        rd = r["race_date"]
        if rd < MOTOR_GENERATION_START[venue]:
            pre_start += 1
            continue
        es = sorted(eb.get(rid, []), key=lambda x: si(x.get("lane")))
        actual = rb.get(rid, "")
        if len(es) != 6 or len({si(e.get("lane")) for e in es}) != 6 or not actual:
            skipped += 1
            continue
        if any(si(e.get("motor_no"), 0) <= 0 or not (0.0 <= sf(e.get("motor_place2_rate"), -1.0) <= 100.0) for e in es):
            skipped += 1
            continue

        priors = [counts[(venue, str(si(e.get("motor_no"))))] for e in es]
        min_prior = min(priors)
        mean_prior = sum(priors) / 6.0
        base = ticket_probs(es, venue, False)
        motor = ticket_probs(es, venue, True)
        if actual not in base:
            skipped += 1
            continue
        label = bin_for(min_prior)
        add_stat(overall, base, motor, actual, min_prior, mean_prior)
        add_stat(by_bin[label], base, motor, actual, min_prior, mean_prior)
        add_stat(by_venue[venue], base, motor, actual, min_prior, mean_prior)
        add_stat(by_venue_bin[(venue, label)], base, motor, actual, min_prior, mean_prior)
        evaluated += 1

        # Update only after evaluating the current race: strictly prior observations.
        for e in es:
            counts[(venue, str(si(e.get("motor_no"))))] += 1

    print(f"MOTOR_PRIOR_COVERAGE=races:{len(races)} evaluated:{evaluated} skipped:{skipped} pre_start:{pre_start} venues:{len(venues)}", flush=True)
    emit("OVERALL", overall)
    print("MOTOR_PRIOR_SECTION=MIN_PRIOR_BIN", flush=True)
    for label, _, _ in PRIOR_BINS:
        emit(f"BIN:{label}", by_bin[label])
    print("MOTOR_PRIOR_SECTION=VENUE", flush=True)
    for venue in venues:
        emit(f"VENUE:{venue}", by_venue[venue])
    print("MOTOR_PRIOR_SECTION=VENUE_X_BIN", flush=True)
    for venue in venues:
        for label, _, _ in PRIOR_BINS:
            if by_venue_bin[(venue, label)]["n"]:
                emit(f"CROSS:{venue}_{label}", by_venue_bin[(venue, label)])
    print("MOTOR_PRIOR_INTERPRETATION=MATURITY_DIAGNOSTIC_ONLY_REQUIRE_FORWARD_BEFORE_MODEL_USE", flush=True)
    print("MOTOR_PRIOR_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_PRIOR_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
