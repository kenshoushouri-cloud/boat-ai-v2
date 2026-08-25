# -*- coding: utf-8 -*-
"""Read-only temporal-safety audit for frozen GUARD05.

PR #226 generated one exploratory candidate:
  if a lane's motor has <=5 strictly-prior appearances in the verified current
  generation, use motor2=33.0 for that lane; otherwise use the race-card actual
  motor_place2_rate.

Before any Forward collection, this audit checks that the candidate survives
counts that are fully knowable without race outcomes.  The threshold is NOT
searched or changed.

Two fixed temporal-safe count definitions are compared:
- CARD_ORDER: count complete/valid race-card appearances earlier in chronological
  race order, regardless of whether a result exists. Same-day earlier scheduled
  cards can count because their existence is already known before the target race.
- PRIOR_DAY: count only complete/valid race-card appearances from earlier dates;
  all races on the same date use the start-of-day count.

BASE and FULL use the existing v24 formula. Results are used only as labels after
probabilities are formed; they are never used to determine maturity counts.
Historical evidence is reused and remains candidate-generation only.
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

VERSION = "2026-08-25 motor-guard05-preknown-count-v1"
END_DATE = date.fromisoformat(os.getenv("MOTOR_PREKNOWN_END_DATE", "2026-08-15"))
GUARD_MAX_PRIOR = 5
MODELS = ("BASE", "FULL", "CARD_ORDER", "PRIOR_DAY")


def stat() -> Dict[str, float]:
    return sh.new_stat()


def card_valid(es: List[Dict[str, Any]]) -> bool:
    return (
        len(es) == 6
        and len({prior.si(e.get("lane")) for e in es}) == 6
        and all(prior.si(e.get("motor_no"), 0) > 0 for e in es)
        and all(0.0 <= prior.sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es)
    )


def guard_probs(entries: List[Dict[str, Any]], venue: str, counts_by_lane: Dict[int, int]):
    guarded = copy.deepcopy(entries)
    for e in guarded:
        lane = prior.si(e.get("lane"))
        if counts_by_lane.get(lane, 0) <= GUARD_MAX_PRIOR:
            e["motor_place2_rate"] = 33.0
    return sh.ticket_probs(guarded, venue, counts_by_lane, None)


def avg(s: Dict[str, float], key: str) -> float:
    return sh.mean(s, key)


def emit(scope: str, model: str, s: Dict[str, float], base: Dict[str, float], full: Dict[str, float]) -> None:
    n = int(s["n"])
    if not n:
        print(f"MOTOR_PREKNOWN_SCOPE={scope} model:{model} n:0", flush=True)
        return
    ll, br, rk = avg(s, "ll"), avg(s, "br"), avg(s, "rk")
    print(
        f"MOTOR_PREKNOWN_SCOPE={scope} model:{model} n:{n} "
        f"ll:{ll:.8f} brier:{br:.8f} rank:{rk:.4f} "
        f"delta_ll_vs_base:{ll-avg(base,'ll'):+.8f} "
        f"delta_brier_vs_base:{br-avg(base,'br'):+.8f} "
        f"delta_rank_vs_base:{rk-avg(base,'rk'):+.4f} "
        f"delta_ll_vs_full:{ll-avg(full,'ll'):+.8f} "
        f"delta_brier_vs_full:{br-avg(full,'br'):+.8f} "
        f"delta_rank_vs_full:{rk-avg(full,'rk'):+.4f}",
        flush=True,
    )


def add_all(target: Dict[str, Dict[str, float]], probs: Dict[str, Dict[str, float]], actual: str,
            card_min: int, card_mean: float, day_min: int, day_mean: float) -> None:
    sh.add_stat(target["BASE"], probs["BASE"], actual, card_min, card_mean)
    sh.add_stat(target["FULL"], probs["FULL"], actual, card_min, card_mean)
    sh.add_stat(target["CARD_ORDER"], probs["CARD_ORDER"], actual, card_min, card_mean)
    sh.add_stat(target["PRIOR_DAY"], probs["PRIOR_DAY"], actual, day_min, day_mean)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")

    venues = sorted(prior.MOTOR_GENERATION_START)
    start_all = min(prior.MOTOR_GENERATION_START.values())
    analysis_start = sh.BLOCKS[0][1]

    print(f"MOTOR_PREKNOWN_VERSION={VERSION}", flush=True)
    print("MOTOR_PREKNOWN_MODE=read_only_frozen_guard05_no_threshold_search", flush=True)
    print("MOTOR_PREKNOWN_POLICY=official_generation_subset_counts_from_race_cards_only_results_labels_only_db_first_seen_forbidden_no_writes_no_production_no_line", flush=True)
    print("MOTOR_PREKNOWN_RULE=guard05_lane_prior_le_5_use33_else_actual_motor2", flush=True)
    print("MOTOR_PREKNOWN_COUNT_MODES=CARD_ORDER,PRIOR_DAY", flush=True)
    print("MOTOR_PREKNOWN_BLOCKS=" + ",".join(x[0] for x in sh.BLOCKS), flush=True)
    print(f"MOTOR_PREKNOWN_PERIOD={analysis_start}..{END_DATE} prior_count_start:{start_all}", flush=True)
    print("MOTOR_PREKNOWN_VENUES=" + ",".join(venues), flush=True)

    races = fetch_all(
        """
        select race_id,race_date::date race_date,race_no::int race_no,
               lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
          from v2_races
         where race_date between %s and %s
           and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0')=any(%s)
         order by race_date,venue,race_no,race_id
        """,
        (start_all, END_DATE, venues),
    )
    entries = fetch_all(
        """
        select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
               e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
          from v2_race_entries e
          join v2_races r on r.race_id=e.race_id
         where r.race_date between %s and %s
           and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
         order by r.race_date,coalesce(r.venue_id,r.venue_code),r.race_no,e.lane
        """,
        (start_all, END_DATE, venues),
    )
    results = fetch_all(
        """
        select res.race_id,res.trifecta_ticket
          from v2_results res
          join v2_races r on r.race_id=res.race_id
         where r.race_date between %s and %s
           and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
           and coalesce(res.result_status,'')='official'
           and coalesce(res.race_status,'')='official'
        """,
        (start_all, END_DATE, venues),
    )

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}

    card_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    day_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    pending_day: Dict[Tuple[str, str], int] = defaultdict(int)
    active_date: date | None = None

    overall = {m: stat() for m in MODELS}
    by_block = defaultdict(lambda: {m: stat() for m in MODELS})
    affected_card = {m: stat() for m in MODELS}
    affected_day = {m: stat() for m in MODELS}
    affected_card_block = defaultdict(lambda: {m: stat() for m in MODELS})
    affected_day_block = defaultdict(lambda: {m: stat() for m in MODELS})
    by_venue = defaultdict(lambda: {m: stat() for m in MODELS})
    coverage = defaultdict(int)

    for r0 in races:
        r = dict(r0)
        rid = str(r["race_id"])
        venue = str(r["venue"])
        rd = r["race_date"]

        if active_date is None:
            active_date = rd
        elif rd != active_date:
            for key, n in pending_day.items():
                day_counts[key] += n
            pending_day.clear()
            active_date = rd

        if rd < prior.MOTOR_GENERATION_START[venue]:
            coverage["pre_start"] += 1
            continue

        es = sorted(eb.get(rid, []), key=lambda x: prior.si(x.get("lane")))
        valid_card = card_valid(es)
        if not valid_card:
            coverage["invalid_card"] += 1
            continue

        card_by_lane = {
            prior.si(e["lane"]): card_counts[(venue, str(prior.si(e.get("motor_no"))))]
            for e in es
        }
        day_by_lane = {
            prior.si(e["lane"]): day_counts[(venue, str(prior.si(e.get("motor_no"))))]
            for e in es
        }
        card_min = min(card_by_lane.values())
        card_mean = sum(card_by_lane.values()) / 6.0
        day_min = min(day_by_lane.values())
        day_mean = sum(day_by_lane.values()) / 6.0

        block = sh.block_for(rd)
        actual = rb.get(rid, "")
        if block is not None and actual:
            probs = {
                "BASE": sh.ticket_probs(es, venue, card_by_lane, -1),
                "FULL": sh.ticket_probs(es, venue, card_by_lane, None),
                "CARD_ORDER": guard_probs(es, venue, card_by_lane),
                "PRIOR_DAY": guard_probs(es, venue, day_by_lane),
            }
            if actual in probs["BASE"]:
                add_all(overall, probs, actual, card_min, card_mean, day_min, day_mean)
                add_all(by_block[block], probs, actual, card_min, card_mean, day_min, day_mean)
                add_all(by_venue[venue], probs, actual, card_min, card_mean, day_min, day_mean)
                if card_min <= GUARD_MAX_PRIOR:
                    add_all(affected_card, probs, actual, card_min, card_mean, day_min, day_mean)
                    add_all(affected_card_block[block], probs, actual, card_min, card_mean, day_min, day_mean)
                    coverage["affected_card"] += 1
                if day_min <= GUARD_MAX_PRIOR:
                    add_all(affected_day, probs, actual, card_min, card_mean, day_min, day_mean)
                    add_all(affected_day_block[block], probs, actual, card_min, card_mean, day_min, day_mean)
                    coverage["affected_day"] += 1
                coverage["evaluated"] += 1
            else:
                coverage["bad_ticket"] += 1
        elif block is not None:
            coverage["missing_result"] += 1

        # These maturity counters depend only on the race card, never its result.
        for e in es:
            key = (venue, str(prior.si(e.get("motor_no"))))
            card_counts[key] += 1
            pending_day[key] += 1

    print(
        f"MOTOR_PREKNOWN_COVERAGE=evaluated:{coverage['evaluated']} invalid_card:{coverage['invalid_card']} "
        f"missing_result:{coverage['missing_result']} bad_ticket:{coverage['bad_ticket']} pre_start:{coverage['pre_start']} "
        f"affected_card:{coverage['affected_card']} affected_day:{coverage['affected_day']}",
        flush=True,
    )

    print("MOTOR_PREKNOWN_SECTION=OVERALL", flush=True)
    for model in MODELS:
        emit("OVERALL", model, overall[model], overall["BASE"], overall["FULL"])

    print("MOTOR_PREKNOWN_SECTION=BLOCK", flush=True)
    for block, _, _ in sh.BLOCKS:
        for model in MODELS:
            emit(f"BLOCK:{block}", model, by_block[block][model], by_block[block]["BASE"], by_block[block]["FULL"])

    print("MOTOR_PREKNOWN_SECTION=AFFECTED_CARD_ORDER", flush=True)
    for model in MODELS:
        emit("AFFECTED_CARD_ORDER", model, affected_card[model], affected_card["BASE"], affected_card["FULL"])

    print("MOTOR_PREKNOWN_SECTION=AFFECTED_PRIOR_DAY", flush=True)
    for model in MODELS:
        emit("AFFECTED_PRIOR_DAY", model, affected_day[model], affected_day["BASE"], affected_day["FULL"])

    print("MOTOR_PREKNOWN_SECTION=BLOCK_SIGN", flush=True)
    for model in ("CARD_ORDER", "PRIOR_DAY"):
        all_vs_base = {"ll": 0, "br": 0, "rk": 0}
        all_vs_full = {"ll": 0, "br": 0, "rk": 0}
        affected_vs_base = {"ll": 0, "br": 0, "rk": 0}
        affected_vs_full = {"ll": 0, "br": 0, "rk": 0}
        available_all = 0
        available_aff = 0
        for block, _, _ in sh.BLOCKS:
            s = by_block[block][model]; b = by_block[block]["BASE"]; f = by_block[block]["FULL"]
            if s["n"]:
                available_all += 1
                all_vs_base["ll"] += avg(s,"ll") < avg(b,"ll")
                all_vs_base["br"] += avg(s,"br") < avg(b,"br")
                all_vs_base["rk"] += avg(s,"rk") < avg(b,"rk")
                all_vs_full["ll"] += avg(s,"ll") < avg(f,"ll")
                all_vs_full["br"] += avg(s,"br") < avg(f,"br")
                all_vs_full["rk"] += avg(s,"rk") < avg(f,"rk")
            source = affected_card_block if model == "CARD_ORDER" else affected_day_block
            sa = source[block][model]; ba = source[block]["BASE"]; fa = source[block]["FULL"]
            if sa["n"]:
                available_aff += 1
                affected_vs_base["ll"] += avg(sa,"ll") < avg(ba,"ll")
                affected_vs_base["br"] += avg(sa,"br") < avg(ba,"br")
                affected_vs_base["rk"] += avg(sa,"rk") < avg(ba,"rk")
                affected_vs_full["ll"] += avg(sa,"ll") < avg(fa,"ll")
                affected_vs_full["br"] += avg(sa,"br") < avg(fa,"br")
                affected_vs_full["rk"] += avg(sa,"rk") < avg(fa,"rk")
        print(
            f"MOTOR_PREKNOWN_SIGN=model:{model} all_blocks:{available_all} "
            f"all_vs_base_ll:{all_vs_base['ll']}/{available_all} all_vs_base_brier:{all_vs_base['br']}/{available_all} all_vs_base_rank:{all_vs_base['rk']}/{available_all} "
            f"all_vs_full_ll:{all_vs_full['ll']}/{available_all} all_vs_full_brier:{all_vs_full['br']}/{available_all} all_vs_full_rank:{all_vs_full['rk']}/{available_all} "
            f"affected_blocks:{available_aff} affected_vs_base_ll:{affected_vs_base['ll']}/{available_aff} affected_vs_base_brier:{affected_vs_base['br']}/{available_aff} affected_vs_base_rank:{affected_vs_base['rk']}/{available_aff} "
            f"affected_vs_full_ll:{affected_vs_full['ll']}/{available_aff} affected_vs_full_brier:{affected_vs_full['br']}/{available_aff} affected_vs_full_rank:{affected_vs_full['rk']}/{available_aff}",
            flush=True,
        )

    print("MOTOR_PREKNOWN_SECTION=VENUE", flush=True)
    for venue in venues:
        for model in MODELS:
            emit(f"VENUE:{venue}", model, by_venue[venue][model], by_venue[venue]["BASE"], by_venue[venue]["FULL"])

    print("MOTOR_PREKNOWN_INTERPRETATION=TEMPORAL_SAFETY_SCREEN_REUSED_HISTORICAL_EVIDENCE_ONLY_FORWARD_STILL_REQUIRED", flush=True)
    print("MOTOR_PREKNOWN_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE_NO_FORWARD_WRITE_YET", flush=True)
    print("MOTOR_PREKNOWN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
