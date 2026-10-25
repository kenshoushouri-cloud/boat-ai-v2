# -*- coding: utf-8 -*-
"""Prospective, read-only V4 alpha=0.25 shadow freeze.

The target date must be the current JST date, the freeze must occur at/after
08:15 JST and before every selected race deadline, and no result/payout/odds
table is accessed. Output is a research artifact only; nothing is written to
PostgreSQL and no LINE/purchase action exists.
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

from research import candidate_discovery_v4_contract as v4
from research import v4_alpha025_prospective_shadow as shadow

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
V1_PATH = ROOT / ".github" / "scripts" / "candidate_discovery_v1_pg.py"

v1_spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", V1_PATH)
v1 = importlib.util.module_from_spec(v1_spec)
assert v1_spec and v1_spec.loader
v1_spec.loader.exec_module(v1)

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
COURSE_SOURCE = "boatrace_official_racer_course"
OPPONENT_MODEL_VERSION = 2
MIN_MATCHED_OPPONENTS = 4
ALL_LANES = {1, 2, 3, 4, 5, 6}

TARGET_DATE_TEXT = (os.getenv("V4_ALPHA025_FORWARD_DATE") or "").strip()
if not TARGET_DATE_TEXT:
    raise RuntimeError("V4_ALPHA025_FORWARD_DATE is required")
TARGET_DATE = date.fromisoformat(TARGET_DATE_TEXT)
OUTPUT = Path(
    os.getenv(
        "V4_ALPHA025_FORWARD_OUTPUT",
        "v4-alpha025-prospective-shadow.json",
    )
)


def aware_jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def cutoff() -> datetime:
    return datetime.combine(TARGET_DATE, SOURCE_CUTOFF, tzinfo=JST)


def load_pre_result(conn: psycopg.Connection[Any]):
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
                (TARGET_DATE, sorted(racer_numbers), cutoff()),
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
            opponent_by = {
                str(row["race_id"]): dict(row)
                for row in cur.fetchall()
            }

    return races, entries_by, course_by, opponent_by


def course_map(
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
        created = aware_jst(row.get("created_at"))
        value = finite(row.get("top3_rate"))
        if created is None or created >= deadline or created >= cutoff():
            continue
        if value is None or not 0.0 <= value <= 100.0:
            continue
        out[lane] = value
    return out


def opponent_delta(
    row: dict[str, Any] | None,
    deadline: datetime,
) -> dict[int, float] | None:
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
    created = aware_jst(row.get("created_at"))
    updated = aware_jst(row.get("updated_at"))
    if created is None or updated is None:
        return None
    if (
        created >= cutoff()
        or updated >= cutoff()
        or created >= deadline
        or updated >= deadline
    ):
        return None
    delta: dict[int, float] = {}
    for idx in range(6):
        b = finite(base[idx])
        a = finite(adj[idx])
        if b is None or a is None:
            return None
        delta[idx + 1] = a - b
    return delta


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = v1.si(entry.get("lane"), 0)
        value = finite(entry.get("motor_place2_rate"))
        if lane not in ALL_LANES or value is None or not 0.0 <= value <= 100.0:
            return {}
        out[lane] = value
    return out if set(out) == ALL_LANES else {}


def base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
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

    freeze_at = datetime.now(JST)
    if freeze_at.date() != TARGET_DATE:
        raise RuntimeError(
            f"prospective same-day freeze required: now={freeze_at.date()} "
            f"target={TARGET_DATE}"
        )
    if freeze_at.timetz().replace(tzinfo=None) < SOURCE_CUTOFF:
        raise RuntimeError("freeze before 08:15 JST is not allowed")

    print(f"V4_ALPHA025_FORWARD_DATE={TARGET_DATE}", flush=True)
    print(f"V4_ALPHA025_FREEZE_AT={freeze_at.isoformat()}", flush=True)
    print(
        "V4_ALPHA025_MODE=READ_ONLY_PRE_RESULT_SHADOW "
        "RESULT_READ=0 PAYOUT_READ=0 ODDS_READ=0 DB_WRITE=0 "
        "LINE=0 BUY=0 PROMOTION=0",
        flush=True,
    )

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, entries_by, course_by, opponent_by = load_pre_result(conn)
        conn.rollback()

    distributions: dict[str, dict[str, float]] = {}
    features: dict[str, dict[int, tuple[float, ...]]] = {}
    meta: dict[str, dict[str, Any]] = {}

    for race in races:
        rid = str(race["race_id"])
        entries = entries_by.get(rid, [])
        deadline = aware_jst(race.get("deadline_at"))
        if (
            len(entries) != 6
            or {v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES
            or deadline is None
        ):
            continue
        venue = str(
            race.get("venue_id") or race.get("venue_code") or ""
        ).zfill(2)
        base = base_raw(entries, venue)
        course = course_map(entries, deadline, course_by)
        opponent = opponent_delta(opponent_by.get(rid), deadline)
        motor = motor_map(entries)
        distributions[rid] = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        features[rid] = shadow.lane_feature_map(entries, base_raw=base)
        meta[rid] = {
            "race_id": rid,
            "race_date": TARGET_DATE.isoformat(),
            "venue_id": venue,
            "race_no": v1.si(race.get("race_no"), 0),
            "deadline_at": deadline.isoformat(),
            "course_usable_lanes": len(course),
            "opponent_pressure_available": opponent is not None,
            "motor2_complete": bool(motor),
        }

    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )
    if len(selected) != v4.CORE_RACES:
        raise RuntimeError(
            f"exact six current-control races required: got={len(selected)}"
        )

    frozen_races: list[dict[str, Any]] = []
    for row in selected:
        rid = str(row["race_id"])
        deadline = datetime.fromisoformat(str(meta[rid]["deadline_at"]))
        if deadline <= freeze_at:
            raise RuntimeError(
                f"selected race deadline not prospective: race={rid} "
                f"deadline={deadline.isoformat()} freeze={freeze_at.isoformat()}"
            )
        current_probs = distributions[rid]
        shadow_probs = shadow.shadow_distribution(
            current_probs,
            features[rid],
        )
        control_top2 = list(v4.top_tickets(current_probs, 2))
        shadow_top2 = list(v4.top_tickets(shadow_probs, 2))
        frozen_races.append(
            {
                **meta[rid],
                "daily_rank": int(row["daily_race_rank"]),
                "race_score": round(float(row["race_score"]), 10),
                "control_top2": control_top2,
                "shadow_top2": shadow_top2,
                "shadow_top5": list(v4.top_tickets(shadow_probs, 5)),
                "top2_changed": shadow_top2 != control_top2,
            }
        )

    model = shadow.model_metadata()
    out = {
        "contract": shadow.CONTRACT,
        "freeze": {
            "target_date": TARGET_DATE.isoformat(),
            "freeze_at_jst": freeze_at.isoformat(),
            "source_cutoff_jst": "08:15",
            "same_day_required": True,
            "all_selected_deadlines_after_freeze": True,
        },
        "model": model,
        "policy": {
            "alpha": shadow.ALPHA,
            "training_end_date": shadow.TRAINING_END_DATE,
            "historical_tuning_closed": True,
            "current_daily_six_fixed": True,
            "first_place_marginal_preserved": True,
            "formal_control_tickets": 2,
            "result_read": False,
            "payout_read": False,
            "odds_read": False,
            "db_write": False,
            "line_sent": False,
            "purchase_action": False,
            "promotion_allowed": False,
            "production_behavior_changed": False,
        },
        "summary": {
            "scheduled_races": len(races),
            "evaluable_races": len(distributions),
            "frozen_core_races": len(frozen_races),
            "top2_changed_races": sum(
                1 for row in frozen_races if row["top2_changed"]
            ),
        },
        "races": frozen_races,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "V4_ALPHA025_SUMMARY="
        + json.dumps(out["summary"], sort_keys=True),
        flush=True,
    )
    for row in frozen_races:
        print(
            f"V4_ALPHA025_RACE=rank:{row['daily_rank']} race:{row['race_id']} "
            f"control:{','.join(row['control_top2'])} "
            f"shadow:{','.join(row['shadow_top2'])} "
            f"changed:{int(row['top2_changed'])}",
            flush=True,
        )
    print(f"V4_ALPHA025_MODEL_SHA256={model['frozen_model_sha256']}", flush=True)
    print("V4_ALPHA025_PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_PROSPECTIVE_SHADOW_FREEZE", flush=True)


if __name__ == "__main__":
    main()
