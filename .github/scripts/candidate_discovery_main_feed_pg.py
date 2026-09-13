# -*- coding: utf-8 -*-
"""Candidate Discovery main feed prototype (READ ONLY).

Main-feed contract
------------------
- Always build a broad prediction feed from race-card structure, not EV/odds gates.
- Core: top 6 races/day by V2 structural predictability.
- Core formation: top 2 exact-order tickets/race from the BASE probability model.
- Tier A = daily ranks 1-2, B = 3-4, C = 5-6.
- Motor2 is an independent support tag: report overlap with the fixed beta=0.06
  Motor2-adjusted top-2, but do not change the core tickets yet.
- Existing S01-S05 candidates are carried over. If their ticket is outside the
  core top-2 it is appended to that race; if their race is outside core top-6,
  the race is appended as LEGACY tier.
- Odds may be attached as display metadata only. They never determine inclusion,
  tier, ticket order, or deletion from the feed.

No DB writes, no LINE sends, no BUY action, no Production selector changes.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
V2_PATH = HERE / "candidate_discovery_v2_formation_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v2_formation_pg", V2_PATH)
v2 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(v2)
v1 = v2.v1

JST = ZoneInfo("Asia/Tokyo")
TARGET_DATE = os.getenv("CANDIDATE_MAIN_DATE", datetime.now(JST).date().isoformat()).strip()
OUTPUT = Path(os.getenv("CANDIDATE_MAIN_OUTPUT", "candidate-discovery-main-feed.json"))
CORE_RACES = 6
CORE_TICKETS = 2
LEGACY_RULES = {"S01", "S02", "S03", "S04", "S05"}
ALL_LANES = {1, 2, 3, 4, 5, 6}


def tier_for(rank: int) -> str:
    if rank <= 2:
        return "A"
    if rank <= 4:
        return "B"
    return "C"


def load_data(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute(
            """select race_id,race_date,venue_id,venue_code,race_no,deadline_at
                 from v2_races
                where race_date=%s
                order by venue_id,race_no,race_id""",
            (TARGET_DATE,),
        )
        races = [dict(row) for row in cur.fetchall()]
        race_ids = [str(row["race_id"]) for row in races]
        entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
        odds: dict[tuple[str, str], float] = {}
        legacy: list[dict[str, Any]] = []
        if race_ids:
            cur.execute(
                """select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                          local_place2_rate,avg_st,motor_place2_rate
                     from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane""",
                (race_ids,),
            )
            for row in cur.fetchall():
                entries[str(row["race_id"])].append(dict(row))

            cur.execute(
                """select race_id,ticket,odds
                     from v2_odds_trifecta
                    where race_id=any(%s) and odds>0
                    order by race_id,ticket""",
                (race_ids,),
            )
            for row in cur.fetchall():
                ticket = v1.norm_ticket(row["ticket"])
                value = v1.sf(row["odds"], None)
                if ticket and value and value > 0:
                    odds[(str(row["race_id"]), ticket)] = float(value)

            cur.execute(
                """select race_id,race_date,venue_id,race_no,rule_id,ticket,
                          prob,prob_rank,market_rank,odds,snapshot_at
                     from v2_candidate_filter_shadow
                    where race_date=%s and rule_id=any(%s)
                    order by race_id,rule_id,snapshot_at desc nulls last,id desc""",
                (TARGET_DATE, sorted(LEGACY_RULES)),
            )
            seen = set()
            for row in cur.fetchall():
                key = (str(row["race_id"]), str(row["rule_id"]))
                if key in seen:
                    continue
                seen.add(key)
                ticket = v1.norm_ticket(row["ticket"])
                if ticket:
                    item = dict(row)
                    item["ticket"] = ticket
                    legacy.append(item)
    return races, entries, odds, legacy


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"CANDIDATE_MAIN_DATE={TARGET_DATE}", flush=True)
    print("CANDIDATE_MAIN_CONTRACT=core6_races_top2_tickets_plus_legacy_carryover", flush=True)
    print("CANDIDATE_MAIN_TIERS=A:rank1-2,B:rank3-4,C:rank5-6,L:legacy_outside_core", flush=True)
    print("CANDIDATE_MAIN_ODDS_ROLE=display_only", flush=True)
    print("CANDIDATE_MAIN_EV_FILTER=0 ODDS_FILTER=0 PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_MAIN_DB_WRITE=0 LINE=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
        races, entries_by, odds_map, legacy_rows = load_data(conn)
        conn.rollback()

    base_rows = []
    m2_by_race: dict[str, dict[str, Any]] = {}
    skipped = 0
    for race in races:
        race_id = str(race["race_id"])
        entries = entries_by.get(race_id, [])
        if len(entries) != 6 or {v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES:
            skipped += 1
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base_probs = v1.ticket_probabilities(entries, venue, 0.0)
        m2_probs = v2.motor_adjust(base_probs, entries)
        base = v2.probability_metrics(race, base_probs, "BASE")
        m2 = v2.probability_metrics(race, m2_probs, "MOTOR2_FACTOR")
        base["deadline_at"] = race.get("deadline_at")
        base_rows.append(base)
        m2_by_race[race_id] = m2

    ranked = v2.rank_day(base_rows)
    core = ranked[: min(CORE_RACES, len(ranked))]
    feed_by_race: dict[str, dict[str, Any]] = {}

    for row in core:
        race_id = str(row["race_id"])
        rank = int(row["daily_race_rank"])
        base_tickets = list(row["ranked_tickets"][:CORE_TICKETS])
        m2_tickets = set(m2_by_race[race_id]["ranked_tickets"][:CORE_TICKETS])
        ticket_rows = []
        for idx, ticket in enumerate(base_tickets, 1):
            ticket_rows.append(
                {
                    "ticket": ticket,
                    "core_order": idx,
                    "source": ["DISCOVERY_CORE"],
                    "motor2_top2_support": ticket in m2_tickets,
                    "display_odds": odds_map.get((race_id, ticket)),
                    "legacy_rules": [],
                }
            )
        feed_by_race[race_id] = {
            "race_id": race_id,
            "race_date": row["race_date"],
            "venue_id": row["venue_id"],
            "race_no": row["race_no"],
            "tier": tier_for(rank),
            "daily_rank": rank,
            "race_score": round(float(row["race_score"]), 8),
            "head_lane": row["head_lane"],
            "head_p1": round(float(row["head_p1"]), 8),
            "tickets": ticket_rows,
            "legacy_carryover": False,
        }

    legacy_added_races = 0
    legacy_added_tickets = 0
    legacy_exact_overlap = 0
    for legacy in legacy_rows:
        race_id = str(legacy["race_id"])
        ticket = str(legacy["ticket"])
        rule_id = str(legacy["rule_id"])
        race_feed = feed_by_race.get(race_id)
        if race_feed is None:
            race_meta = next((r for r in races if str(r["race_id"]) == race_id), None)
            if race_meta is None:
                continue
            race_feed = {
                "race_id": race_id,
                "race_date": str(race_meta.get("race_date") or TARGET_DATE)[:10],
                "venue_id": str(race_meta.get("venue_id") or race_meta.get("venue_code") or "").zfill(2),
                "race_no": v1.si(race_meta.get("race_no"), 0),
                "tier": "L",
                "daily_rank": None,
                "race_score": None,
                "head_lane": None,
                "head_p1": None,
                "tickets": [],
                "legacy_carryover": True,
            }
            feed_by_race[race_id] = race_feed
            legacy_added_races += 1

        existing = next((x for x in race_feed["tickets"] if x["ticket"] == ticket), None)
        if existing:
            legacy_exact_overlap += 1
            if rule_id not in existing["legacy_rules"]:
                existing["legacy_rules"].append(rule_id)
            if "LEGACY" not in existing["source"]:
                existing["source"].append("LEGACY")
        else:
            race_feed["tickets"].append(
                {
                    "ticket": ticket,
                    "core_order": None,
                    "source": ["LEGACY"],
                    "motor2_top2_support": ticket in set(m2_by_race.get(race_id, {}).get("ranked_tickets", [])[:CORE_TICKETS]),
                    "display_odds": odds_map.get((race_id, ticket)) or v1.sf(legacy.get("odds"), None),
                    "legacy_rules": [rule_id],
                }
            )
            legacy_added_tickets += 1

    feed = sorted(
        feed_by_race.values(),
        key=lambda row: (
            0 if row["daily_rank"] is not None else 1,
            row["daily_rank"] if row["daily_rank"] is not None else 999,
            row["venue_id"], row["race_no"], row["race_id"],
        ),
    )
    total_tickets = sum(len(row["tickets"]) for row in feed)
    motor_support = sum(
        1 for row in feed for ticket in row["tickets"] if ticket["motor2_top2_support"]
    )
    summary = {
        "date": TARGET_DATE,
        "scheduled_races": len(races),
        "evaluable_races": len(base_rows),
        "skipped_incomplete_entries": skipped,
        "core_races": len(core),
        "legacy_shadow_rows": len(legacy_rows),
        "legacy_added_races": legacy_added_races,
        "legacy_added_tickets": legacy_added_tickets,
        "legacy_exact_overlap_events": legacy_exact_overlap,
        "feed_races": len(feed),
        "feed_tickets": total_tickets,
        "motor2_supported_tickets": motor_support,
    }

    out = {
        "contract": "candidate_discovery_main_feed_v1",
        "summary": summary,
        "policy": {
            "core_races_per_day": CORE_RACES,
            "core_tickets_per_race": CORE_TICKETS,
            "tiers": {"A": "rank1-2", "B": "rank3-4", "C": "rank5-6", "L": "legacy outside core"},
            "odds_role": "display_only",
            "expected_value_filter": False,
            "odds_filter": False,
            "legacy_carryover": True,
            "motor2_role": "support_tag_only",
        },
        "feed": feed,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print("CANDIDATE_MAIN_SUMMARY=" + json.dumps(summary, sort_keys=True), flush=True)
    for row in feed:
        print(
            f"CANDIDATE_MAIN_RACE=tier:{row['tier']} rank:{row['daily_rank']} "
            f"race:{row['race_id']} venue:{row['venue_id']} R{int(row['race_no']):02d} "
            f"tickets:{','.join(x['ticket'] for x in row['tickets'])}",
            flush=True,
        )
    print("CANDIDATE_MAIN_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_MAIN_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_MAIN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
