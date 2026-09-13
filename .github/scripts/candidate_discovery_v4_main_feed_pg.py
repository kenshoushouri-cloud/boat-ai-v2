# -*- coding: utf-8 -*-
"""Read-only integrated Candidate Discovery V4 main-feed generator.

Research-only Forward candidate generator. It integrates the frozen V4 pure
contract with timing-safe pre-result Production data without changing Production.

Inputs:
- v2_races / v2_race_entries: race card and BASE structural fields
- v2_racer_course_stats_snapshots: exact-date official Course observations only
- v2_opponent_pressure_shadow_v2: timing-clean v2 opponent-pressure arrays only
- v2_candidate_filter_shadow: legacy S01-S05 carryover only

It never reads outcomes/payouts and never writes the database. Course, Opponent
Pressure and Motor2 missingness fail neutral, as frozen by the V4 contract.
Odds/EV are not read and cannot affect candidate inclusion/order.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V1_PATH = HERE / "candidate_discovery_v1_pg.py"
V4_PATH = ROOT / "research" / "candidate_discovery_v4_contract.py"

v1_spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", V1_PATH)
v1 = importlib.util.module_from_spec(v1_spec)
assert v1_spec and v1_spec.loader
v1_spec.loader.exec_module(v1)

v4_spec = importlib.util.spec_from_file_location("candidate_discovery_v4_contract", V4_PATH)
v4 = importlib.util.module_from_spec(v4_spec)
assert v4_spec and v4_spec.loader
v4_spec.loader.exec_module(v4)

JST = timezone(timedelta(hours=9))
TARGET_DATE = date.fromisoformat(
    os.getenv("CANDIDATE_V4_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
)
OUTPUT = Path(os.getenv("CANDIDATE_V4_OUTPUT", "candidate-discovery-v4-main-feed.json"))
SOURCE_CUTOFF = time(8, 15)
COURSE_SOURCE = "boatrace_official_racer_course"
OPPONENT_MODEL_VERSION = 2
MIN_MATCHED_OPPONENTS = 4
LEGACY_RULES = {"S01", "S02", "S03", "S04", "S05"}
ALL_LANES = {1, 2, 3, 4, 5, 6}


def _aware_jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _cutoff() -> datetime:
    return datetime.combine(TARGET_DATE, SOURCE_CUTOFF, tzinfo=JST)


def _tier(rank: int) -> str:
    if rank <= 2:
        return "A"
    if rank <= 4:
        return "B"
    return "C"


def _load(conn: psycopg.Connection[Any]):
    cutoff = _cutoff()
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date=%s
             order by venue_id,race_no,race_id
            """,
            (TARGET_DATE,),
        )
        races = [dict(row) for row in cur.fetchall()]
        race_ids = [str(row["race_id"]) for row in races]

        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        racer_numbers: set[int] = set()
        if race_ids:
            cur.execute(
                """
                select race_id,lane,racer_number,racer_class,national_win_rate,
                       national_place2_rate,local_place2_rate,avg_st,motor_place2_rate
                  from v2_race_entries
                 where race_id=any(%s)
                 order by race_id,lane
                """,
                (race_ids,),
            )
            for row in cur.fetchall():
                item = dict(row)
                entries_by[str(item["race_id"])].append(item)
                if item.get("racer_number") not in (None, ""):
                    racer_numbers.add(int(item["racer_number"]))

        course_by: dict[tuple[str, int], dict[str, Any]] = {}
        if racer_numbers:
            cur.execute(
                """
                select distinct on (racer_number,course)
                       racer_number,course,top3_rate,created_at,source
                  from v2_racer_course_stats_snapshots
                 where snapshot_date=%s
                   and racer_number=any(%s)
                   and course between 1 and 6
                   and created_at < %s
                 order by racer_number,course,created_at desc
                """,
                (TARGET_DATE, sorted(racer_numbers), cutoff),
            )
            for row in cur.fetchall():
                item = dict(row)
                course_by[(str(item["racer_number"]), int(item["course"]))] = item

        opponent_by: dict[str, dict[str, Any]] = {}
        if race_ids:
            cur.execute(
                """
                select race_id,race_date,model_version,train_end,matched_opponents,
                       base_win,adj_win,created_at,updated_at
                  from v2_opponent_pressure_shadow_v2
                 where race_id=any(%s) and race_date=%s
                 order by race_id
                """,
                (race_ids, TARGET_DATE),
            )
            opponent_by = {str(row["race_id"]): dict(row) for row in cur.fetchall()}

        legacy: list[dict[str, Any]] = []
        if race_ids:
            cur.execute(
                """
                select race_id,race_date,venue_id,race_no,rule_id,ticket,
                       prob,prob_rank,market_rank,odds,snapshot_at,id
                  from v2_candidate_filter_shadow
                 where race_date=%s and rule_id=any(%s)
                 order by race_id,rule_id,snapshot_at desc nulls last,id desc
                """,
                (TARGET_DATE, sorted(LEGACY_RULES)),
            )
            seen: set[tuple[str, str]] = set()
            for row in cur.fetchall():
                item = dict(row)
                key = (str(item["race_id"]), str(item["rule_id"]))
                if key in seen:
                    continue
                seen.add(key)
                ticket = v1.norm_ticket(item.get("ticket"))
                if ticket:
                    item["ticket"] = ticket
                    legacy.append(item)

    return races, entries_by, course_by, opponent_by, legacy


def _course_map(
    entries: list[dict[str, Any]],
    deadline: datetime,
    course_by: dict[tuple[str, int], dict[str, Any]],
) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = v1.si(entry.get("lane"), 0)
        racer = str(entry.get("racer_number") or "")
        row = course_by.get((racer, lane))
        if not row or str(row.get("source") or "") != COURSE_SOURCE:
            continue
        created = _aware_jst(row.get("created_at"))
        value = _finite(row.get("top3_rate"))
        if created is None or created >= deadline or created >= _cutoff():
            continue
        if value is None or not 0.0 <= value <= 100.0:
            continue
        out[lane] = value
    return out


def _opponent_delta(row: dict[str, Any] | None, deadline: datetime) -> dict[int, float] | None:
    if not row:
        return None
    if int(row.get("model_version") or 0) != OPPONENT_MODEL_VERSION:
        return None
    race_date = row.get("race_date")
    train_end = row.get("train_end")
    if race_date != TARGET_DATE or train_end is None or train_end >= race_date:
        return None
    matched = row.get("matched_opponents")
    base = row.get("base_win")
    adj = row.get("adj_win")
    if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
        return None
    if any(int(x) < MIN_MATCHED_OPPONENTS for x in matched):
        return None
    created = _aware_jst(row.get("created_at"))
    updated = _aware_jst(row.get("updated_at"))
    if created is None or updated is None:
        return None
    if created >= _cutoff() or updated >= _cutoff() or created >= deadline or updated >= deadline:
        return None
    delta: dict[int, float] = {}
    for idx in range(6):
        b = _finite(base[idx])
        a = _finite(adj[idx])
        if b is None or a is None:
            return None
        delta[idx + 1] = a - b
    return delta


def _motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = v1.si(entry.get("lane"), 0)
        value = _finite(entry.get("motor_place2_rate"))
        if lane not in ALL_LANES or value is None or not 0.0 <= value <= 100.0:
            return {}
        out[lane] = value
    return out if set(out) == ALL_LANES else {}


def _base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
    by_lane = {v1.si(row.get("lane"), 0): row for row in entries}
    if set(by_lane) != ALL_LANES:
        raise ValueError("complete six-lane entries required")
    return {
        lane: v1.lane_raw_strength(by_lane[lane], lane, venue, 0.0)
        for lane in range(1, 7)
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"CANDIDATE_V4_DATE={TARGET_DATE}", flush=True)
    print("CANDIDATE_V4_MODE=read_only_integrated_pre_result_candidate_feed", flush=True)
    print(
        "CANDIDATE_V4_FIXED="
        f"course:{v4.COURSE_COEF} opponent_head:{v4.OPPONENT_COEF} "
        f"motor2:{v4.MOTOR_BETA} races:{v4.CORE_RACES} tickets:{v4.CORE_TICKETS}",
        flush=True,
    )
    print("CANDIDATE_V4_EV_FILTER=0 ODDS_FILTER=0 ODDS_READ=0", flush=True)
    print("CANDIDATE_V4_RESULT_READ=0 PAYOUT_READ=0 DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, entries_by, course_by, opponent_by, legacy_rows = _load(conn)
        conn.rollback()

    distributions: dict[str, dict[str, float]] = {}
    meta: dict[str, dict[str, Any]] = {}
    skipped = 0
    course_lane_count = 0
    course_race_count = 0
    opponent_race_count = 0
    motor_race_count = 0

    for race in races:
        rid = str(race["race_id"])
        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES:
            skipped += 1
            continue
        deadline = _aware_jst(race.get("deadline_at"))
        if deadline is None:
            skipped += 1
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        course = _course_map(entries, deadline, course_by)
        opponent = _opponent_delta(opponent_by.get(rid), deadline)
        motor = _motor_map(entries)
        base = _base_raw(entries, venue)
        probs = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        distributions[rid] = probs
        course_lane_count += len(course)
        course_race_count += 1 if course else 0
        opponent_race_count += 1 if opponent is not None else 0
        motor_race_count += 1 if motor else 0
        meta[rid] = {
            "race_id": rid,
            "race_date": str(race.get("race_date") or TARGET_DATE)[:10],
            "venue_id": venue,
            "race_no": v1.si(race.get("race_no"), 0),
            "deadline_at": str(deadline),
            "course_usable_lanes": len(course),
            "opponent_pressure_available": opponent is not None,
            "motor2_complete": bool(motor),
        }

    selected = v4.select_daily(distributions, race_cap=v4.CORE_RACES, ticket_count=v4.CORE_TICKETS)
    feed_by_race: dict[str, dict[str, Any]] = {}
    for row in selected:
        rid = str(row["race_id"])
        rank = int(row["daily_race_rank"])
        m = meta[rid]
        tickets = [
            {
                "ticket": str(ticket),
                "core_order": idx,
                "source": ["DISCOVERY_CORE"],
                "legacy_rules": [],
            }
            for idx, ticket in enumerate(row["tickets"], 1)
        ]
        feed_by_race[rid] = {
            **m,
            "tier": _tier(rank),
            "daily_rank": rank,
            "race_score": round(float(row["race_score"]), 8),
            "head_lane": int(row["head_lane"]),
            "head_p1": round(float(row["head_p1"]), 8),
            "tickets": tickets,
            "legacy_carryover": False,
        }

    legacy_added_races = 0
    legacy_added_tickets = 0
    legacy_exact_overlap = 0
    race_meta = {str(row["race_id"]): row for row in races}
    for legacy in legacy_rows:
        rid = str(legacy["race_id"])
        ticket = str(legacy["ticket"])
        rule_id = str(legacy["rule_id"])
        race_feed = feed_by_race.get(rid)
        if race_feed is None:
            rm = race_meta.get(rid)
            if rm is None:
                continue
            race_feed = {
                "race_id": rid,
                "race_date": str(rm.get("race_date") or TARGET_DATE)[:10],
                "venue_id": str(rm.get("venue_id") or rm.get("venue_code") or "").zfill(2),
                "race_no": v1.si(rm.get("race_no"), 0),
                "deadline_at": str(_aware_jst(rm.get("deadline_at"))),
                "course_usable_lanes": None,
                "opponent_pressure_available": None,
                "motor2_complete": None,
                "tier": "L",
                "daily_rank": None,
                "race_score": None,
                "head_lane": None,
                "head_p1": None,
                "tickets": [],
                "legacy_carryover": True,
            }
            feed_by_race[rid] = race_feed
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
    summary = {
        "date": TARGET_DATE.isoformat(),
        "scheduled_races": len(races),
        "evaluable_races": len(distributions),
        "skipped_incomplete_entries_or_deadline": skipped,
        "core_races": len(selected),
        "core_tickets": sum(
            1 for race in feed for ticket in race["tickets"] if ticket.get("core_order") is not None
        ),
        "course_supported_races": course_race_count,
        "course_usable_lanes": course_lane_count,
        "opponent_pressure_supported_races": opponent_race_count,
        "motor2_complete_races": motor_race_count,
        "legacy_shadow_rows": len(legacy_rows),
        "legacy_added_races": legacy_added_races,
        "legacy_added_tickets": legacy_added_tickets,
        "legacy_exact_overlap_events": legacy_exact_overlap,
        "feed_races": len(feed),
        "feed_tickets": sum(len(race["tickets"]) for race in feed),
    }
    out = {
        "contract": "candidate_discovery_v4_main_feed_v1",
        "summary": summary,
        "policy": {
            "course_coefficient": v4.COURSE_COEF,
            "course_missing_lane": "neutral",
            "course_source_cutoff_jst": "08:15",
            "opponent_pressure_coefficient": v4.OPPONENT_COEF,
            "opponent_pressure_role": "first_place_only",
            "motor2_beta": v4.MOTOR_BETA,
            "motor2_position_weights": list(v4.MOTOR_POS_W),
            "core_races_per_day": v4.CORE_RACES,
            "core_tickets_per_race": v4.CORE_TICKETS,
            "expected_value_filter": False,
            "odds_filter": False,
            "odds_read": False,
            "legacy_carryover": True,
        },
        "feed": feed,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("CANDIDATE_V4_SUMMARY=" + json.dumps(summary, sort_keys=True), flush=True)
    for race in feed:
        print(
            f"CANDIDATE_V4_RACE=tier:{race['tier']} rank:{race['daily_rank']} "
            f"race:{race['race_id']} venue:{race['venue_id']} R{int(race['race_no']):02d} "
            f"tickets:{','.join(x['ticket'] for x in race['tickets'])}",
            flush=True,
        )
    print("CANDIDATE_V4_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_V4_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_V4_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
