# -*- coding: utf-8 -*-
"""Read-only exploratory audit for a single predeclared young-motor lane guard.

Derived from the fixed maturity finding in PR #225: races with race-level minimum
prior motor appearances P00-05 were the only slice where FULL actual motor2 was
worse than fixed33 overall.  This follow-up does NOT search thresholds.  It uses
the already-declared P00-05 boundary and tests one lane-local policy:

GUARD05: if a motor has <=5 appearances strictly before the race within its
verified official current generation, use motor2=33 for that lane; otherwise use
the race-card actual motor_place2_rate.

Compare BASE=fixed33 all lanes, FULL=actual all lanes, GUARD05. Historical screen
only; reused evidence, not independent validation. New Forward is required before
any Production consideration.
"""
from __future__ import annotations

import copy
import os
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import backtest_prob_motor_maturity_shrinkage_stability_pg as sh
import backtest_prob_motor_prior_appearance_maturity_pg as prior

VERSION = "2026-08-25 motor-young-lane-guard05-v1"
END_DATE = date.fromisoformat(os.getenv("MOTOR_GUARD_END_DATE", "2026-08-15"))
GUARD_MAX_PRIOR = 5
MODELS = ("BASE", "FULL", "GUARD05")


def stat() -> Dict[str, float]:
    return sh.new_stat()


def guard_probs(entries: List[Dict[str, Any]], venue: str, prior_by_lane: Dict[int, int]):
    guarded = copy.deepcopy(entries)
    for e in guarded:
        lane = prior.si(e.get("lane"))
        if prior_by_lane.get(lane, 0) <= GUARD_MAX_PRIOR:
            e["motor_place2_rate"] = 33.0
    return sh.ticket_probs(guarded, venue, prior_by_lane, None)


def emit(scope: str, stats: Dict[str, Dict[str, float]]) -> None:
    b, f = stats["BASE"], stats["FULL"]
    for model in MODELS:
        sh.emit(scope, model, stats[model], b, f)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")
    venues = sorted(prior.MOTOR_GENERATION_START)
    start_all = min(prior.MOTOR_GENERATION_START.values())
    print(f"MOTOR_GUARD_VERSION={VERSION}", flush=True)
    print("MOTOR_GUARD_MODE=read_only_single_predeclared_p00_05_lane_guard_no_threshold_search", flush=True)
    print("MOTOR_GUARD_POLICY=official_generation_subset_db_first_seen_forbidden_strict_prior_counts_reused_historical_screen_requires_new_forward", flush=True)
    print("MOTOR_GUARD_RULE=lane_prior_appearances_le_5_use33_else_actual_motor2", flush=True)
    print("MOTOR_GUARD_MODELS=BASE,FULL,GUARD05", flush=True)
    print("MOTOR_GUARD_BLOCKS=" + ",".join(x[0] for x in sh.BLOCKS), flush=True)
    print("MOTOR_GUARD_MATURITY=" + ",".join(x[0] for x in sh.MATURITY), flush=True)
    print("MOTOR_GUARD_VENUES=" + ",".join(venues), flush=True)

    races = fetch_all("""select race_id,race_date::date race_date,race_no::int race_no,
                  lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
             from v2_races where race_date between %s and %s
              and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0')=any(%s)
            order by race_date,race_no,race_id""", (start_all, END_DATE, venues))
    entries = fetch_all("""select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                  e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
             from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
            order by r.race_date,r.race_no,e.lane""", (start_all, END_DATE, venues))
    results = fetch_all("""select res.race_id,res.trifecta_ticket
             from v2_results res join v2_races r on r.race_id=res.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
              and coalesce(res.result_status,'')='official' and coalesce(res.race_status,'')='official'""",
        (start_all, END_DATE, venues))

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}
    counts: Dict[Tuple[str, str], int] = defaultdict(int)

    overall = {m: stat() for m in MODELS}
    by_block = defaultdict(lambda: {m: stat() for m in MODELS})
    by_mat = defaultdict(lambda: {m: stat() for m in MODELS})
    by_mat_block = defaultdict(lambda: {m: stat() for m in MODELS})
    by_venue = defaultdict(lambda: {m: stat() for m in MODELS})
    coverage = defaultdict(int)
    guarded_lane_total = 0
    guarded_races = 0

    for r0 in races:
        r = dict(r0); rid = str(r["race_id"]); venue = str(r["venue"]); rd = r["race_date"]
        if rd < prior.MOTOR_GENERATION_START[venue]:
            coverage["pre_start"] += 1
            continue
        es = sorted(eb.get(rid, []), key=lambda x: prior.si(x.get("lane")))
        actual = rb.get(rid, "")
        valid = (len(es) == 6 and len({prior.si(e.get("lane")) for e in es}) == 6 and bool(actual)
                 and all(prior.si(e.get("motor_no"), 0) > 0 for e in es)
                 and all(0.0 <= prior.sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es))
        if not valid:
            coverage["skipped"] += 1
            continue
        prior_by_lane = {prior.si(e["lane"]): counts[(venue, str(prior.si(e.get("motor_no"))))] for e in es}
        min_prior = min(prior_by_lane.values()); mean_prior = sum(prior_by_lane.values()) / 6.0
        block = sh.block_for(rd)
        if block is not None:
            probs = {
                "BASE": sh.ticket_probs(es, venue, prior_by_lane, -1),
                "FULL": sh.ticket_probs(es, venue, prior_by_lane, None),
                "GUARD05": guard_probs(es, venue, prior_by_lane),
            }
            if actual in probs["BASE"]:
                mat = sh.maturity_for(min_prior)
                guarded_lanes = sum(1 for n in prior_by_lane.values() if n <= GUARD_MAX_PRIOR)
                guarded_lane_total += guarded_lanes
                guarded_races += int(guarded_lanes > 0)
                for model in MODELS:
                    sh.add_stat(overall[model], probs[model], actual, min_prior, mean_prior)
                    sh.add_stat(by_block[block][model], probs[model], actual, min_prior, mean_prior)
                    sh.add_stat(by_mat[mat][model], probs[model], actual, min_prior, mean_prior)
                    sh.add_stat(by_mat_block[(mat, block)][model], probs[model], actual, min_prior, mean_prior)
                    sh.add_stat(by_venue[venue][model], probs[model], actual, min_prior, mean_prior)
                coverage["evaluated"] += 1
            else:
                coverage["skipped"] += 1
        for e in es:
            counts[(venue, str(prior.si(e.get("motor_no"))))] += 1

    print(f"MOTOR_GUARD_COVERAGE=evaluated:{coverage['evaluated']} skipped:{coverage['skipped']} pre_start:{coverage['pre_start']} guarded_races:{guarded_races} guarded_lanes:{guarded_lane_total}", flush=True)
    print("MOTOR_GUARD_SECTION=OVERALL", flush=True); emit("OVERALL", overall)
    print("MOTOR_GUARD_SECTION=BLOCK", flush=True)
    for block, _, _ in sh.BLOCKS:
        emit(f"BLOCK:{block}", by_block[block])
    print("MOTOR_GUARD_SECTION=MATURITY", flush=True)
    for mat, _, _ in sh.MATURITY:
        emit(f"MAT:{mat}", by_mat[mat])
    print("MOTOR_GUARD_SECTION=MATURITY_BLOCK_SIGN", flush=True)
    for mat, _, _ in sh.MATURITY:
        available = ll_base = br_base = rk_base = ll_full = br_full = rk_full = 0
        for block, _, _ in sh.BLOCKS:
            s = by_mat_block[(mat,block)]["GUARD05"]
            b = by_mat_block[(mat,block)]["BASE"]
            f = by_mat_block[(mat,block)]["FULL"]
            if not s["n"]:
                continue
            available += 1
            ll_base += sh.mean(s,"ll") < sh.mean(b,"ll"); br_base += sh.mean(s,"br") < sh.mean(b,"br"); rk_base += sh.mean(s,"rk") < sh.mean(b,"rk")
            ll_full += sh.mean(s,"ll") < sh.mean(f,"ll"); br_full += sh.mean(s,"br") < sh.mean(f,"br"); rk_full += sh.mean(s,"rk") < sh.mean(f,"rk")
        print(f"MOTOR_GUARD_MAT_SIGN=mat:{mat} blocks:{available} vs_base_ll:{ll_base}/{available} vs_base_brier:{br_base}/{available} vs_base_rank:{rk_base}/{available} vs_full_ll:{ll_full}/{available} vs_full_brier:{br_full}/{available} vs_full_rank:{rk_full}/{available}", flush=True)
    print("MOTOR_GUARD_SECTION=VENUE", flush=True)
    for venue in venues:
        emit(f"VENUE:{venue}", by_venue[venue])
    print("MOTOR_GUARD_INTERPRETATION=EXPLORATORY_REUSED_HISTORICAL_EVIDENCE_ONLY_FREEZE_CANDIDATE_IF_USEFUL_AND_REQUIRE_NEW_FORWARD", flush=True)
    print("MOTOR_GUARD_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_GUARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
