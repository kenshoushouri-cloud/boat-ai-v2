# -*- coding: utf-8 -*-
"""Read-only A/B/C tier bet-type hit-rate audit.

Uses the same historical V2 structural ranking geometry as the first bet-type audit,
but restricts to the current main-feed shape: top 6 races/day.

Tier mapping is frozen before result evaluation:
- A: daily race rank 1-2
- B: daily race rank 3-4
- C: daily race rank 5-6

For each tier, compare trifecta / exacta / trio across the already-frozen point
strategies from candidate_discovery_bettype_contract.py. No odds, payout, EV,
DB writes, LINE, BUY, or Production changes.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "candidate_discovery_bettype_hit_audit_pg.py"
spec_base = importlib.util.spec_from_file_location("candidate_discovery_bettype_hit_audit_pg", BASE_PATH)
base = importlib.util.module_from_spec(spec_base)
assert spec_base and spec_base.loader
spec_base.loader.exec_module(base)

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_BETTYPE_TIER_START", "2025-07-01").strip()
END_DATE = os.getenv(
    "CANDIDATE_BETTYPE_TIER_END",
    (datetime.now(JST).date() - timedelta(days=1)).isoformat(),
).strip()
OUTPUT = Path(os.getenv("CANDIDATE_BETTYPE_TIER_OUTPUT", "candidate-discovery-bettype-tier-audit.json"))


def tier_for_rank(rank: int) -> str:
    if 1 <= rank <= 2:
        return "A"
    if 3 <= rank <= 4:
        return "B"
    if 5 <= rank <= 6:
        return "C"
    return "OUT"


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    # Keep imported loader on this workflow's frozen period.
    base.START_DATE = START_DATE
    base.END_DATE = END_DATE

    print("CANDIDATE_BETTYPE_TIER_MODE=read_only_motor2_top6_abc", flush=True)
    print(f"CANDIDATE_BETTYPE_TIER_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CANDIDATE_BETTYPE_TIER_MAP=A:1-2,B:3-4,C:5-6", flush=True)
    print("CANDIDATE_BETTYPE_TIER_ODDS_READ=0 EV_FILTER=0 PAYOUT_READ=0", flush=True)
    print("CANDIDATE_BETTYPE_TIER_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")
        races, entries_by, results = base.load_data(conn)
        conn.rollback()

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evaluable = motor_complete = 0

    # Freeze MOTOR2_FACTOR probabilities and daily rank before reading results.
    for race in races:
        race_id = str(race.get("race_id") or "")
        entries = entries_by.get(race_id, [])
        if len(entries) != 6 or {base.v2.v1.si(row.get("lane"), 0) for row in entries} != base.ALL_LANES:
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        raw = base.v2.v1.ticket_probabilities(entries, venue, 0.0)
        probs = base.v2.motor_adjust(raw, entries)
        if base.v2.motor_z(entries) is not None:
            motor_complete += 1
        ds = str(race.get("race_date") or "")[:10]
        by_day[ds].append(base.v2.probability_metrics(race, probs, "MOTOR2_FACTOR"))
        evaluable += 1

    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    tier_races = defaultdict(int)

    for ds, rows in sorted(by_day.items()):
        ranked = base.v2.rank_day(rows)[:6]
        for row in ranked:
            rank = int(row["daily_race_rank"])
            tier = tier_for_rank(rank)
            if tier == "OUT":
                continue
            win_tri = results.get(str(row["race_id"]))
            if not win_tri:
                continue
            tier_races[tier] += 1
            tri_probs = {
                ticket: float(prob)
                for ticket, prob in zip(row["ranked_tickets"], row["ranked_probs"])
            }
            for view in base.bet.build_comparison_grid(tri_probs):
                bet_type = str(view["bet_type"])
                strategy = str(view["strategy"])
                winner = base.actual_ticket(win_tri, bet_type)
                tickets = tuple(str(x) for x in view["tickets"])
                buckets[(tier, bet_type, strategy)].append({
                    "race_id": str(row["race_id"]),
                    "race_date": str(row["race_date"]),
                    "venue_id": str(row["venue_id"]),
                    "race_no": int(row["race_no"]),
                    "ticket_count": int(view["ticket_count"]),
                    "probability_mass": float(view["probability_mass"]),
                    "hit": winner in tickets,
                })

    reports: dict[str, Any] = {}
    for (tier, bet_type, strategy), obs in sorted(buckets.items()):
        reports[f"{tier}|{bet_type}|{strategy}"] = base.aggregate(obs)

    out = {
        "contract": "candidate_discovery_bettype_tier_audit_v1",
        "period": {"start": START_DATE, "end": END_DATE},
        "variant": "MOTOR2_FACTOR",
        "daily_race_cap": 6,
        "tier_map": {"A": [1, 2], "B": [3, 4], "C": [5, 6]},
        "tier_evaluated_races": dict(sorted(tier_races.items())),
        "audit": {
            "races_total": len(races),
            "evaluable_races": evaluable,
            "motor_complete_races": motor_complete,
            "official_result_tickets": len(results),
        },
        "reports": reports,
        "payout_evaluated": False,
        "profitability_established": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"CANDIDATE_BETTYPE_TIER_COUNTS={json.dumps(dict(sorted(tier_races.items())), sort_keys=True)}", flush=True)
    for key, value in sorted(reports.items()):
        tier, bet_type, strategy = key.split("|")
        if strategy not in {"top1", "top2", "top3", "top5"}:
            continue
        compact = {k: value[k] for k in (
            "evaluated_races", "hits", "race_hit_rate_pct", "tickets",
            "mean_tickets_per_race", "hits_per_100_tickets", "max_losing_race_streak"
        )}
        print(f"CANDIDATE_BETTYPE_TIER={key} {json.dumps(compact, sort_keys=True)}", flush=True)
    print("CANDIDATE_BETTYPE_TIER_PROFITABILITY=NOT_EVALUATED_NO_PAYOUT_DATA", flush=True)
    print("CANDIDATE_BETTYPE_TIER_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"CANDIDATE_BETTYPE_TIER_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
