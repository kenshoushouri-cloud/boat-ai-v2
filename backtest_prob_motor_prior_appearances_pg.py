# -*- coding: utf-8 -*-
"""Read-only motor maturity diagnostic by prior individual-motor appearances.

Uses only the official-generation-start venue subset defined in
backtest_prob_motor_maturity_official_subset_pg.py.

For every race, each motor's prior appearance count is calculated strictly
from earlier race cards in the same official motor generation. The current
race is evaluated before its six motors are added to the history, avoiding
same-race leakage.

The race is grouped by the minimum prior appearance count among its six
motors. This conservative maturity measure detects a race where even one
motor has very little accumulated history, including motors introduced later
than the nominal generation start.

Fixed diagnostic only:
- BASE=fixed motor2 33.0 vs MOTOR=race-card actual motor2;
- same v24 formula / coefficients / temperature;
- no shrinkage tuning/search;
- DB read-only; no Production/LINE/Railway changes.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Tuple
import os

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
from backtest_prob_motor_maturity_official_subset_pg import (
    MOTOR_GENERATION_START,
    add_stat,
    emit,
    new_stat,
    ticket_probs,
)

VERSION = "2026-08-24 motor-prior-appearances-v1"
END_DATE = os.getenv("MOTOR_PRIOR_END_DATE", "2026-08-15")

# Fixed before looking at outcomes. `prior` means completed earlier race-card
# appearances for the least-observed motor among the current six.
PRIOR_BINS: Tuple[Tuple[str, int, int | None], ...] = (
    ("P00_04", 0, 5),
    ("P05_09", 5, 10),
    ("P10_19", 10, 20),
    ("P20_39", 20, 40),
    ("P40_PLUS", 40, None),
)


def prior_bin(n: int) -> str | None:
    for label, lo, hi in PRIOR_BINS:
        if n >= lo and (hi is None or n < hi):
            return label
    return None


def as_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def motor_key(venue: str, motor_no: Any) -> tuple[str, str] | None:
    if motor_no in (None, ""):
        return None
    try:
        m = str(int(float(motor_no)))
    except Exception:
        m = str(motor_no).strip()
    return (venue, m) if m else None


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL required")

    starts = {v: date.fromisoformat(ds) for v, (ds, _) in MOTOR_GENERATION_START.items()}
    venues = sorted(starts)
    start = min(starts.values())
    end = date.fromisoformat(END_DATE)

    print(f"MOTOR_PRIOR_VERSION={VERSION}", flush=True)
    print("MOTOR_PRIOR_MODE=read_only_no_tuning", flush=True)
    print(f"MOTOR_PRIOR_PERIOD={start}..{end}", flush=True)
    print(f"MOTOR_PRIOR_VENUES={','.join(venues)}", flush=True)
    print("MOTOR_PRIOR_POLICY=counts_only_after_verified_official_generation_start_no_same_race_leakage", flush=True)

    races = fetch_all(
        """select race_id,race_date,venue_id,venue_code
           from v2_races
           where race_date between %s and %s
             and coalesce(venue_id,venue_code)=any(%s)
           order by race_date,race_id""",
        (start.isoformat(), end.isoformat(), venues),
    )

    race_meta: Dict[str, Dict[str, Any]] = {}
    ordered_ids: List[str] = []
    for r in races:
        rid = str(r.get("race_id") or "")
        venue = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
        d = as_date(r.get("race_date"))
        if not rid or venue not in starts or d < starts[venue]:
            continue
        race_meta[rid] = {"venue": venue, "date": d}
        ordered_ids.append(rid)

    entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if ordered_ids:
        for e in fetch_all(
            """select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                      local_place2_rate,avg_st,motor_no,motor_place2_rate
               from v2_race_entries
               where race_id=any(%s)
               order by race_id,lane""",
            (ordered_ids,),
        ):
            entries_by[str(e.get("race_id") or "")].append(e)

    result_by: Dict[str, str] = {}
    if ordered_ids:
        for r in fetch_all(
            """select race_id,trifecta_ticket
               from v2_results
               where race_id=any(%s)
                 and trifecta_ticket is not null
                 and coalesce(result_status,'')='official'
                 and coalesce(race_status,'')='official'""",
            (ordered_ids,),
        ):
            t = v24._norm_ticket(r.get("trifecta_ticket"))
            if t:
                result_by[str(r.get("race_id") or "")] = t

    # Ensure true chronological ordering independent of lexical assumptions.
    ordered_ids.sort(key=lambda rid: (race_meta[rid]["date"], rid))

    prior_counts: Dict[tuple[str, str], int] = defaultdict(int)
    overall = new_stat()
    by_bin = defaultdict(new_stat)
    by_venue = defaultdict(new_stat)
    by_venue_bin = defaultdict(new_stat)
    evaluated = result_races = full6 = motor_complete = motor_no_complete = 0
    min_prior_sum = mean_prior_sum = 0.0

    for rid in ordered_ids:
        meta = race_meta[rid]
        venue = meta["venue"]
        entries = entries_by.get(rid, [])
        by = v24._entry_by_lane(entries)

        # Read prior counts BEFORE adding this race, preventing leakage.
        keys = [motor_key(venue, by[i].get("motor_no")) for i in range(1, 7)] if len(by) == 6 else []
        prior = [prior_counts[k] for k in keys] if keys and all(k is not None for k in keys) else []

        winner = result_by.get(rid)
        if winner:
            result_races += 1
            if len(by) == 6:
                full6 += 1
                if all(by[i].get("motor_place2_rate") is not None for i in range(1, 7)):
                    motor_complete += 1
                    if len(prior) == 6:
                        motor_no_complete += 1
                        min_prior = min(prior)
                        mean_prior = sum(prior) / 6.0
                        b = prior_bin(min_prior)
                        if b is not None:
                            p_base = ticket_probs(entries, venue, False)
                            p_motor = ticket_probs(entries, venue, True)
                            add_stat(overall, p_base, p_motor, winner, entries)
                            add_stat(by_bin[b], p_base, p_motor, winner, entries)
                            add_stat(by_venue[venue], p_base, p_motor, winner, entries)
                            add_stat(by_venue_bin[(venue, b)], p_base, p_motor, winner, entries)
                            evaluated += 1
                            min_prior_sum += min_prior
                            mean_prior_sum += mean_prior

        # Add current race appearances only AFTER scoring this race.
        if len(by) == 6:
            for k in keys:
                if k is not None:
                    prior_counts[k] += 1

    print(
        f"MOTOR_PRIOR_COVERAGE=races_after_start:{len(ordered_ids)} result_races:{result_races} "
        f"full6:{full6} motor_complete:{motor_complete} motor_no_complete:{motor_no_complete} evaluated:{evaluated}",
        flush=True,
    )
    if evaluated:
        print(
            f"MOTOR_PRIOR_MATURITY=avg_race_min_prior:{min_prior_sum/evaluated:.2f} "
            f"avg_lane_prior:{mean_prior_sum/evaluated:.2f}", flush=True,
        )
    emit("MOTOR_PRIOR_OVERALL", overall)
    for label, _, _ in PRIOR_BINS:
        emit(f"MOTOR_PRIOR_BIN={label}", by_bin[label])
    for venue in venues:
        emit(f"MOTOR_PRIOR_VENUE={venue}", by_venue[venue])
    for venue in venues:
        for label, _, _ in PRIOR_BINS:
            if by_venue_bin[(venue, label)]["n"]:
                emit(f"MOTOR_PRIOR_VENUE_BIN={venue}:{label}", by_venue_bin[(venue, label)])

    very_young = int(by_bin["P00_04"]["n"] + by_bin["P05_09"]["n"])
    established = int(by_bin["P20_39"]["n"] + by_bin["P40_PLUS"]["n"])
    print(f"MOTOR_PRIOR_SAMPLE_GATE=prior_lt10:{very_young} prior_20_plus:{established}", flush=True)
    print("MOTOR_PRIOR_INTERPRETATION=diagnostic_only_use_prior_appearance_evidence_before_any_shrinkage_or_production_use", flush=True)
    print("MOTOR_PRIOR_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_PRIOR_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
