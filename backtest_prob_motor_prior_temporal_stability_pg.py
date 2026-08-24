# -*- coding: utf-8 -*-
"""Read-only temporal stability audit for actual motor 2-place rates.

Follow-up to PR #213.  It keeps the v24 formula fixed and asks whether replacing
fixed motor2=33.0 with the race-card motor_place2_rate improves trifecta
probabilities in each of three predeclared calendar blocks, overall and by venue.

Only the five venues whose current motor-generation start dates were already
verified are included. Prior appearances are counted strictly before each race
from the verified generation start; DB first-seen is never treated as an official
exchange date. No coefficient, threshold, bin boundary, or venue is tuned here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import backtest_prob_motor_prior_appearance_maturity_pg as prior

VERSION = "2026-08-25 motor-prior-temporal-stability-v1"
END_DATE = date(2026, 8, 15)
BLOCKS: Tuple[Tuple[str, date, date], ...] = (
    ("B1_2026MAY11_JUN15", date(2026, 5, 11), date(2026, 6, 15)),
    ("B2_2026JUN16_JUL15", date(2026, 6, 16), date(2026, 7, 15)),
    ("B3_2026JUL16_AUG15", date(2026, 7, 16), date(2026, 8, 15)),
)
# Fixed maturity slices, declared before looking at this audit's outcomes.
MATURITY: Tuple[Tuple[str, int, int | None], ...] = (
    ("YOUNG_P00_05", 0, 6),
    ("MID_P06_20", 6, 21),
    ("MATURE_P21_PLUS", 21, None),
)


def block_for(d: date) -> str | None:
    for label, lo, hi in BLOCKS:
        if lo <= d <= hi:
            return label
    return None


def maturity_for(n: int) -> str:
    for label, lo, hi in MATURITY:
        if n >= lo and (hi is None or n < hi):
            return label
    return "UNKNOWN"


def stat() -> Dict[str, float]:
    return prior.new_stat()


def delta(s: Dict[str, float], key_m: str, key_b: str) -> float:
    return (s[key_m] - s[key_b]) / s["n"] if s["n"] else 0.0


def main() -> None:
    print(f"MOTOR_TEMPORAL_MODE=read_only_fixed_formula_no_tuning version:{VERSION}", flush=True)
    print("MOTOR_TEMPORAL_POLICY=verified_generation_subset_db_first_seen_forbidden_no_selection_no_writes_no_production_no_line", flush=True)
    print("MOTOR_TEMPORAL_BLOCKS=" + ",".join(x[0] for x in BLOCKS), flush=True)
    print("MOTOR_TEMPORAL_MATURITY=" + ",".join(x[0] for x in MATURITY), flush=True)

    venues = sorted(prior.MOTOR_GENERATION_START)
    start_all = min(prior.MOTOR_GENERATION_START.values())
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
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}

    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    by_block: Dict[str, Dict[str, float]] = defaultdict(stat)
    by_venue_block: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(stat)
    by_maturity_block: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(stat)
    coverage = defaultdict(int)

    for r0 in races:
        r = dict(r0)
        rid = str(r["race_id"])
        venue = str(r["venue"])
        rd = r["race_date"]
        if rd < prior.MOTOR_GENERATION_START[venue]:
            coverage["pre_start"] += 1
            continue
        es = sorted(eb.get(rid, []), key=lambda x: prior.si(x.get("lane")))
        actual = rb.get(rid, "")
        valid = (
            len(es) == 6
            and len({prior.si(e.get("lane")) for e in es}) == 6
            and bool(actual)
            and all(prior.si(e.get("motor_no"), 0) > 0 for e in es)
            and all(0.0 <= prior.sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es)
        )
        if not valid:
            coverage["skipped"] += 1
            continue

        priors = [counts[(venue, str(prior.si(e.get("motor_no"))))] for e in es]
        min_prior = min(priors)
        mean_prior = sum(priors) / 6.0
        base = prior.ticket_probs(es, venue, False)
        motor = prior.ticket_probs(es, venue, True)
        if actual not in base:
            coverage["skipped"] += 1
            continue

        block = block_for(rd)
        if block is not None:
            mat = maturity_for(min_prior)
            prior.add_stat(by_block[block], base, motor, actual, min_prior, mean_prior)
            prior.add_stat(by_venue_block[(venue, block)], base, motor, actual, min_prior, mean_prior)
            prior.add_stat(by_maturity_block[(mat, block)], base, motor, actual, min_prior, mean_prior)
            coverage["evaluated"] += 1

        # Strictly prior: update after evaluation, including pre-analysis dates so
        # maturity entering B1 is based on already observed generation history.
        for e in es:
            counts[(venue, str(prior.si(e.get("motor_no"))))] += 1

    print(
        f"MOTOR_TEMPORAL_COVERAGE=evaluated:{coverage['evaluated']} skipped:{coverage['skipped']} pre_start:{coverage['pre_start']} venues:{len(venues)}",
        flush=True,
    )
    print("MOTOR_TEMPORAL_SECTION=BLOCK", flush=True)
    block_sign_ll = block_sign_br = 0
    for label, _, _ in BLOCKS:
        s = by_block[label]
        prior.emit(f"TEMP_BLOCK:{label}", s)
        block_sign_ll += delta(s, "ll_m", "ll_b") < 0
        block_sign_br += delta(s, "br_m", "br_b") < 0
    print(f"MOTOR_TEMPORAL_BLOCK_SIGN=logloss_improve:{block_sign_ll}/3 brier_improve:{block_sign_br}/3", flush=True)

    print("MOTOR_TEMPORAL_SECTION=VENUE_SIGN", flush=True)
    for venue in venues:
        ll_sign = br_sign = 0
        parts = []
        for label, _, _ in BLOCKS:
            s = by_venue_block[(venue, label)]
            dll = delta(s, "ll_m", "ll_b")
            dbr = delta(s, "br_m", "br_b")
            if s["n"]:
                ll_sign += dll < 0
                br_sign += dbr < 0
            parts.append(f"{label}:n{int(s['n'])},ll{dll:+.6f},br{dbr:+.7f}")
        print(f"MOTOR_TEMPORAL_VENUE={venue} ll_improve:{ll_sign}/3 br_improve:{br_sign}/3 " + " ".join(parts), flush=True)

    print("MOTOR_TEMPORAL_SECTION=MATURITY_X_BLOCK", flush=True)
    for mat, _, _ in MATURITY:
        ll_sign = br_sign = 0
        parts = []
        for label, _, _ in BLOCKS:
            s = by_maturity_block[(mat, label)]
            dll = delta(s, "ll_m", "ll_b")
            dbr = delta(s, "br_m", "br_b")
            if s["n"]:
                ll_sign += dll < 0
                br_sign += dbr < 0
            parts.append(f"{label}:n{int(s['n'])},ll{dll:+.6f},br{dbr:+.7f}")
        print(f"MOTOR_TEMPORAL_MAT={mat} ll_improve:{ll_sign}/3 br_improve:{br_sign}/3 " + " ".join(parts), flush=True)

    print("MOTOR_TEMPORAL_INTERPRETATION=TEMPORAL_STABILITY_DIAGNOSTIC_ONLY_REQUIRE_FORWARD_BEFORE_MODEL_USE", flush=True)
    print("MOTOR_TEMPORAL_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_TEMPORAL_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
