# -*- coding: utf-8 -*-
"""Independent read-only holdout for maturity-aware actual motor 2-place rate.

Holdout 2026-08-16..2026-08-24 was not used in the preceding motor maturity audits,
which ended at 2026-08-15. The maturity gate is frozen from that prior evidence:
use actual motor_place2_rate only when the race-level minimum prior appearances
across all six current-generation motors is >=21; otherwise retain fixed motor2=33.

Compares BASE, ALL_ACTUAL, and MATURE_GATE. No threshold/coefficient/venue search,
no DB writes, no Production/LINE/Railway setting changes. DB first-seen is forbidden
as an official motor generation start proxy.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import backtest_prob_motor_prior_appearance_maturity_pg as prior

VERSION = "2026-08-25 motor-maturity-holdout-aug16-24-v1"
HOLDOUT_START = date(2026, 8, 16)
HOLDOUT_END = date(2026, 8, 24)
MATURE_MIN_PRIOR = 21  # frozen from pre-holdout PR #214/#219 evidence; not searched here
EPS = 1e-15


def new_stat() -> Dict[str, float]:
    return {
        "n": 0.0,
        "ll_base": 0.0,
        "ll_all": 0.0,
        "ll_gate": 0.0,
        "br_base": 0.0,
        "br_all": 0.0,
        "br_gate": 0.0,
        "rk_base": 0.0,
        "rk_all": 0.0,
        "rk_gate": 0.0,
        "min_prior": 0.0,
        "mean_prior": 0.0,
        "gate_on": 0.0,
    }


def add_stat(
    s: Dict[str, float],
    base: Dict[str, float],
    all_actual: Dict[str, float],
    gate: Dict[str, float],
    actual: str,
    min_prior: int,
    mean_prior: float,
    gate_on: bool,
) -> None:
    models = (("base", base), ("all", all_actual), ("gate", gate))
    s["n"] += 1
    s["min_prior"] += min_prior
    s["mean_prior"] += mean_prior
    s["gate_on"] += 1 if gate_on else 0
    for label, probs in models:
        p = max(probs.get(actual, 0.0), EPS)
        s[f"ll_{label}"] += -math.log(p)
        s[f"rk_{label}"] += prior.rank_of(probs, actual)
        s[f"br_{label}"] += sum(
            (prob - (1.0 if ticket == actual else 0.0)) ** 2
            for ticket, prob in probs.items()
        )


def emit(label: str, s: Dict[str, float]) -> None:
    n = int(s["n"])
    if not n:
        print(f"MOTOR_HOLDOUT={label} n:0", flush=True)
        return
    def avg(k: str) -> float:
        return s[k] / n
    print(
        f"MOTOR_HOLDOUT={label} n:{n} gate_on:{int(s['gate_on'])}/{n} "
        f"avg_min_prior:{avg('min_prior'):.2f} avg_mean_prior:{avg('mean_prior'):.2f} "
        f"base_ll:{avg('ll_base'):.8f} all_ll:{avg('ll_all'):.8f} gate_ll:{avg('ll_gate'):.8f} "
        f"all_vs_base_ll:{avg('ll_all')-avg('ll_base'):+.8f} gate_vs_base_ll:{avg('ll_gate')-avg('ll_base'):+.8f} gate_vs_all_ll:{avg('ll_gate')-avg('ll_all'):+.8f} "
        f"all_vs_base_brier:{avg('br_all')-avg('br_base'):+.8f} gate_vs_base_brier:{avg('br_gate')-avg('br_base'):+.8f} gate_vs_all_brier:{avg('br_gate')-avg('br_all'):+.8f} "
        f"all_vs_base_rank:{avg('rk_all')-avg('rk_base'):+.4f} gate_vs_base_rank:{avg('rk_gate')-avg('rk_base'):+.4f} gate_vs_all_rank:{avg('rk_gate')-avg('rk_all'):+.4f}",
        flush=True,
    )


def main() -> None:
    print(f"MOTOR_HOLDOUT_MODE=read_only_independent_holdout_fixed_gate version:{VERSION}", flush=True)
    print("MOTOR_HOLDOUT_PERIOD=2026-08-16..2026-08-24", flush=True)
    print("MOTOR_HOLDOUT_POLICY=verified_generation_subset_db_first_seen_forbidden_gate21_frozen_no_search_no_writes_no_production_no_line", flush=True)
    print("MOTOR_HOLDOUT_MODELS=BASE_fixed33,ALL_ACTUAL,MATURE_GATE_min_prior_ge21", flush=True)

    venues = sorted(prior.MOTOR_GENERATION_START)
    start_all = min(prior.MOTOR_GENERATION_START.values())
    races = fetch_all(
        """select race_id,race_date::date race_date,race_no::int race_no,
                  lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
             from v2_races
            where race_date between %s and %s
              and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') = any(%s)
            order by race_date,race_no,race_id""",
        (start_all, HOLDOUT_END, venues),
    )
    entries = fetch_all(
        """select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                  e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
             from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
            order by r.race_date,r.race_no,e.lane""",
        (start_all, HOLDOUT_END, venues),
    )
    results = fetch_all(
        """select res.race_id,res.trifecta_ticket
             from v2_results res join v2_races r on r.race_id=res.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
              and coalesce(res.result_status,'')='official'""",
        (start_all, HOLDOUT_END, venues),
    )

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}

    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    overall = new_stat()
    by_venue: Dict[str, Dict[str, float]] = defaultdict(new_stat)
    by_maturity: Dict[str, Dict[str, float]] = defaultdict(new_stat)
    by_date: Dict[date, Dict[str, float]] = defaultdict(new_stat)
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
        all_actual = prior.ticket_probs(es, venue, True)
        if actual not in base:
            coverage["skipped"] += 1
            continue

        if rd >= HOLDOUT_START:
            gate_on = min_prior >= MATURE_MIN_PRIOR
            gate = all_actual if gate_on else base
            maturity = "MATURE_P21_PLUS" if gate_on else "YOUNG_MID_P00_20"
            add_stat(overall, base, all_actual, gate, actual, min_prior, mean_prior, gate_on)
            add_stat(by_venue[venue], base, all_actual, gate, actual, min_prior, mean_prior, gate_on)
            add_stat(by_maturity[maturity], base, all_actual, gate, actual, min_prior, mean_prior, gate_on)
            add_stat(by_date[rd], base, all_actual, gate, actual, min_prior, mean_prior, gate_on)
            coverage["evaluated"] += 1

        # Preserve the preceding audit's definition: count only valid, evaluated historical race-card appearances,
        # and update strictly after the current race so the current race never leaks into its own maturity count.
        for e in es:
            counts[(venue, str(prior.si(e.get("motor_no"))))] += 1

    print(
        f"MOTOR_HOLDOUT_COVERAGE=evaluated:{coverage['evaluated']} skipped:{coverage['skipped']} pre_start:{coverage['pre_start']} venues:{len(venues)}",
        flush=True,
    )
    emit("OVERALL", overall)
    print("MOTOR_HOLDOUT_SECTION=MATURITY", flush=True)
    emit("YOUNG_MID_P00_20", by_maturity["YOUNG_MID_P00_20"])
    emit("MATURE_P21_PLUS", by_maturity["MATURE_P21_PLUS"])
    print("MOTOR_HOLDOUT_SECTION=VENUE", flush=True)
    for venue in venues:
        emit(f"VENUE:{venue}", by_venue[venue])
    print("MOTOR_HOLDOUT_SECTION=DATE", flush=True)
    for rd in sorted(by_date):
        emit(f"DATE:{rd.isoformat()}", by_date[rd])
    print("MOTOR_HOLDOUT_INTERPRETATION=INDEPENDENT_POST_2026_08_15_HOLDOUT_NO_RETUNING_REQUIRE_FORWARD_BEFORE_PRODUCTION", flush=True)
    print("MOTOR_HOLDOUT_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_HOLDOUT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
