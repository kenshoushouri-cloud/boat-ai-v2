# -*- coding: utf-8 -*-
"""Read-only bet-type / point-count hit-rate audit for Candidate Discovery.

Purpose
-------
Compare trifecta, exacta (2-ren-tan), and trio (3-ren-puku) without changing
which races are selected or using odds/EV/payouts to select candidates.

The audit intentionally reuses the already-frozen V2 race-selection geometry as
a timing-safe historical baseline while the disconnected V4 contract remains
research-only. For every selected race it derives exacta and trio probabilities
from the same 120-ticket trifecta distribution, then evaluates the frozen grid:

- race caps per day: 3 / 6 / 9 / 12
- bet types: trifecta / exacta / trio
- fixed points: top 1 / 2 / 3 / 5
- probability coverage: 20% / 35% / 50%, max 12 tickets
- flat unit: 100 JPY per ticket (reported only as point-count context here)

This audit does NOT use payout data, odds, expected value, DB writes, LINE, BUY,
or Production changes. Official finish order is consulted only after race and
bet selections have been frozen in memory.
"""
from __future__ import annotations

import importlib.util
import json
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
REPO_ROOT = HERE.parents[1]

V2_PATH = HERE / "candidate_discovery_v2_formation_pg.py"
spec_v2 = importlib.util.spec_from_file_location("candidate_discovery_v2_formation_pg", V2_PATH)
v2 = importlib.util.module_from_spec(spec_v2)
assert spec_v2 and spec_v2.loader
spec_v2.loader.exec_module(v2)

BET_PATH = REPO_ROOT / "research" / "candidate_discovery_bettype_contract.py"
spec_bet = importlib.util.spec_from_file_location("candidate_discovery_bettype_contract", BET_PATH)
bet = importlib.util.module_from_spec(spec_bet)
assert spec_bet and spec_bet.loader
spec_bet.loader.exec_module(bet)

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_BETTYPE_START", "2025-07-01").strip()
END_DATE = os.getenv(
    "CANDIDATE_BETTYPE_END",
    (datetime.now(JST).date() - timedelta(days=1)).isoformat(),
).strip()
RACE_CAPS = tuple(
    sorted({int(x) for x in os.getenv("CANDIDATE_BETTYPE_RACE_CAPS", "3,6,9,12").split(",") if x.strip()})
)
OUTPUT = Path(os.getenv("CANDIDATE_BETTYPE_OUTPUT", "candidate-discovery-bettype-hit-audit.json"))
ALL_LANES = {1, 2, 3, 4, 5, 6}
PRIMARY_VARIANT = "MOTOR2_FACTOR"
PRIMARY_RACE_CAP = 6


def load_data(conn: psycopg.Connection[Any]):
    """Load only race card, entry features, and official winning ticket."""
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
            select r.race_id,r.trifecta_ticket
              from v2_results r
              join v2_races rr on rr.race_id=r.race_id
             where rr.race_date between %s and %s
               and r.result_status='official' and r.race_status='official'
               and r.trifecta_ticket is not null
             order by r.race_id
            """,
            (START_DATE, END_DATE),
        )
        results: dict[str, str] = {}
        for row in cur.fetchall():
            ticket = v2.v1.norm_ticket(row["trifecta_ticket"])
            if ticket:
                results[str(row["race_id"])] = ticket

    return races, entries_by, results


def actual_ticket(trifecta_ticket: str, bet_type: str) -> str:
    parts = [int(x) for x in trifecta_ticket.split("-")]
    if len(parts) != 3 or len(set(parts)) != 3:
        return ""
    if bet_type == "trifecta":
        return "-".join(map(str, parts))
    if bet_type == "exacta":
        return f"{parts[0]}-{parts[1]}"
    if bet_type == "trio":
        return "-".join(map(str, sorted(parts)))
    raise ValueError(f"unknown bet type: {bet_type}")


def aggregate(observations: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        observations,
        key=lambda x: (x["race_date"], x["venue_id"], x["race_no"], x["race_id"]),
    )
    n = len(ordered)
    hits = sum(1 for row in ordered if row["hit"])
    total_tickets = sum(int(row["ticket_count"]) for row in ordered)
    masses = [float(row["probability_mass"]) for row in ordered]

    losing = 0
    max_losing = 0
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        if row["hit"]:
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        by_month[str(row["race_date"])[:7]].append(row)
        by_day[str(row["race_date"])[:10]].append(row)

    monthly = {}
    for month, rows in sorted(by_month.items()):
        mh = sum(1 for row in rows if row["hit"])
        mt = sum(int(row["ticket_count"]) for row in rows)
        monthly[month] = {
            "races": len(rows),
            "hits": mh,
            "race_hit_rate_pct": round(mh / len(rows) * 100.0, 3) if rows else None,
            "tickets": mt,
            "mean_tickets_per_race": round(mt / len(rows), 3) if rows else None,
        }

    daily_hit_rates = []
    for rows in by_day.values():
        if rows:
            daily_hit_rates.append(sum(1 for row in rows if row["hit"]) / len(rows))

    return {
        "evaluated_races": n,
        "hits": hits,
        "race_hit_rate_pct": round(hits / n * 100.0, 3) if n else None,
        "tickets": total_tickets,
        "mean_tickets_per_race": round(total_tickets / n, 3) if n else None,
        "hits_per_100_tickets": round(hits / total_tickets * 100.0, 3) if total_tickets else None,
        "mean_probability_mass_pct": round(mean(masses) * 100.0, 3) if masses else None,
        "max_losing_race_streak": max_losing,
        "mean_daily_race_hit_rate_pct": round(mean(daily_hit_rates) * 100.0, 3) if daily_hit_rates else None,
        "monthly": monthly,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if not RACE_CAPS:
        raise RuntimeError("at least one race cap is required")

    print("CANDIDATE_BETTYPE_MODE=read_only_hit_rate_no_payout", flush=True)
    print(f"CANDIDATE_BETTYPE_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(f"CANDIDATE_BETTYPE_RACE_CAPS={','.join(map(str, RACE_CAPS))}", flush=True)
    print("CANDIDATE_BETTYPE_TYPES=trifecta,exacta,trio", flush=True)
    print("CANDIDATE_BETTYPE_FIXED_POINTS=1,2,3,5 COVERAGE=20,35,50 MAX_COVERAGE_TICKETS=12", flush=True)
    print("CANDIDATE_BETTYPE_ODDS_READ=0 EV_FILTER=0 PAYOUT_READ=0", flush=True)
    print("CANDIDATE_BETTYPE_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")
        races, entries_by, results = load_data(conn)
        conn.rollback()

    by_variant_day: dict[str, dict[str, list[dict[str, Any]]]] = {
        "BASE": defaultdict(list),
        "MOTOR2_FACTOR": defaultdict(list),
    }
    audit = {
        "races_total": len(races),
        "evaluable_races": 0,
        "motor_complete_races": 0,
        "official_result_tickets": len(results),
    }

    # Freeze probability distributions and race ranking without consulting results.
    for race in races:
        race_id = str(race.get("race_id") or "")
        entries = entries_by.get(race_id, [])
        if len(entries) != 6 or {v2.v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES:
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base_probs = v2.v1.ticket_probabilities(entries, venue, 0.0)
        m2_probs = v2.motor_adjust(base_probs, entries)
        if v2.motor_z(entries) is not None:
            audit["motor_complete_races"] += 1
        ds = str(race.get("race_date") or "")[:10]
        by_variant_day["BASE"][ds].append(v2.probability_metrics(race, base_probs, "BASE"))
        by_variant_day["MOTOR2_FACTOR"][ds].append(v2.probability_metrics(race, m2_probs, "MOTOR2_FACTOR"))
        audit["evaluable_races"] += 1

    buckets: dict[tuple[str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    mean_races_per_day: dict[str, float] = {}

    for variant, by_day in by_variant_day.items():
        ranked_days = {ds: v2.rank_day(rows) for ds, rows in sorted(by_day.items())}
        for race_cap in RACE_CAPS:
            selected: list[dict[str, Any]] = []
            daily_counts: list[int] = []
            for ds, rows in ranked_days.items():
                take = rows[: min(race_cap, len(rows))]
                selected.extend(take)
                daily_counts.append(len(take))
            mean_races_per_day[f"{variant}_R{race_cap}"] = round(mean(daily_counts), 3) if daily_counts else 0.0

            # Only now consult official results for hit/no-hit evaluation.
            for row in selected:
                win_tri = results.get(str(row["race_id"]))
                if not win_tri:
                    continue
                tri_probs = {
                    ticket: float(prob)
                    for ticket, prob in zip(row["ranked_tickets"], row["ranked_probs"])
                }
                grid = bet.build_comparison_grid(tri_probs)
                for view in grid:
                    bet_type = str(view["bet_type"])
                    strategy = str(view["strategy"])
                    winner = actual_ticket(win_tri, bet_type)
                    tickets = tuple(str(x) for x in view["tickets"])
                    buckets[(variant, race_cap, bet_type, strategy)].append({
                        "race_id": str(row["race_id"]),
                        "race_date": str(row["race_date"]),
                        "venue_id": str(row["venue_id"]),
                        "race_no": int(row["race_no"]),
                        "ticket_count": int(view["ticket_count"]),
                        "probability_mass": float(view["probability_mass"]),
                        "hit": winner in tickets,
                    })

    reports: dict[str, Any] = {}
    for (variant, race_cap, bet_type, strategy), observations in sorted(buckets.items()):
        key = f"{variant}|R{race_cap}|{bet_type}|{strategy}"
        reports[key] = aggregate(observations)

    primary = {
        key: value
        for key, value in reports.items()
        if key.startswith(f"{PRIMARY_VARIANT}|R{PRIMARY_RACE_CAP}|")
    }

    out = {
        "contract": "candidate_discovery_bettype_hit_audit_v1",
        "period": {"start": START_DATE, "end": END_DATE},
        "race_caps": list(RACE_CAPS),
        "variants": ["BASE", "MOTOR2_FACTOR"],
        "bet_types": list(bet.BET_TYPES),
        "fixed_point_counts": list(bet.FIXED_POINT_COUNTS),
        "coverage_targets": list(bet.COVERAGE_TARGETS),
        "coverage_max_tickets": bet.COVERAGE_MAX_TICKETS,
        "stake_per_ticket_yen_reference": bet.STAKE_PER_TICKET_YEN,
        "selection_contract": "V2_equal_weight_head_p1_head_margin_top3_mass_concentration",
        "audit": audit,
        "mean_races_per_day": mean_races_per_day,
        "reports": reports,
        "primary_motor2_r6": primary,
        "payout_evaluated": False,
        "profitability_established": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"CANDIDATE_BETTYPE_AUDIT={json.dumps(audit, sort_keys=True)}", flush=True)
    for key, value in sorted(primary.items()):
        compact = {k: value[k] for k in (
            "evaluated_races", "hits", "race_hit_rate_pct", "tickets",
            "mean_tickets_per_race", "hits_per_100_tickets",
            "max_losing_race_streak", "mean_probability_mass_pct"
        )}
        print(f"CANDIDATE_BETTYPE_PRIMARY={key} {json.dumps(compact, sort_keys=True)}", flush=True)
    print("CANDIDATE_BETTYPE_PROFITABILITY=NOT_EVALUATED_NO_PAYOUT_DATA", flush=True)
    print("CANDIDATE_BETTYPE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"CANDIDATE_BETTYPE_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
