# -*- coding: utf-8 -*-
"""Read-only matched-contract baseline for the V5 research review.

Purpose:
- evaluate the frozen current V4 probability/selector contract on a historical
  universe where the model-critical inputs are actually available;
- use historical Course reconstruction plus either historical Opponent replay
  (model 102) or genuine timing-clean Forward Opponent evidence (model 2);
- keep recent_form as a coverage label only, not a V5-core feature;
- freeze daily TOP6/TOP2 before any result/payout read.

This is a V5-review baseline, not a new V5 model and not Production promotion.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research import _v4_long_history_walkforward_reference_20260923 as ref

JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
START_DATE = date.fromisoformat(os.getenv("MATCHED_BT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("MATCHED_BT_END_DATE", "2026-09-29"))
OUTPUT_JSON = Path(os.getenv("MATCHED_BT_OUTPUT_JSON", "v5-matched-contract-baseline.json"))
COURSE_SOURCE = "boatrace_official_k_applied_term_proxy"
HIST_OPP_VERSION = 102
FORWARD_OPP_VERSION = 2
MIN_MATCHED_OPPONENTS = 4
UNIT_YEN = 100
BLOCKS = 10


def daterange(a: date, b: date):
    x = a
    while x <= b:
        yield x
        x += timedelta(days=1)


def as_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except Exception:
            return None
    return None


def aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def finite(v: Any) -> float | None:
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def expected_course_snapshot(d: date) -> date | None:
    if date(2025, 7, 1) <= d <= date(2025, 12, 31):
        return date(2025, 4, 30)
    if date(2026, 1, 1) <= d <= date(2026, 6, 30):
        return date(2025, 10, 31)
    if date(2026, 7, 1) <= d <= date(2026, 12, 31):
        return date(2026, 4, 30)
    return None


def opponent_payload_valid(row: dict[str, Any], race_day: date) -> bool:
    train_end = as_date(row.get("train_end"))
    if train_end is None or train_end >= race_day:
        return False
    matched = row.get("matched_opponents")
    base = row.get("base_win")
    adj = row.get("adj_win")
    if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
        return False
    try:
        if any(int(x) < MIN_MATCHED_OPPONENTS for x in matched):
            return False
    except Exception:
        return False
    return all(finite(x) is not None for x in base) and all(finite(x) is not None for x in adj)


def opponent_delta(
    rows: list[dict[str, Any]],
    race_day: date,
    deadline: datetime,
) -> tuple[dict[int, float] | None, str | None]:
    # Prefer genuine timing-clean Forward evidence when present.
    cutoff = datetime.combine(race_day, SOURCE_CUTOFF, tzinfo=JST)
    for version, label in ((FORWARD_OPP_VERSION, "forward_timing_clean"), (HIST_OPP_VERSION, "historical_reconstruction")):
        for row in rows:
            if int(row.get("model_version") or 0) != version:
                continue
            if as_date(row.get("race_date")) != race_day or not opponent_payload_valid(row, race_day):
                continue
            if version == FORWARD_OPP_VERSION:
                created = aware_jst(row.get("created_at"))
                updated = aware_jst(row.get("updated_at"))
                if created is None or updated is None:
                    continue
                if created >= cutoff or updated >= cutoff or created >= deadline or updated >= deadline:
                    continue
            base = row["base_win"]
            adj = row["adj_win"]
            return ({i + 1: float(adj[i]) - float(base[i]) for i in range(6)}, label)
    return None, None


def fetch_day_inputs(cur: psycopg.Cursor[Any], day: date):
    cur.execute(
        """
        select race_id,race_date,venue_id,venue_code,race_no,deadline_at
          from v2_races
         where race_date=%s
         order by venue_id,race_no,race_id
        """,
        (day,),
    )
    races = [dict(x) for x in cur.fetchall()]
    race_ids = [str(x["race_id"]) for x in races]

    entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    racers: set[int] = set()
    if race_ids:
        cur.execute(
            """
            select race_id,lane,racer_number,racer_class,national_win_rate,
                   national_place2_rate,local_place2_rate,avg_st,motor_place2_rate,
                   recent_form
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
                racers.add(int(item["racer_number"]))

    course_by: dict[tuple[str, int], dict[str, Any]] = {}
    snap = expected_course_snapshot(day)
    if racers and snap is not None:
        cur.execute(
            """
            select distinct on (racer_number,course)
                   racer_number,course,top3_rate,snapshot_date,source,created_at
              from v2_racer_course_stats_snapshots
             where snapshot_date=%s
               and source=%s
               and racer_number=any(%s)
               and course between 1 and 6
             order by racer_number,course,created_at desc
            """,
            (snap, COURSE_SOURCE, sorted(racers)),
        )
        for row in cur.fetchall():
            item = dict(row)
            course_by[(str(item["racer_number"]), int(item["course"]))] = item

    opp_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if race_ids:
        cur.execute(
            """
            select race_id,race_date,model_version,train_end,matched_opponents,
                   base_win,adj_win,created_at,updated_at
              from v2_opponent_pressure_shadow_v2
             where race_id=any(%s)
               and race_date=%s
               and model_version in (%s,%s)
             order by race_id,model_version
            """,
            (race_ids, day, HIST_OPP_VERSION, FORWARD_OPP_VERSION),
        )
        for row in cur.fetchall():
            opp_by[str(row["race_id"])].append(dict(row))

    return races, entries_by, course_by, opp_by


def build_course(entries: list[dict[str, Any]], course_by: dict[tuple[str, int], dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = ref.v1.si(entry.get("lane"), 0)
        racer = str(entry.get("racer_number") or "")
        row = course_by.get((racer, lane))
        value = finite(row.get("top3_rate")) if row else None
        if value is not None and 0.0 <= value <= 100.0:
            out[lane] = value
    return out


def recent_form_complete(entries: list[dict[str, Any]]) -> bool:
    if len(entries) != 6:
        return False
    for row in entries:
        v = row.get("recent_form")
        if v is None:
            return False
        if isinstance(v, (list, dict)) and len(v) == 0:
            return False
        if isinstance(v, str) and v.strip() in ("", "null", "[]", "{}"):
            return False
    return True


def freeze_matched_day(cur: psycopg.Cursor[Any], day: date) -> dict[str, Any]:
    races, entries_by, course_by, opp_by = fetch_day_inputs(cur, day)
    distributions: dict[str, dict[str, float]] = {}
    meta: dict[str, dict[str, Any]] = {}
    evidence_counts = {"historical_reconstruction": 0, "forward_timing_clean": 0}
    incomplete = 0

    for race in races:
        rid = str(race["race_id"])
        deadline = aware_jst(race.get("deadline_at"))
        entries = entries_by.get(rid, [])
        if deadline is None or deadline <= datetime.combine(day, SOURCE_CUTOFF, tzinfo=JST) or len(entries) != 6:
            incomplete += 1
            continue
        try:
            base = ref.base_raw(entries, str(race.get("venue_id") or ""))
        except Exception:
            incomplete += 1
            continue
        motor = ref.motor_map(entries)
        course = build_course(entries, course_by)
        opp, evidence = opponent_delta(opp_by.get(rid, []), day, deadline)

        # Matched-contract universe: model-critical inputs must all exist.
        if len(motor) != 6 or len(course) != 6 or opp is None or evidence is None:
            continue

        probs = ref.v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opp,
        )
        distributions[rid] = probs
        evidence_counts[evidence] += 1
        meta[rid] = {
            "race_id": rid,
            "venue_id": str(race.get("venue_id") or "").zfill(2),
            "race_no": int(race.get("race_no") or 0),
            "deadline_at": deadline,
            "opponent_evidence_class": evidence,
            "recent_form6": recent_form_complete(entries),
        }

    selected = ref.v4.select_daily(
        distributions,
        race_cap=ref.v4.CORE_RACES,
        ticket_count=ref.v4.CORE_TICKETS,
    ) if len(distributions) >= ref.v4.CORE_RACES else []

    frozen = []
    for row in selected:
        rid = str(row["race_id"])
        frozen.append({
            **meta[rid],
            "daily_rank": int(row["daily_race_rank"]),
            "race_score": float(row["race_score"]),
            "formal_top2": list(row["tickets"]),
        })

    return {
        "eligible_matched_races": len(distributions),
        "selected": frozen,
        "skipped_incomplete": incomplete,
        "evidence_counts": evidence_counts,
    }


def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    races = len(rows)
    tickets = races * 2
    investment = tickets * UNIT_YEN
    hits = 0
    gross = 0
    for row in rows:
        if row["actual_trifecta"] in row["formal_top2"]:
            hits += 1
            gross += int(row["payout_yen"])
    profit = gross - investment
    return {
        "races": races,
        "tickets": tickets,
        "hits": hits,
        "hit_rate_pct": round(100.0 * hits / races, 3) if races else 0.0,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": profit,
        "roi_pct": round(100.0 * gross / investment, 3) if investment else 0.0,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if END_DATE < START_DATE:
        raise RuntimeError("invalid period")

    print("V5_MATCHED_BASELINE_CONTRACT=FROZEN_V4_CORE_MATCHED_EVIDENCE_V1", flush=True)
    print(f"V5_MATCHED_BASELINE_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("V5_MATCHED_BASELINE_POLICY=READ_ONLY MATCHED_CORE_ONLY PRE_RESULT_FREEZE RESULT_AFTER_FREEZE NO_RETUNE", flush=True)
    print("V5_MATCHED_BASELINE_RECENT_FORM_USED_AS_MODEL_INPUT=0", flush=True)
    print("V5_MATCHED_BASELINE_ODDS_EV_SELECTION=0", flush=True)
    print("V5_MATCHED_BASELINE_PRODUCTION_CHANGE=0 PURCHASE_ACTION=0", flush=True)

    evaluated_rows: list[dict[str, Any]] = []
    day_audit: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='20min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for day in daterange(START_DATE, END_DATE):
                frozen = freeze_matched_day(cur, day)
                selected = frozen["selected"]
                audit = {
                    "date": day.isoformat(),
                    "eligible_matched_races": frozen["eligible_matched_races"],
                    "selected_races": len(selected),
                    "opponent_evidence": frozen["evidence_counts"],
                    "selected_recent_form6": sum(int(x["recent_form6"]) for x in selected),
                    "status": None,
                }
                if len(selected) != ref.v4.CORE_RACES:
                    audit["status"] = "UNEVALUABLE_LT6_MATCHED_CORE"
                    day_audit.append(audit)
                    continue

                # Outcome query occurs only after the daily matched universe,
                # six races, scores and TOP2 tickets are frozen.
                selected_ids = [x["race_id"] for x in selected]
                results = ref.fetch_selected_results(cur, day, selected_ids)
                if set(results) != set(selected_ids):
                    audit["status"] = "UNEVALUABLE_MISSING_OFFICIAL_SELECTED_RESULT"
                    day_audit.append(audit)
                    continue

                day_rows = []
                malformed = False
                for sel in selected:
                    result = results[sel["race_id"]]
                    actual = ref.norm_ticket(result.get("trifecta_ticket"))
                    payout = result.get("trifecta_payout_yen")
                    if actual is None or not isinstance(payout, int) or payout <= 0:
                        malformed = True
                        break
                    day_rows.append({
                        **sel,
                        "date": day.isoformat(),
                        "actual_trifecta": actual,
                        "payout_yen": int(payout),
                    })
                if malformed:
                    audit["status"] = "UNEVALUABLE_MALFORMED_SELECTED_RESULT"
                    day_audit.append(audit)
                    continue

                audit["status"] = "EVALUATED_EXACT_SIX_MATCHED"
                day_audit.append(audit)
                evaluated_rows.extend(day_rows)
        conn.rollback()

    evaluated_days = sorted({x["date"] for x in evaluated_rows})
    blocks = []
    for idx, block_days in enumerate(ref.split_blocks(evaluated_days, BLOCKS), 1):
        block_rows = [x for x in evaluated_rows if x["date"] in block_days]
        blocks.append({
            "block": idx,
            "start_date": min(block_days) if block_days else None,
            "end_date": max(block_days) if block_days else None,
            "days": len(block_days),
            **stats(block_rows),
        })

    months = []
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated_rows:
        by_month[row["date"][:7]].append(row)
    for month in sorted(by_month):
        months.append({"month": month, **stats(by_month[month])})

    payload = {
        "contract": "V5_REVIEW_MATCHED_BASELINE_V1",
        "period": [START_DATE.isoformat(), END_DATE.isoformat()],
        "interpretation": {
            "model": "frozen_current_v4_core",
            "role": "v5_research_review_baseline",
            "candidate_universe": "matched_core_only_before_ranking",
            "recent_form_model_input": False,
            "historical_gate_credit": False,
            "no_posthoc_retune": True,
            "automatic_v5_promotion": False,
            "automatic_production_change": False,
        },
        "evidence_classes": {
            "course": COURSE_SOURCE,
            "opponent_historical_model_version": HIST_OPP_VERSION,
            "opponent_forward_model_version": FORWARD_OPP_VERSION,
            "forward_requires_before_0815_and_deadline": True,
        },
        "coverage": {
            "calendar_days": (END_DATE - START_DATE).days + 1,
            "evaluated_days": len(evaluated_days),
            "evaluated_races": len(evaluated_rows),
            "days_lt6_matched_core": sum(x["status"] == "UNEVALUABLE_LT6_MATCHED_CORE" for x in day_audit),
            "days_missing_official_result": sum(x["status"] == "UNEVALUABLE_MISSING_OFFICIAL_SELECTED_RESULT" for x in day_audit),
            "selected_recent_form6_races": sum(int(x["recent_form6"]) for x in evaluated_rows),
            "selected_forward_opponent_races": sum(x["opponent_evidence_class"] == "forward_timing_clean" for x in evaluated_rows),
            "selected_historical_opponent_races": sum(x["opponent_evidence_class"] == "historical_reconstruction" for x in evaluated_rows),
        },
        "formal_top2": stats(evaluated_rows),
        "monthly": months,
        "chronological_blocks": blocks,
        "day_audit": day_audit,
        "safety": {
            "transaction_read_only": True,
            "selection_before_result_query": True,
            "odds_ev_selection": False,
            "db_write": False,
            "production_change": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("V5_MATCHED_BASELINE_COVERAGE=" + json.dumps(payload["coverage"], sort_keys=True), flush=True)
    print("V5_MATCHED_BASELINE_FORMAL_TOP2=" + json.dumps(payload["formal_top2"], sort_keys=True), flush=True)
    print("V5_MATCHED_BASELINE_BLOCKS=" + json.dumps(blocks, sort_keys=True), flush=True)
    print("V5_MATCHED_BASELINE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
