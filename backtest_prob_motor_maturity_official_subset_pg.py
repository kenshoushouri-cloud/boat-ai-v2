# -*- coding: utf-8 -*-
"""Read-only motor maturity diagnostic using externally verified official start dates.

Purpose
-------
The existing v24 ablation shows that replacing the fixed motor 2-place rate
(33.0) with the race-card actual motor 2-place rate improves OOS probability
metrics overall. Before any Production use, this script checks whether that
improvement depends on time since the current motor generation started.

Only venue generations whose start date has been explicitly verified on the
venue's official motor-data page are included. No date is inferred from DB
first-seen. 艇国DB remains secondary cross-check/reference and is not used to
create an unverified start date here.

This is a fixed diagnostic, not tuning:
- same v24 formula / coefficients / PROB_TEMP;
- compare BASE=fixed motor2 33.0 vs MOTOR=race-card actual motor2;
- fixed maturity bins chosen before evaluation;
- no shrinkage coefficient search;
- DB read-only, no Production/LINE/Railway changes.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-24 official-motor-maturity-subset-v1"
END_DATE = os.getenv("MOTOR_MATURITY_END_DATE", "2026-08-15")

# Verified from venue official motor-data pages on 2026-08-24.
# Keep this list conservative: add a venue only after an explicit official
# current-generation use-start date is verified.
MOTOR_GENERATION_START: Dict[str, Tuple[str, str]] = {
    "03": ("2026-05-11", "Edogawa official motor data"),
    "05": ("2026-04-18", "Tamagawa official motor data"),
    "12": ("2026-03-23", "Suminoe official motor ranking"),
    "14": ("2026-04-11", "Naruto official motor data"),
    "23": ("2025-09-05", "Karatsu official motor data"),
}

# Fixed before looking at results. Inclusive lower bound, exclusive upper.
MATURITY_BINS: Tuple[Tuple[str, int, int | None], ...] = (
    ("D00_14", 0, 15),
    ("D15_30", 15, 31),
    ("D31_60", 31, 61),
    ("D61_120", 61, 121),
    ("D121_PLUS", 121, None),
)


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
    boat2 = 34.0  # hold boat fixed: prior ablation found almost no independent gain
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
    raw = {
        lane: lane_strength(by[lane], lane, venue_id, use_actual_motor)
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
    ordered = sorted(probs, key=lambda t: probs[t], reverse=True)
    try:
        return ordered.index(ticket) + 1
    except ValueError:
        return 999


def new_stat() -> Dict[str, float]:
    return {"n": 0.0, "ll_base": 0.0, "ll_motor": 0.0, "brier_base": 0.0,
            "brier_motor": 0.0, "rank_base": 0.0, "rank_motor": 0.0,
            "motor_abs_dev": 0.0}


def add_stat(s: Dict[str, float], base: Dict[str, float], motor: Dict[str, float], winner: str,
             entries: List[Dict[str, Any]]) -> None:
    eps = 1e-15
    s["n"] += 1
    s["ll_base"] += -math.log(max(sf(base.get(winner)), eps))
    s["ll_motor"] += -math.log(max(sf(motor.get(winner)), eps))
    s["rank_base"] += rank_of(base, winner)
    s["rank_motor"] += rank_of(motor, winner)
    bb = bm = 0.0
    for t, p in base.items():
        y = 1.0 if t == winner else 0.0
        bb += (p - y) ** 2
    for t, p in motor.items():
        y = 1.0 if t == winner else 0.0
        bm += (p - y) ** 2
    s["brier_base"] += bb
    s["brier_motor"] += bm
    vals = [sf(e.get("motor_place2_rate"), 33.0) for e in entries]
    s["motor_abs_dev"] += sum(abs(x - 33.0) for x in vals) / len(vals)


def maturity_bin(age_days: int) -> str | None:
    for label, lo, hi in MATURITY_BINS:
        if age_days >= lo and (hi is None or age_days < hi):
            return label
    return None


def emit(label: str, s: Dict[str, float]) -> None:
    n = int(s["n"])
    if not n:
        print(f"{label}=n:0", flush=True)
        return
    lb = s["ll_base"] / n
    lm = s["ll_motor"] / n
    bb = s["brier_base"] / n
    bm = s["brier_motor"] / n
    rb = s["rank_base"] / n
    rm = s["rank_motor"] / n
    dev = s["motor_abs_dev"] / n
    print(
        f"{label}=n:{n} logloss_base:{lb:.8f} logloss_motor:{lm:.8f} "
        f"logloss_delta:{lm-lb:+.8f} brier_base:{bb:.8f} brier_motor:{bm:.8f} "
        f"brier_delta:{bm-bb:+.8f} winner_rank_base:{rb:.4f} winner_rank_motor:{rm:.4f} "
        f"rank_delta:{rm-rb:+.4f} avg_motor2_abs_dev_from33:{dev:.3f}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")
    end = date.fromisoformat(END_DATE)
    starts = {v: date.fromisoformat(ds) for v, (ds, _) in MOTOR_GENERATION_START.items()}
    start = min(starts.values())
    venues = sorted(starts)

    print(f"MOTOR_MATURITY_VERSION={VERSION}", flush=True)
    print("MOTOR_MATURITY_MODE=read_only_fixed_formula_no_tuning", flush=True)
    print(f"MOTOR_MATURITY_PERIOD={start}..{end}", flush=True)
    print(f"MOTOR_MATURITY_VENUES={','.join(venues)}", flush=True)
    for v in venues:
        ds, source = MOTOR_GENERATION_START[v]
        print(f"MOTOR_MATURITY_SOURCE=venue:{v} start:{ds} source:{source}", flush=True)
    print("MOTOR_MATURITY_POLICY=official_start_only_db_first_seen_forbidden_boat_fixed34", flush=True)

    results = fetch_all(
        """select r.race_id,r.race_date,r.venue_id,r.venue_code,res.trifecta_ticket
           from v2_races r join v2_results res on res.race_id=r.race_id
           where r.race_date between %s and %s
             and coalesce(r.venue_id,r.venue_code)=any(%s)
             and res.trifecta_ticket is not null
             and coalesce(res.result_status,'')='official'
             and coalesce(res.race_status,'')='official'
           order by r.race_date,r.race_id""",
        (start.isoformat(), end.isoformat(), venues),
    )
    rb: Dict[str, Dict[str, Any]] = {}
    for r in results:
        rid = str(r.get("race_id") or "")
        venue = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        race_date = r.get("race_date")
        if isinstance(race_date, datetime):
            race_date = race_date.date()
        elif not isinstance(race_date, date):
            race_date = date.fromisoformat(str(race_date))
        if race_date < starts[venue]:
            continue
        winner = v24._norm_ticket(r.get("trifecta_ticket"))
        if winner:
            rb[rid] = {"venue": venue, "date": race_date, "winner": winner}

    entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if rb:
        ids = sorted(rb)
        for e in fetch_all(
            """select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                      local_place2_rate,avg_st,motor_no,motor_place2_rate
               from v2_race_entries where race_id=any(%s) order by race_id,lane""",
            (ids,),
        ):
            entries_by[str(e.get("race_id") or "")].append(e)

    overall = new_stat()
    by_bin = defaultdict(new_stat)
    by_venue = defaultdict(new_stat)
    by_venue_bin = defaultdict(new_stat)
    result_races = full6 = motor_complete = 0

    for rid, meta in rb.items():
        result_races += 1
        entries = entries_by.get(rid, [])
        by = v24._entry_by_lane(entries)
        if len(by) != 6:
            continue
        full6 += 1
        if not all(by[i].get("motor_place2_rate") is not None for i in range(1, 7)):
            continue
        motor_complete += 1
        venue = meta["venue"]
        age = (meta["date"] - starts[venue]).days
        b = maturity_bin(age)
        if b is None:
            continue
        p_base = ticket_probs(entries, venue, False)
        p_motor = ticket_probs(entries, venue, True)
        winner = meta["winner"]
        add_stat(overall, p_base, p_motor, winner, entries)
        add_stat(by_bin[b], p_base, p_motor, winner, entries)
        add_stat(by_venue[venue], p_base, p_motor, winner, entries)
        add_stat(by_venue_bin[(venue, b)], p_base, p_motor, winner, entries)

    print(
        f"MOTOR_MATURITY_COVERAGE=result_races:{result_races} full6:{full6} motor_complete:{motor_complete}",
        flush=True,
    )
    emit("MOTOR_MATURITY_OVERALL", overall)
    for label, _, _ in MATURITY_BINS:
        emit(f"MOTOR_MATURITY_BIN={label}", by_bin[label])
    for venue in venues:
        emit(f"MOTOR_MATURITY_VENUE={venue}", by_venue[venue])
    for venue in venues:
        for label, _, _ in MATURITY_BINS:
            if by_venue_bin[(venue, label)]["n"]:
                emit(f"MOTOR_MATURITY_VENUE_BIN={venue}:{label}", by_venue_bin[(venue, label)])

    young_n = int(by_bin["D00_14"]["n"] + by_bin["D15_30"]["n"])
    mature_n = int(by_bin["D61_120"]["n"] + by_bin["D121_PLUS"]["n"])
    print(f"MOTOR_MATURITY_SAMPLE_GATE=young_0_30:{young_n} mature_61_plus:{mature_n}", flush=True)
    print("MOTOR_MATURITY_INTERPRETATION=diagnostic_only_assess_age_dependence_before_any_shrinkage_or_production_use", flush=True)
    print("MOTOR_MATURITY_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_MATURITY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
