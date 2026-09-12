# -*- coding: utf-8 -*-
"""Candidate Discovery V2 formation audit (READ ONLY).

V1 proved that selecting one top-probability ticket from a fixed number of races
creates enough candidates but does not create acceptable economics. V2 keeps the
odds/EV-independent discovery principle and changes the unit of prediction:

- select *races* by structural predictability;
- attach a small fixed formation (top K exact-order tickets) to each selected race;
- compare fixed race counts and formation sizes without outcome-driven retuning.

Race discovery signals (all predeclared, equal-weight percentile consensus):
- strongest first-place lane probability;
- first-place lane probability margin over runner-up lane;
- probability mass of the top three exact-order tickets;
- distribution concentration (1 - normalized entropy).

Probability variants:
- BASE: v24-style race-card model with neutral Motor2 input.
- MOTOR2_FACTOR: BASE probabilities multiplied by the independently frozen
  exp(0.06 * [1.0*z(first)+0.6*z(second)+0.3*z(third)]) factor and renormalized.

No odds table is read. No expected value or odds band is used for candidate
selection. Results/payouts are joined only after selections are frozen in memory.
No DB write / LINE / BUY / Production change.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
V1_PATH = HERE / "candidate_discovery_v1_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", V1_PATH)
v1 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(v1)

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_DISCOVERY_V2_START", "2025-07-01").strip()
END_DATE = os.getenv(
    "CANDIDATE_DISCOVERY_V2_END",
    (datetime.now(JST).date() - timedelta(days=1)).isoformat(),
).strip()
OUTPUT = Path(os.getenv("CANDIDATE_DISCOVERY_V2_OUTPUT", "candidate-discovery-v2-formation.json"))
UNIT_YEN = max(1, int(os.getenv("CANDIDATE_DISCOVERY_V2_UNIT_YEN", "100")))
RACE_CAPS = tuple(sorted({int(x) for x in os.getenv("CANDIDATE_DISCOVERY_V2_RACE_CAPS", "3,6,9,12").split(",") if x.strip()}))
FORMATION_SIZES = tuple(sorted({int(x) for x in os.getenv("CANDIDATE_DISCOVERY_V2_FORMATIONS", "1,2,3,5").split(",") if x.strip()}))
PRIMARY_RACE_CAP = 6
PRIMARY_FORMATION = 3
MOTOR_BETA = 0.06
POS_W = (1.0, 0.6, 0.3)
ALL_LANES = {1, 2, 3, 4, 5, 6}

if PRIMARY_RACE_CAP not in RACE_CAPS or PRIMARY_FORMATION not in FORMATION_SIZES:
    raise RuntimeError("V2 fixed primary view must be present in configured grids")


def motor_z(entries: list[dict[str, Any]]) -> dict[int, float] | None:
    by = {v1.si(row.get("lane"), 0): row for row in entries}
    if set(by) != ALL_LANES:
        return None
    vals: dict[int, float] = {}
    for lane in range(1, 7):
        value = v1.valid_motor2(by[lane].get("motor_place2_rate"))
        if value is None:
            return None
        vals[lane] = float(value)
    mu = sum(vals.values()) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals.values()) / 6.0)
    if sd < 1e-12:
        return None
    return {lane: (value - mu) / sd for lane, value in vals.items()}


def motor_adjust(base_probs: dict[str, float], entries: list[dict[str, Any]]) -> dict[str, float]:
    z = motor_z(entries)
    if z is None:
        return dict(base_probs)
    weighted: dict[str, float] = {}
    for ticket, prob in base_probs.items():
        a, b, c = (int(x) for x in ticket.split("-"))
        score = POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]
        weighted[ticket] = prob * math.exp(MOTOR_BETA * score)
    total = sum(weighted.values())
    if total <= 0:
        return dict(base_probs)
    return {ticket: value / total for ticket, value in weighted.items()}


def probability_metrics(
    race: dict[str, Any],
    probs: dict[str, float],
    variant: str,
) -> dict[str, Any]:
    ranked_tickets = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))
    first_lane: dict[int, float] = defaultdict(float)
    for ticket, prob in probs.items():
        first_lane[int(ticket.split("-", 1)[0])] += prob
    ranked_heads = sorted(first_lane.items(), key=lambda kv: (-kv[1], kv[0]))
    head_p1 = ranked_heads[0][1]
    head_margin = ranked_heads[0][1] - ranked_heads[1][1]
    top3_mass = sum(prob for _, prob in ranked_tickets[:3])
    entropy = -sum(p * math.log(p) for p in probs.values()) / math.log(len(probs))
    return {
        "race_id": str(race.get("race_id") or ""),
        "race_date": str(race.get("race_date") or "")[:10],
        "venue_id": str(race.get("venue_id") or race.get("venue_code") or "").zfill(2),
        "race_no": v1.si(race.get("race_no"), 0),
        "variant": variant,
        "head_lane": ranked_heads[0][0],
        "head_p1": float(head_p1),
        "head_margin": float(head_margin),
        "top3_mass": float(top3_mass),
        "concentration": float(1.0 - entropy),
        "ranked_tickets": [ticket for ticket, _ in ranked_tickets],
        "ranked_probs": [float(prob) for _, prob in ranked_tickets],
    }


def percentile_rank(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    ordered = sorted(rows, key=lambda row: (-float(row[key]), str(row["race_id"])))
    if len(ordered) <= 1:
        return {str(row["race_id"]): 1.0 for row in ordered}
    return {
        str(row["race_id"]): 1.0 - idx / (len(ordered) - 1)
        for idx, row in enumerate(ordered)
    }


def rank_day(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    ranks = {
        key: percentile_rank(rows, key)
        for key in ("head_p1", "head_margin", "top3_mass", "concentration")
    }
    out = []
    for row in rows:
        race_id = str(row["race_id"])
        item = dict(row)
        item["race_score"] = sum(ranks[key][race_id] for key in ranks) / len(ranks)
        out.append(item)
    out.sort(
        key=lambda row: (
            -float(row["race_score"]),
            -float(row["head_p1"]),
            -float(row["top3_mass"]),
            str(row["race_id"]),
        )
    )
    for idx, row in enumerate(out, 1):
        row["daily_race_rank"] = idx
    return out


def evaluate_race_formations(
    selected_races: list[dict[str, Any]],
    formation_size: int,
    results: dict[str, tuple[str, int]],
) -> dict[str, Any]:
    selected = len(selected_races)
    evaluated_races = hits = pending = 0
    investment = returns = 0
    losing_races = max_losing_races = 0
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(
        selected_races,
        key=lambda x: (x["race_date"], x["venue_id"], x["race_no"], x["race_id"]),
    ):
        result = results.get(str(row["race_id"]))
        if result is None:
            pending += 1
            continue
        win_ticket, payout = result
        tickets = row["ranked_tickets"][:formation_size]
        hit = win_ticket in tickets
        evaluated_races += 1
        investment += UNIT_YEN * formation_size
        if hit:
            hits += 1
            returns += payout
            losing_races = 0
        else:
            losing_races += 1
            max_losing_races = max(max_losing_races, losing_races)
        by_month[str(row["race_date"])[:7]].append(
            {"hit": hit, "payout": payout if hit else 0}
        )

    monthly = {}
    for month, rows in sorted(by_month.items()):
        inv = len(rows) * UNIT_YEN * formation_size
        ret = sum(int(x["payout"]) for x in rows)
        mh = sum(1 for x in rows if x["hit"])
        monthly[month] = {
            "evaluated_races": len(rows),
            "hits": mh,
            "hit_rate_pct": round(mh / len(rows) * 100.0, 3) if rows else None,
            "investment_yen": inv,
            "return_yen": ret,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 3) if inv else None,
        }

    return {
        "selected_races": selected,
        "evaluated_races": evaluated_races,
        "pending_races": pending,
        "formation_size": formation_size,
        "bet_points": evaluated_races * formation_size,
        "hits": hits,
        "race_hit_rate_pct": round(hits / evaluated_races * 100.0, 3) if evaluated_races else None,
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": round(returns / investment * 100.0, 3) if investment else None,
        "max_losing_race_streak": max_losing_races,
        "monthly": monthly,
    }


def load_data(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (START_DATE, END_DATE),
        )
        races = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select e.race_id,e.lane,e.racer_class,e.national_win_rate,
                   e.national_place2_rate,e.local_place2_rate,e.avg_st,
                   e.motor_place2_rate
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date between %s and %s
             order by e.race_id,e.lane
            """,
            (START_DATE, END_DATE),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))
        cur.execute(
            """
            select r.race_id,r.trifecta_ticket,r.trifecta_payout_yen
              from v2_results r
              join v2_races rr on rr.race_id=r.race_id
             where rr.race_date between %s and %s
               and r.result_status='official' and r.race_status='official'
               and r.trifecta_ticket is not null and r.trifecta_payout_yen > 0
             order by r.race_id
            """,
            (START_DATE, END_DATE),
        )
        results = {}
        for row in cur.fetchall():
            ticket = v1.norm_ticket(row["trifecta_ticket"])
            payout = v1.si(row["trifecta_payout_yen"], 0)
            if ticket and payout > 0:
                results[str(row["race_id"])] = (ticket, payout)
    return races, entries_by, results


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("CANDIDATE_DISCOVERY_V2_MODE=race_first_small_formation", flush=True)
    print(f"CANDIDATE_DISCOVERY_V2_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CANDIDATE_DISCOVERY_V2_SELECTION=head_p1,head_margin,top3_mass,concentration equal_weight_percentiles", flush=True)
    print(f"CANDIDATE_DISCOVERY_V2_RACE_CAPS={','.join(map(str,RACE_CAPS))} FORMATIONS={','.join(map(str,FORMATION_SIZES))}", flush=True)
    print(f"CANDIDATE_DISCOVERY_V2_PRIMARY=races:{PRIMARY_RACE_CAP} formation:{PRIMARY_FORMATION}", flush=True)
    print("CANDIDATE_DISCOVERY_V2_ODDS_READ=0 EV_FILTER=0 ODDS_FILTER=0", flush=True)
    print("CANDIDATE_DISCOVERY_V2_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, entries_by, results = load_data(conn)
        conn.rollback()

    by_variant_day: dict[str, dict[str, list[dict[str, Any]]]] = {
        "BASE": defaultdict(list),
        "MOTOR2_FACTOR": defaultdict(list),
    }
    audit = {"races_total": len(races), "evaluable_races": 0, "motor_complete_races": 0, "results_official": len(results)}
    for race in races:
        race_id = str(race.get("race_id") or "")
        entries = entries_by.get(race_id, [])
        if len(entries) != 6 or {v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES:
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base_probs = v1.ticket_probabilities(entries, venue, 0.0)
        m2_probs = motor_adjust(base_probs, entries)
        if motor_z(entries) is not None:
            audit["motor_complete_races"] += 1
        ds = str(race.get("race_date") or "")[:10]
        by_variant_day["BASE"][ds].append(probability_metrics(race, base_probs, "BASE"))
        by_variant_day["MOTOR2_FACTOR"][ds].append(probability_metrics(race, m2_probs, "MOTOR2_FACTOR"))
        audit["evaluable_races"] += 1

    reports: dict[str, Any] = {}
    for variant, by_day in by_variant_day.items():
        ranked_days = {ds: rank_day(rows) for ds, rows in sorted(by_day.items())}
        views: dict[str, Any] = {}
        for race_cap in RACE_CAPS:
            selected = []
            daily_counts = []
            for ds, rows in ranked_days.items():
                take = rows[: min(race_cap, len(rows))]
                selected.extend(take)
                daily_counts.append(len(take))
            for formation in FORMATION_SIZES:
                ev = evaluate_race_formations(selected, formation, results)
                key = f"R{race_cap}_K{formation}"
                views[key] = {
                    "mean_races_per_day": round(mean(daily_counts), 3) if daily_counts else 0.0,
                    "median_races_per_day": float(median(daily_counts)) if daily_counts else 0.0,
                    "evaluation": ev,
                }
                print(
                    f"CANDIDATE_DISCOVERY_V2_VIEW={variant}/{key} "
                    f"races:{ev['evaluated_races']} hits:{ev['hits']} "
                    f"hit_rate:{ev['race_hit_rate_pct']} roi:{ev['roi_pct']} "
                    f"bet_points:{ev['bet_points']} max_lose:{ev['max_losing_race_streak']}",
                    flush=True,
                )
        reports[variant] = {"views": views}

    out = {
        "contract": "candidate_discovery_v2_race_first_small_formation",
        "period": {"start": START_DATE, "end": END_DATE},
        "selection": {
            "uses_odds": False,
            "uses_expected_value": False,
            "race_signals": ["head_p1", "head_margin", "top3_ticket_mass", "distribution_concentration"],
            "race_signal_weighting": "equal_weight_within_day_percentile_consensus",
            "race_caps": list(RACE_CAPS),
            "formation_sizes": list(FORMATION_SIZES),
            "primary": {"race_cap": PRIMARY_RACE_CAP, "formation_size": PRIMARY_FORMATION},
        },
        "variants": {
            "BASE": {"motor2_factor": False},
            "MOTOR2_FACTOR": {"beta": MOTOR_BETA, "position_weights": list(POS_W), "fallback": "BASE when incomplete"},
        },
        "audit": audit,
        "reports": reports,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANDIDATE_DISCOVERY_V2_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    print("CANDIDATE_DISCOVERY_V2_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_DISCOVERY_V2_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_DISCOVERY_V2_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
