# -*- coding: utf-8 -*-
"""Read-only motor maturity shrinkage stability audit.

Question
--------
Historical OOS work shows that race-card motor 2-place rates improve the current
v24 trifecta probability model overall, while a hard maturity cutoff did not
improve the independent Aug-16..24 holdout.  This audit tests the softer idea:
shrink a young motor's observed 2-place rate toward 33.0, and gradually trust the
observed rate as strictly-prior appearances accumulate.

Only the five venues whose current-generation motor start dates were already
verified from official BOAT RACE venue pages are used.  DB first-seen is never
used as an exchange date.

This is a predeclared diagnostic family, not Production tuning:
- BASE: fixed motor2=33.0
- FULL: current race-card motor_place2_rate
- K03/K06/K12/K24: 33 + n/(n+K) * (actual-33), where n is that motor's number
  of race-card appearances strictly before the evaluated race within the
  verified current generation.
- fixed v24 formula / motor coefficient 0.45 / PROB_TEMP
- fixed three calendar blocks inherited from the prior temporal audit
- no winner is automatically selected and no Production/LINE/Railway setting is
  changed.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import backtest_prob_motor_prior_appearance_maturity_pg as prior

VERSION = "2026-08-25 motor-maturity-shrinkage-stability-v1"
END_DATE = date.fromisoformat(os.getenv("MOTOR_SHRINK_END_DATE", "2026-08-15"))

# Reuse only previously verified official current-generation starts.
MOTOR_GENERATION_START = prior.MOTOR_GENERATION_START

BLOCKS: Tuple[Tuple[str, date, date], ...] = (
    ("B1_2026MAY11_JUN15", date(2026, 5, 11), date(2026, 6, 15)),
    ("B2_2026JUN16_JUL15", date(2026, 6, 16), date(2026, 7, 15)),
    ("B3_2026JUL16_AUG15", date(2026, 7, 16), date(2026, 8, 15)),
)

# Fixed before running this audit. K behaves like a prior-observation strength.
MODELS: Tuple[Tuple[str, int | None], ...] = (
    ("BASE", -1),
    ("K03", 3),
    ("K06", 6),
    ("K12", 12),
    ("K24", 24),
    ("FULL", None),
)
EPS = 1e-15


def sf(v: Any, d: float = 0.0) -> float:
    return prior.sf(v, d)


def si(v: Any, d: int = 0) -> int:
    return prior.si(v, d)


def block_for(d: date) -> str | None:
    for label, lo, hi in BLOCKS:
        if lo <= d <= hi:
            return label
    return None


def effective_motor2(actual: float, n_prior: int, k: int | None) -> float:
    if k == -1:  # BASE
        return 33.0
    if k is None:  # FULL
        return actual
    alpha = n_prior / (n_prior + k) if n_prior > 0 else 0.0
    return 33.0 + alpha * (actual - 33.0)


def lane_strength(entry: Dict[str, Any], lane: int, venue: str, n_prior: int,
                  k: int | None) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = v24.CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    actual_m2 = sf(entry.get("motor_place2_rate"), 33.0)
    mot2 = effective_motor2(actual_m2, n_prior, k)
    boat2 = 34.0
    avg_st = sf(entry.get("avg_st"), 0.18)
    course_bias = v24.VENUE_COURSE_BIAS.get(venue, v24.DEFAULT_COURSE_BIAS).get(
        lane, v24.DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    return (
        cls_w
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (mot2 / 100.0) * 0.45
        + (boat2 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def ticket_probs(entries: List[Dict[str, Any]], venue: str,
                 prior_by_lane: Dict[int, int], k: int | None) -> Dict[str, float]:
    by = v24._entry_by_lane(entries)
    raw = {
        lane: lane_strength(by[lane], lane, venue, prior_by_lane[lane], k)
        for lane in range(1, 7)
    }
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
    return 1 + sum(1 for t, x in probs.items() if x > p or (x == p and t < ticket))


def new_stat() -> Dict[str, float]:
    return {"n": 0.0, "ll": 0.0, "br": 0.0, "rk": 0.0,
            "min_prior": 0.0, "mean_prior": 0.0}


def add_stat(s: Dict[str, float], probs: Dict[str, float], actual: str,
             min_prior: int, mean_prior: float) -> None:
    s["n"] += 1
    s["ll"] += -math.log(max(probs.get(actual, 0.0), EPS))
    s["br"] += sum((p - (1.0 if t == actual else 0.0)) ** 2 for t, p in probs.items())
    s["rk"] += rank_of(probs, actual)
    s["min_prior"] += min_prior
    s["mean_prior"] += mean_prior


def mean(s: Dict[str, float], key: str) -> float:
    return s[key] / s["n"] if s["n"] else 0.0


def emit(scope: str, model: str, s: Dict[str, float], base: Dict[str, float],
         full: Dict[str, float]) -> None:
    n = int(s["n"])
    if not n:
        print(f"MOTOR_SHRINK_SCOPE={scope} model:{model} n:0", flush=True)
        return
    ll = mean(s, "ll")
    br = mean(s, "br")
    rk = mean(s, "rk")
    print(
        f"MOTOR_SHRINK_SCOPE={scope} model:{model} n:{n} "
        f"ll:{ll:.8f} brier:{br:.8f} rank:{rk:.4f} "
        f"delta_ll_vs_base:{ll-mean(base,'ll'):+.8f} "
        f"delta_brier_vs_base:{br-mean(base,'br'):+.8f} "
        f"delta_rank_vs_base:{rk-mean(base,'rk'):+.4f} "
        f"delta_ll_vs_full:{ll-mean(full,'ll'):+.8f} "
        f"delta_brier_vs_full:{br-mean(full,'br'):+.8f} "
        f"delta_rank_vs_full:{rk-mean(full,'rk'):+.4f} "
        f"avg_min_prior:{mean(s,'min_prior'):.2f} avg_mean_prior:{mean(s,'mean_prior'):.2f}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")

    venues = sorted(MOTOR_GENERATION_START)
    start_all = min(MOTOR_GENERATION_START.values())
    analysis_start = BLOCKS[0][1]
    print(f"MOTOR_SHRINK_VERSION={VERSION}", flush=True)
    print("MOTOR_SHRINK_MODE=read_only_predeclared_shrinkage_family_no_tuning", flush=True)
    print("MOTOR_SHRINK_POLICY=official_generation_subset_db_first_seen_forbidden_strict_prior_counts_no_writes_no_production_no_line", flush=True)
    print("MOTOR_SHRINK_FORMULA=effective_m2_33_plus_n_over_n_plus_k_times_actual_minus_33", flush=True)
    print("MOTOR_SHRINK_MODELS=" + ",".join(name for name, _ in MODELS), flush=True)
    print("MOTOR_SHRINK_BLOCKS=" + ",".join(label for label, _, _ in BLOCKS), flush=True)
    print(f"MOTOR_SHRINK_PERIOD={analysis_start}..{END_DATE} prior_count_start:{start_all}", flush=True)
    print("MOTOR_SHRINK_VENUES=" + ",".join(venues), flush=True)

    races = fetch_all(
        """select race_id,race_date::date race_date,race_no::int race_no,
                  lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
             from v2_races
            where race_date between %s and %s
              and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0')=any(%s)
            order by race_date,race_no,race_id""",
        (start_all, END_DATE, venues),
    )
    entries = fetch_all(
        """select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                  e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
             from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
            order by r.race_date,r.race_no,e.lane""",
        (start_all, END_DATE, venues),
    )
    results = fetch_all(
        """select res.race_id,res.trifecta_ticket
             from v2_results res join v2_races r on r.race_id=res.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
              and coalesce(res.result_status,'')='official'
              and coalesce(res.race_status,'')='official'""",
        (start_all, END_DATE, venues),
    )

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}

    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    overall: Dict[str, Dict[str, float]] = {name: new_stat() for name, _ in MODELS}
    by_block: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(new_stat)
    by_venue: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(new_stat)
    coverage = defaultdict(int)

    for r0 in races:
        r = dict(r0)
        rid = str(r["race_id"])
        venue = str(r["venue"])
        rd = r["race_date"]
        if rd < MOTOR_GENERATION_START[venue]:
            coverage["pre_start"] += 1
            continue
        es = sorted(eb.get(rid, []), key=lambda x: si(x.get("lane")))
        actual = rb.get(rid, "")
        valid = (
            len(es) == 6
            and len({si(e.get("lane")) for e in es}) == 6
            and bool(actual)
            and all(si(e.get("motor_no"), 0) > 0 for e in es)
            and all(0.0 <= sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es)
        )
        if not valid:
            coverage["skipped"] += 1
            continue

        prior_by_lane = {
            si(e["lane"]): counts[(venue, str(si(e.get("motor_no"))))]
            for e in es
        }
        min_prior = min(prior_by_lane.values())
        mean_prior = sum(prior_by_lane.values()) / 6.0
        block = block_for(rd)

        # Count pre-analysis races to establish strictly-prior maturity but do not
        # score them.  The evaluated blocks begin at the common May-11 boundary.
        if block is not None:
            probs_by_model = {
                name: ticket_probs(es, venue, prior_by_lane, k)
                for name, k in MODELS
            }
            if actual in probs_by_model["BASE"]:
                for name, _ in MODELS:
                    add_stat(overall[name], probs_by_model[name], actual, min_prior, mean_prior)
                    add_stat(by_block[(block, name)], probs_by_model[name], actual, min_prior, mean_prior)
                    add_stat(by_venue[(venue, name)], probs_by_model[name], actual, min_prior, mean_prior)
                coverage["evaluated"] += 1
            else:
                coverage["skipped"] += 1

        # Strictly prior: current race becomes history only after scoring.
        for e in es:
            counts[(venue, str(si(e.get("motor_no"))))] += 1

    print(
        f"MOTOR_SHRINK_COVERAGE=evaluated:{coverage['evaluated']} skipped:{coverage['skipped']} pre_start:{coverage['pre_start']} venues:{len(venues)}",
        flush=True,
    )
    print("MOTOR_SHRINK_SECTION=OVERALL", flush=True)
    base = overall["BASE"]
    full = overall["FULL"]
    for name, _ in MODELS:
        emit("OVERALL", name, overall[name], base, full)

    print("MOTOR_SHRINK_SECTION=BLOCK", flush=True)
    for block, _, _ in BLOCKS:
        bbase = by_block[(block, "BASE")]
        bfull = by_block[(block, "FULL")]
        for name, _ in MODELS:
            emit(f"BLOCK:{block}", name, by_block[(block, name)], bbase, bfull)

    print("MOTOR_SHRINK_SECTION=BLOCK_STABILITY", flush=True)
    for name, _ in MODELS:
        if name == "BASE":
            continue
        ll_base = br_base = rk_base = ll_full = br_full = rk_full = 0
        for block, _, _ in BLOCKS:
            s = by_block[(block, name)]
            b = by_block[(block, "BASE")]
            f = by_block[(block, "FULL")]
            if not s["n"]:
                continue
            ll_base += mean(s, "ll") < mean(b, "ll")
            br_base += mean(s, "br") < mean(b, "br")
            rk_base += mean(s, "rk") < mean(b, "rk")
            ll_full += mean(s, "ll") < mean(f, "ll")
            br_full += mean(s, "br") < mean(f, "br")
            rk_full += mean(s, "rk") < mean(f, "rk")
        print(
            f"MOTOR_SHRINK_STABILITY=model:{name} "
            f"vs_base_ll:{ll_base}/3 vs_base_brier:{br_base}/3 vs_base_rank:{rk_base}/3 "
            f"vs_full_ll:{ll_full}/3 vs_full_brier:{br_full}/3 vs_full_rank:{rk_full}/3",
            flush=True,
        )

    print("MOTOR_SHRINK_SECTION=VENUE", flush=True)
    for venue in venues:
        vbase = by_venue[(venue, "BASE")]
        vfull = by_venue[(venue, "FULL")]
        for name, _ in MODELS:
            emit(f"VENUE:{venue}", name, by_venue[(venue, name)], vbase, vfull)

    print("MOTOR_SHRINK_INTERPRETATION=HISTORICAL_STABILITY_SCREEN_ONLY_DO_NOT_SELECT_OR_PROMOTE_WITHOUT_NEW_FORWARD", flush=True)
    print("MOTOR_SHRINK_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_SHRINK_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
