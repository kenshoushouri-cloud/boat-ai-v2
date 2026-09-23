# -*- coding: utf-8 -*-
"""Read-only historical V4 1..5 point walk-forward economics.

Design:
- build V4 distributions from race-card data only;
- Course uses exact-date official snapshots created before 08:15 JST;
- Opponent uses model-v2 rows whose train_end is before race_date and whose
  created/updated timestamps are before 08:15 JST and the race deadline;
- Motor2 uses the race-specific entry motor_place2_rate field, as current V4;
- no odds/EV are used for candidate selection;
- results/payouts are queried only after each day's six-race + top-five ranking
  has been frozen in memory;
- a day with any missing/non-official selected result is unevaluable as a whole;
  there is no five-race shrink, replacement, synthetic zero, or rerank.

The script opens PostgreSQL in a read-only transaction and never writes.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4

VERSION = "2026-09-23 v4-point-count-historical-walkforward-v1"
JST = timezone(timedelta(hours=9))
SOURCE_CUTOFF = time(8, 15)
START_DATE = date.fromisoformat(
    os.getenv("V4_POINTS_BT_START_DATE", "2026-07-01")
)
END_DATE = date.fromisoformat(
    os.getenv("V4_POINTS_BT_END_DATE", "2026-08-15")
)
UNIT_YEN = int(os.getenv("V4_POINTS_BT_UNIT_YEN", "100"))
BLOCKS = int(os.getenv("V4_POINTS_BT_BLOCKS", "4"))
OUTPUT_JSON = Path(
    os.getenv("V4_POINTS_BT_OUTPUT_JSON", "v4-point-count-historical-walkforward.json")
)

if UNIT_YEN != 100:
    raise RuntimeError("V4_POINTS_BT_UNIT_YEN must remain fixed at 100")
if BLOCKS < 2:
    raise RuntimeError("V4_POINTS_BT_BLOCKS must be >= 2")
if END_DATE < START_DATE:
    raise RuntimeError("invalid backtest period")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V1_PATH = ROOT / ".github" / "scripts" / "candidate_discovery_v1_pg.py"
v1_spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", V1_PATH)
v1 = importlib.util.module_from_spec(v1_spec)
assert v1_spec and v1_spec.loader
v1_spec.loader.exec_module(v1)

COURSE_SOURCE = "boatrace_official_racer_course"
OPPONENT_MODEL_VERSION = 2
MIN_MATCHED_OPPONENTS = 4
ALL_LANES = {1, 2, 3, 4, 5, 6}
POINT_COUNTS = (1, 2, 3, 4, 5)


def daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


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


def cutoff_for(day: date) -> datetime:
    return datetime.combine(day, SOURCE_CUTOFF, tzinfo=JST)


def base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
    by_lane = {v1.si(row.get("lane"), 0): row for row in entries}
    if set(by_lane) != ALL_LANES:
        raise ValueError("complete six-lane entries required")
    return {
        lane: v1.lane_raw_strength(by_lane[lane], lane, venue, 0.0)
        for lane in range(1, 7)
    }


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = v1.si(entry.get("lane"), 0)
        value = finite(entry.get("motor_place2_rate"))
        if lane not in ALL_LANES or value is None or not 0.0 <= value <= 100.0:
            return {}
        out[lane] = value
    return out if set(out) == ALL_LANES else {}


def course_map(
    *,
    entries: list[dict[str, Any]],
    deadline: datetime,
    cutoff: datetime,
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
        if created is None or created >= deadline or created >= cutoff:
            continue
        if value is None or not 0.0 <= value <= 100.0:
            continue
        out[lane] = value
    return out


def opponent_delta(
    *,
    row: dict[str, Any] | None,
    race_day: date,
    deadline: datetime,
    cutoff: datetime,
) -> dict[int, float] | None:
    if not row:
        return None
    if int(row.get("model_version") or 0) != OPPONENT_MODEL_VERSION:
        return None
    if row.get("race_date") != race_day:
        return None
    train_end = row.get("train_end")
    if train_end is None or train_end >= race_day:
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
        created >= cutoff
        or updated >= cutoff
        or created >= deadline
        or updated >= deadline
    ):
        return None

    out: dict[int, float] = {}
    for idx in range(6):
        b = finite(base[idx])
        a = finite(adj[idx])
        if b is None or a is None:
            return None
        out[idx + 1] = a - b
    return out


@dataclass
class DayFreeze:
    target_date: date
    selected: list[dict[str, Any]]
    eligible_race_count: int
    skipped_incomplete: int
    course_supported_races: int
    opponent_supported_races: int
    motor_supported_races: int


def fetch_day_inputs(
    cur: psycopg.Cursor[Any],
    day: date,
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[tuple[str, int], dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    cutoff = cutoff_for(day)
    cur.execute(
        """
        select race_id,race_date,venue_id,venue_code,race_no,deadline_at
          from v2_races
         where race_date=%s
         order by venue_id,race_no,race_id
        """,
        (day,),
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
            rid = str(item["race_id"])
            entries_by[rid].append(item)
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
            (day, sorted(racer_numbers), cutoff),
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
            (race_ids, day),
        )
        opponent_by = {str(row["race_id"]): dict(row) for row in cur.fetchall()}

    return races, entries_by, course_by, opponent_by


def freeze_day(cur: psycopg.Cursor[Any], day: date) -> DayFreeze:
    races, entries_by, course_by, opponent_by = fetch_day_inputs(cur, day)
    cutoff = cutoff_for(day)

    distributions: dict[str, dict[str, float]] = {}
    meta: dict[str, dict[str, Any]] = {}
    skipped_incomplete = 0
    course_supported = 0
    opponent_supported = 0
    motor_supported = 0

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            skipped_incomplete += 1
            continue

        try:
            base = base_raw(entries, str(race.get("venue_id") or ""))
        except Exception:
            skipped_incomplete += 1
            continue

        course = course_map(
            entries=entries,
            deadline=deadline,
            cutoff=cutoff,
            course_by=course_by,
        )
        opponent = opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = motor_map(entries)

        probs = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        distributions[rid] = probs
        meta[rid] = {
            "race_id": rid,
            "venue_id": str(race.get("venue_id") or "").zfill(2),
            "race_no": int(race.get("race_no") or 0),
            "deadline_at": deadline,
            "course_lane_count": len(course),
            "opponent_available": opponent is not None,
            "motor_available": bool(motor),
        }
        course_supported += int(bool(course))
        opponent_supported += int(opponent is not None)
        motor_supported += int(bool(motor))

    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )

    frozen: list[dict[str, Any]] = []
    for row in selected:
        rid = str(row["race_id"])
        info = meta[rid]
        top5 = list(v4.top_tickets(distributions[rid], 5))
        formal_top2 = list(row["tickets"])
        if top5[:2] != formal_top2:
            raise RuntimeError(f"top-five prefix drift: {rid}")
        frozen.append(
            {
                **info,
                "daily_rank": int(row["daily_race_rank"]),
                "race_score": float(row["race_score"]),
                "formal_top2": formal_top2,
                "ranked_top5": top5,
            }
        )

    return DayFreeze(
        target_date=day,
        selected=frozen,
        eligible_race_count=len(distributions),
        skipped_incomplete=skipped_incomplete,
        course_supported_races=course_supported,
        opponent_supported_races=opponent_supported,
        motor_supported_races=motor_supported,
    )


def fetch_selected_results(
    cur: psycopg.Cursor[Any],
    day: date,
    selected_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Result query is intentionally isolated after freeze_day()."""
    if not selected_ids:
        return {}
    cur.execute(
        """
        select race_id,trifecta_ticket,trifecta_payout_yen,
               result_status,race_status
          from v2_results
         where race_date=%s
           and race_id=any(%s)
           and trifecta_ticket is not null
           and trifecta_payout_yen is not null
           and trifecta_payout_yen > 0
           and coalesce(result_status,'')='official'
           and coalesce(race_status,'')='official'
         order by race_id
        """,
        (day, selected_ids),
    )
    return {str(row["race_id"]): dict(row) for row in cur.fetchall()}


def norm_ticket(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(" ", "").replace("－", "-")
    parts = text.split("-")
    if (
        len(parts) != 3
        or any(not part.isdigit() for part in parts)
        or len(set(parts)) != 3
        or any(not (1 <= int(part) <= 6) for part in parts)
    ):
        return None
    return "-".join(str(int(part)) for part in parts)


def max_drawdown(profits: list[int]) -> int:
    running = 0
    peak = 0
    out = 0
    for profit in profits:
        running += profit
        peak = max(peak, running)
        out = max(out, peak - running)
    return out


def strategy_stats(rows: list[dict[str, Any]], points: int) -> dict[str, Any]:
    investments = len(rows) * points * UNIT_YEN
    gross = 0
    hits = 0
    profits: list[int] = []
    marginal_gross = 0
    marginal_hits = 0

    for row in rows:
        actual = row["actual_trifecta"]
        top = row["ranked_top5"][:points]
        hit = actual in top
        ret = int(row["payout_yen"]) if hit else 0
        gross += ret
        hits += int(hit)
        profits.append(ret - points * UNIT_YEN)

        marginal_ticket = row["ranked_top5"][points - 1]
        marginal_hit = actual == marginal_ticket
        marginal_gross += int(row["payout_yen"]) if marginal_hit else 0
        marginal_hits += int(marginal_hit)

    marginal_investment = len(rows) * UNIT_YEN
    return {
        "points_per_race": points,
        "races": len(rows),
        "investment_yen": investments,
        "gross_return_yen": gross,
        "profit_yen": gross - investments,
        "roi_percent": round(gross / investments * 100.0, 3) if investments else 0.0,
        "hit_races": hits,
        "hit_rate_percent": round(hits / len(rows) * 100.0, 3) if rows else 0.0,
        "max_drawdown_yen": max_drawdown(profits),
        "marginal": {
            "rank": points,
            "investment_yen": marginal_investment,
            "gross_return_yen": marginal_gross,
            "profit_yen": marginal_gross - marginal_investment,
            "roi_percent": round(
                marginal_gross / marginal_investment * 100.0, 3
            ) if marginal_investment else 0.0,
            "hit_races": marginal_hits,
            "hit_rate_percent": round(
                marginal_hits / len(rows) * 100.0, 3
            ) if rows else 0.0,
        },
    }


def split_blocks(days: list[str], blocks: int) -> list[set[str]]:
    if not days:
        return []
    blocks = min(blocks, len(days))
    base, extra = divmod(len(days), blocks)
    out: list[set[str]] = []
    start = 0
    for idx in range(blocks):
        size = base + (1 if idx < extra else 0)
        out.append(set(days[start:start + size]))
        start += size
    return out


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strategies = [strategy_stats(rows, points) for points in POINT_COUNTS]

    monthly: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        monthly[row["date"][:7]].append(row)
    month_rows = [
        {
            "month": month,
            "strategies": [
                strategy_stats(month_rows, points) for points in POINT_COUNTS
            ],
        }
        for month, month_rows in sorted(monthly.items())
    ]

    days = sorted({row["date"] for row in rows})
    blocks = []
    for idx, block_days in enumerate(split_blocks(days, BLOCKS), 1):
        block_rows = [row for row in rows if row["date"] in block_days]
        blocks.append(
            {
                "block": idx,
                "start_date": min(block_days),
                "end_date": max(block_days),
                "days": len(block_days),
                "strategies": [
                    strategy_stats(block_rows, points) for points in POINT_COUNTS
                ],
            }
        )

    screening = []
    for points in POINT_COUNTS:
        overall = strategies[points - 1]
        block_stats = [b["strategies"][points - 1] for b in blocks]
        month_stats = [m["strategies"][points - 1] for m in month_rows]
        marginal_block_rois = [b["marginal"]["roi_percent"] for b in block_stats]
        screening.append(
            {
                "points_per_race": points,
                "overall_profit_yen": overall["profit_yen"],
                "overall_roi_percent": overall["roi_percent"],
                "marginal_profit_yen": overall["marginal"]["profit_yen"],
                "marginal_roi_percent": overall["marginal"]["roi_percent"],
                "profitable_blocks": sum(
                    int(b["profit_yen"] > 0) for b in block_stats
                ),
                "total_blocks": len(block_stats),
                "marginal_profitable_blocks": sum(
                    int(b["marginal"]["profit_yen"] > 0) for b in block_stats
                ),
                "min_block_roi_percent": min(
                    (b["roi_percent"] for b in block_stats), default=0.0
                ),
                "median_block_roi_percent": round(
                    median([b["roi_percent"] for b in block_stats]), 3
                ) if block_stats else 0.0,
                "min_marginal_block_roi_percent": min(
                    marginal_block_rois, default=0.0
                ),
                "profitable_months": sum(
                    int(m["profit_yen"] > 0) for m in month_stats
                ),
                "total_months": len(month_stats),
            }
        )

    return {
        "strategies": strategies,
        "monthly": month_rows,
        "walkforward_blocks": blocks,
        "screening": screening,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_POINT_COUNT_HISTORICAL_VERSION={VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY PRE_RESULT_RANKING_ONLY RESULT_AFTER_FREEZE_ONLY "
        "NO_ODDS_SELECTION NO_5R_SHRINK NO_REPLACEMENT NO_RETUNE",
        flush=True,
    )
    print(
        "FIXED="
        f"core_races:{v4.CORE_RACES} formal_tickets:{v4.CORE_TICKETS} "
        f"research_ranks:5 unit_yen:{UNIT_YEN}",
        flush=True,
    )

    complete_rows: list[dict[str, Any]] = []
    day_audit: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='20min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for idx, day in enumerate(daterange(START_DATE, END_DATE), 1):
                frozen = freeze_day(cur, day)
                selected_ids = [row["race_id"] for row in frozen.selected]

                audit = {
                    "date": day.isoformat(),
                    "eligible_races": frozen.eligible_race_count,
                    "selected_races": len(frozen.selected),
                    "skipped_incomplete": frozen.skipped_incomplete,
                    "course_supported_races": frozen.course_supported_races,
                    "opponent_supported_races": frozen.opponent_supported_races,
                    "motor_supported_races": frozen.motor_supported_races,
                    "status": None,
                    "missing_result_races": [],
                }

                if len(frozen.selected) != v4.CORE_RACES:
                    audit["status"] = "UNEVALUABLE_NOT_EXACT_SIX_SELECTED"
                    day_audit.append(audit)
                    continue

                cutoff = cutoff_for(day)
                if any(row["deadline_at"] <= cutoff for row in frozen.selected):
                    audit["status"] = "UNEVALUABLE_SELECTED_DEADLINE_AT_OR_BEFORE_CUTOFF"
                    day_audit.append(audit)
                    continue

                # The only result/payout query happens after the full ranking is frozen.
                results = fetch_selected_results(cur, day, selected_ids)
                missing = sorted(set(selected_ids) - set(results))
                if missing:
                    audit["status"] = "UNEVALUABLE_MISSING_OFFICIAL_SELECTED_RESULT"
                    audit["missing_result_races"] = missing
                    day_audit.append(audit)
                    continue

                day_rows = []
                malformed = []
                for selected in frozen.selected:
                    result = results[selected["race_id"]]
                    actual = norm_ticket(result.get("trifecta_ticket"))
                    payout = result.get("trifecta_payout_yen")
                    if actual is None or not isinstance(payout, int) or payout <= 0:
                        malformed.append(selected["race_id"])
                        continue
                    day_rows.append(
                        {
                            "date": day.isoformat(),
                            "race_id": selected["race_id"],
                            "venue_id": selected["venue_id"],
                            "race_no": selected["race_no"],
                            "deadline_at": selected["deadline_at"].isoformat(),
                            "daily_rank": selected["daily_rank"],
                            "race_score": selected["race_score"],
                            "ranked_top5": selected["ranked_top5"],
                            "actual_trifecta": actual,
                            "payout_yen": int(payout),
                            "course_lane_count": selected["course_lane_count"],
                            "opponent_available": selected["opponent_available"],
                            "motor_available": selected["motor_available"],
                        }
                    )
                if malformed or len(day_rows) != v4.CORE_RACES:
                    audit["status"] = "UNEVALUABLE_MALFORMED_SELECTED_RESULT"
                    audit["missing_result_races"] = malformed
                    day_audit.append(audit)
                    continue

                audit["status"] = "EVALUATED_EXACT_SIX"
                day_audit.append(audit)
                complete_rows.extend(day_rows)

                if idx % 10 == 0:
                    print(
                        f"PROGRESS={day} evaluated_days="
                        f"{sum(a['status']=='EVALUATED_EXACT_SIX' for a in day_audit)}",
                        flush=True,
                    )

        conn.rollback()

    evaluated_days = [a for a in day_audit if a["status"] == "EVALUATED_EXACT_SIX"]
    aggregate_result = aggregate(complete_rows)
    selected_feature_coverage = {
        "races": len(complete_rows),
        "course_any_races": sum(
            int(row["course_lane_count"] > 0) for row in complete_rows
        ),
        "course_full6_races": sum(
            int(row["course_lane_count"] == 6) for row in complete_rows
        ),
        "opponent_available_races": sum(
            int(bool(row["opponent_available"])) for row in complete_rows
        ),
        "motor_available_races": sum(
            int(bool(row["motor_available"])) for row in complete_rows
        ),
    }
    denom = len(complete_rows) or 1
    selected_feature_coverage.update(
        {
            "course_any_percent": round(
                selected_feature_coverage["course_any_races"] / denom * 100.0,
                3,
            ),
            "course_full6_percent": round(
                selected_feature_coverage["course_full6_races"] / denom * 100.0,
                3,
            ),
            "opponent_available_percent": round(
                selected_feature_coverage["opponent_available_races"] / denom * 100.0,
                3,
            ),
            "motor_available_percent": round(
                selected_feature_coverage["motor_available_races"] / denom * 100.0,
                3,
            ),
        }
    )

    result = {
        "contract": "v4_point_count_historical_walkforward_v1",
        "version": VERSION,
        "period": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "policy": {
            "source_cutoff_jst": "08:15",
            "course_exact_date_created_before_cutoff": True,
            "opponent_exact_date_train_end_before_race_date": True,
            "opponent_created_updated_before_cutoff": True,
            "motor_from_race_entry": True,
            "odds_used_for_selection": False,
            "result_read_before_ranking": False,
            "payout_read_before_ranking": False,
            "five_race_shrink": False,
            "replacement_race": False,
            "retune": False,
            "db_write": False,
            "line": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": len(day_audit),
            "evaluated_days": len(evaluated_days),
            "evaluated_races": len(complete_rows),
            "unevaluable_days": len(day_audit) - len(evaluated_days),
            "status_counts": {
                status: sum(1 for row in day_audit if row["status"] == status)
                for status in sorted({str(row["status"]) for row in day_audit})
            },
        },
        "selected_feature_coverage": selected_feature_coverage,
        **aggregate_result,
        "evaluated_race_records": complete_rows,
        "day_audit": day_audit,
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== COVERAGE ===", flush=True)
    print(json.dumps(result["coverage"], ensure_ascii=False, sort_keys=True), flush=True)
    print("=== SELECTED FEATURE COVERAGE ===", flush=True)
    print(
        json.dumps(
            result["selected_feature_coverage"],
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print("=== OVERALL STRATEGIES ===", flush=True)
    for row in result["strategies"]:
        m = row["marginal"]
        print(
            "POINTS={points_per_race} RACES={races} INVEST={investment_yen} "
            "GROSS={gross_return_yen} PROFIT={profit_yen} ROI={roi_percent:.3f} "
            "HITS={hit_races} HIT_RATE={hit_rate_percent:.3f} DD={max_drawdown_yen} "
            "MARGINAL_PROFIT={mp} MARGINAL_ROI={mr:.3f} MARGINAL_HITS={mh}".format(
                **row,
                mp=m["profit_yen"],
                mr=m["roi_percent"],
                mh=m["hit_races"],
            ),
            flush=True,
        )
    print("=== WALKFORWARD SCREENING ===", flush=True)
    for row in result["screening"]:
        print(
            "POINTS={points_per_race} OVERALL_PROFIT={overall_profit_yen} "
            "OVERALL_ROI={overall_roi_percent:.3f} "
            "MARGINAL_PROFIT={marginal_profit_yen} "
            "MARGINAL_ROI={marginal_roi_percent:.3f} "
            "PROFITABLE_BLOCKS={profitable_blocks}/{total_blocks} "
            "MARGINAL_PROFITABLE_BLOCKS={marginal_profitable_blocks}/{total_blocks} "
            "MIN_BLOCK_ROI={min_block_roi_percent:.3f} "
            "MEDIAN_BLOCK_ROI={median_block_roi_percent:.3f}".format(**row),
            flush=True,
        )
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
