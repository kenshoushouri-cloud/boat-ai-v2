# -*- coding: utf-8 -*-
"""Read-only venue x date decomposition of the frozen Aug16-24 motor holdout.

This is a diagnostic follow-up to PR #220 after venue heterogeneity was observed.
It does not select/exclude any venue or date and does not tune a threshold or
coefficient. It uses the same verified official-generation five-venue subset,
current v24 formula, BASE motor2=33 and race-card ALL_ACTUAL motor2 comparison.

No DB writes, Production/LINE changes, Railway settings, or promotion decision.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List

from db_pg import fetch_all
import backtest_prob_motor_prior_appearance_maturity_pg as prior

VERSION = "2026-08-25 motor-holdout-venue-date-diagnostic-v1"
START = date(2026, 8, 16)
END = date(2026, 8, 24)
EPS = 1e-15


def new_stat() -> Dict[str, float]:
    return {
        "n": 0.0,
        "ll_base": 0.0,
        "ll_actual": 0.0,
        "br_base": 0.0,
        "br_actual": 0.0,
        "rk_base": 0.0,
        "rk_actual": 0.0,
    }


def add_stat(s: Dict[str, float], base: Dict[str, float], actual_probs: Dict[str, float], ticket: str) -> None:
    s["n"] += 1
    for label, probs in (("base", base), ("actual", actual_probs)):
        p = max(probs.get(ticket, 0.0), EPS)
        s[f"ll_{label}"] += -math.log(p)
        s[f"rk_{label}"] += prior.rank_of(probs, ticket)
        s[f"br_{label}"] += sum(
            (prob - (1.0 if t == ticket else 0.0)) ** 2
            for t, prob in probs.items()
        )


def metrics(s: Dict[str, float]) -> Dict[str, float]:
    n = int(s["n"])
    if not n:
        return {"n": 0.0, "ll": 0.0, "br": 0.0, "rk": 0.0}
    return {
        "n": float(n),
        "ll": (s["ll_actual"] - s["ll_base"]) / n,
        "br": (s["br_actual"] - s["br_base"]) / n,
        "rk": (s["rk_actual"] - s["rk_base"]) / n,
    }


def emit(prefix: str, s: Dict[str, float]) -> None:
    m = metrics(s)
    print(
        f"{prefix}=n:{int(m['n'])} all_vs_base_ll:{m['ll']:+.8f} "
        f"all_vs_base_brier:{m['br']:+.8f} all_vs_base_rank:{m['rk']:+.4f}",
        flush=True,
    )


def main() -> None:
    print(f"MOTOR_VD_MODE=read_only_fixed_holdout_decomposition_no_selection version:{VERSION}", flush=True)
    print("MOTOR_VD_PERIOD=2026-08-16..2026-08-24", flush=True)
    print("MOTOR_VD_MODELS=BASE_fixed33_vs_ALL_ACTUAL_race_card_motor2", flush=True)
    print("MOTOR_VD_POLICY=verified_generation_subset_db_first_seen_forbidden_no_venue_or_date_selection_no_tuning_no_writes_no_production_no_line", flush=True)

    venues = sorted(prior.MOTOR_GENERATION_START)
    races = fetch_all(
        """select race_id,race_date::date race_date,race_no::int race_no,
                  lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') venue
             from v2_races
            where race_date between %s and %s
              and lpad(coalesce(nullif(venue_id::text,''),nullif(venue_code::text,'')),2,'0') = any(%s)
            order by race_date,venue,race_no,race_id""",
        (START, END, venues),
    )
    entries = fetch_all(
        """select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                  e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
             from v2_race_entries e join v2_races r on r.race_id=e.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
            order by r.race_date,r.venue_id,r.race_no,e.lane""",
        (START, END, venues),
    )
    results = fetch_all(
        """select res.race_id,res.trifecta_ticket
             from v2_results res join v2_races r on r.race_id=res.race_id
            where r.race_date between %s and %s
              and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') = any(%s)
              and coalesce(res.result_status,'')='official'""",
        (START, END, venues),
    )

    eb: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in entries:
        eb[str(e["race_id"])].append(dict(e))
    rb = {str(x["race_id"]): prior.norm_ticket(x.get("trifecta_ticket")) for x in results}

    overall = new_stat()
    by_venue: Dict[str, Dict[str, float]] = defaultdict(new_stat)
    by_date: Dict[date, Dict[str, float]] = defaultdict(new_stat)
    by_cell: Dict[tuple[str, date], Dict[str, float]] = defaultdict(new_stat)
    skipped = pre_start = 0

    for r0 in races:
        r = dict(r0)
        rid = str(r["race_id"])
        venue = str(r["venue"])
        rd = r["race_date"]
        if rd < prior.MOTOR_GENERATION_START[venue]:
            pre_start += 1
            continue
        es = sorted(eb.get(rid, []), key=lambda x: prior.si(x.get("lane")))
        ticket = rb.get(rid, "")
        valid = (
            len(es) == 6
            and len({prior.si(e.get("lane")) for e in es}) == 6
            and bool(ticket)
            and all(prior.si(e.get("motor_no"), 0) > 0 for e in es)
            and all(0.0 <= prior.sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es)
        )
        if not valid:
            skipped += 1
            continue
        base = prior.ticket_probs(es, venue, False)
        actual_probs = prior.ticket_probs(es, venue, True)
        if ticket not in base or ticket not in actual_probs:
            skipped += 1
            continue
        add_stat(overall, base, actual_probs, ticket)
        add_stat(by_venue[venue], base, actual_probs, ticket)
        add_stat(by_date[rd], base, actual_probs, ticket)
        add_stat(by_cell[(venue, rd)], base, actual_probs, ticket)

    print(f"MOTOR_VD_COVERAGE=evaluated:{int(overall['n'])} skipped:{skipped} pre_start:{pre_start} venues:{len(venues)}", flush=True)
    emit("MOTOR_VD_OVERALL", overall)
    print("MOTOR_VD_SECTION=VENUE", flush=True)
    for venue in venues:
        if by_venue[venue]["n"]:
            emit(f"MOTOR_VD_VENUE={venue}", by_venue[venue])
    print("MOTOR_VD_SECTION=DATE", flush=True)
    for rd in sorted(by_date):
        emit(f"MOTOR_VD_DATE={rd.isoformat()}", by_date[rd])
    print("MOTOR_VD_SECTION=VENUE_DATE", flush=True)
    for venue in venues:
        for rd in sorted(by_date):
            s = by_cell.get((venue, rd))
            if s and s["n"]:
                emit(f"MOTOR_VD_CELL={venue}|{rd.isoformat()}", s)

    # Descriptive sign counts only. They must not be used to select venues/dates.
    cells = [metrics(s) for s in by_cell.values() if s["n"]]
    print(
        "MOTOR_VD_SIGN_COUNT="
        f"cells:{len(cells)} ll_better:{sum(m['ll'] < 0 for m in cells)} "
        f"brier_better:{sum(m['br'] < 0 for m in cells)} rank_better:{sum(m['rk'] < 0 for m in cells)}",
        flush=True,
    )
    print("MOTOR_VD_INTERPRETATION=POST_HOC_DIAGNOSTIC_ONLY_DO_NOT_SELECT_VENUE_OR_DATE_REQUIRE_NEW_FORWARD", flush=True)
    print("MOTOR_VD_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("MOTOR_VD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
