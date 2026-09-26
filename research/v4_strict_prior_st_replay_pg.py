# -*- coding: utf-8 -*-
"""One-shot read-only V4 strict-prior-ST replay.

This script must only be run after the contract is frozen and CI validation is
green. It never writes to PostgreSQL and never reads odds.

Primary question: on the SAME current-V4 daily-rank-1 race, does the fixed
strict-prior-ST feature improve first-place multiclass proper scores?
"""
from __future__ import annotations

import bisect
import importlib.util
import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research.v4_strict_prior_st_contract import (
    BLOCKS,
    END_DATE,
    EXPECTED_CONTROL_DAYS,
    FORMAL_TICKETS,
    OFFICIAL_RESULT_ENTRY_SOURCE,
    PURE_EVAL_START_BLOCK,
    START_DATE,
    UNIT_YEN,
    adjust_base_raw,
    contract_metadata,
)

VERSION = "2026-09-27-v4-strict-prior-st-replay-v1"
PINNED_LONG_HELPER_SHA = "ac91c9a2e9570d3af3589e2e98b6529a77c14756"
OUTPUT_JSON = Path(os.getenv("V4_PRIOR_ST_OUTPUT_JSON", "v4-strict-prior-st-replay.json"))
LONG_HELPER_PATH = Path(
    os.getenv(
        "V4_LONG_HELPER_PATH",
        Path(__file__).resolve().parent / "v4_long_history_walkforward_pg.py",
    )
)
EPS = 1e-15


def load_long_helper():
    spec = importlib.util.spec_from_file_location("v4_prior_st_long_helper", LONG_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load long helper: {LONG_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def daterange(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def split_blocks(days: list[str], blocks: int = BLOCKS) -> list[list[str]]:
    q, r = divmod(len(days), blocks)
    out: list[list[str]] = []
    pos = 0
    for idx in range(blocks):
        size = q + (1 if idx < r else 0)
        out.append(days[pos : pos + size])
        pos += size
    return out


def block_bounds(days: list[str]) -> list[dict[str, object]]:
    groups = split_blocks(days, BLOCKS)
    return [
        {"block": idx + 1, "start": group[0], "end": group[-1], "days": len(group)}
        for idx, group in enumerate(groups)
        if group
    ]


def block_for(value: str, bounds: list[dict[str, object]]) -> int:
    for item in bounds:
        if str(item["start"]) <= value <= str(item["end"]):
            return int(item["block"])
    raise ValueError(f"date outside block bounds: {value}")


def first_place_marginal(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in range(1, 7)}
    for ticket, prob in probs.items():
        lane = int(str(ticket).split("-", 1)[0])
        out[lane] += float(prob)
    total = sum(out.values())
    if total <= 0:
        raise RuntimeError("invalid first-place mass")
    return {lane: value / total for lane, value in out.items()}


def prediction_record(
    *,
    day: date,
    variant: str,
    race_id: str,
    probs: Mapping[str, float],
    actual_ticket: str,
    payout_yen: int,
    selected_top6: list[str],
    prior_st_lane_count: int,
) -> dict[str, Any]:
    actual_head = int(actual_ticket.split("-", 1)[0])
    head = first_place_marginal(probs)
    predicted_head = min(
        (lane for lane in range(1, 7)),
        key=lambda lane: (-head[lane], lane),
    )
    p_actual = max(EPS, head[actual_head])
    brier = sum(
        (head[lane] - (1.0 if lane == actual_head else 0.0)) ** 2
        for lane in range(1, 7)
    )
    tickets = list(v4.top_tickets(probs, FORMAL_TICKETS))
    hit = actual_ticket in tickets
    gross = payout_yen if hit else 0
    return {
        "date": day.isoformat(),
        "variant": variant,
        "race_id": race_id,
        "selected_top6": selected_top6,
        "prior_st_lane_count": prior_st_lane_count,
        "head_correct": predicted_head == actual_head,
        "head_log_loss": -math.log(p_actual),
        "head_brier": brier,
        "formal_top2_hit": hit,
        "investment_yen": FORMAL_TICKETS * UNIT_YEN,
        "gross_return_yen": gross,
        "profit_yen": gross - FORMAL_TICKETS * UNIT_YEN,
    }


def max_drawdown(profits: list[int]) -> int:
    running = peak = out = 0
    for profit in profits:
        running += profit
        peak = max(peak, running)
        out = max(out, peak - running)
    return out


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {
            "days": 0,
            "head_accuracy_percent": None,
            "head_log_loss": None,
            "head_brier": None,
            "formal_top2_hit_rate_percent": None,
            "roi_percent": None,
            "profit_yen": 0,
            "max_drawdown_yen": 0,
        }
    investment = sum(int(row["investment_yen"]) for row in rows)
    gross = sum(int(row["gross_return_yen"]) for row in rows)
    profits = [int(row["profit_yen"]) for row in rows]
    return {
        "days": n,
        "head_accuracy_percent": round(100.0 * sum(bool(r["head_correct"]) for r in rows) / n, 6),
        "head_log_loss": round(sum(float(r["head_log_loss"]) for r in rows) / n, 9),
        "head_brier": round(sum(float(r["head_brier"]) for r in rows) / n, 9),
        "formal_top2_hit_rate_percent": round(
            100.0 * sum(bool(r["formal_top2_hit"]) for r in rows) / n, 6
        ),
        "roi_percent": round(100.0 * gross / investment, 6) if investment else None,
        "profit_yen": gross - investment,
        "max_drawdown_yen": max_drawdown(profits),
    }


def summarize(
    rows_by_variant: dict[str, list[dict[str, Any]]],
    bounds: list[dict[str, object]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for variant, rows in rows_by_variant.items():
        tagged = [(row, block_for(str(row["date"]), bounds)) for row in rows]
        pure = [row for row, block in tagged if block >= PURE_EVAL_START_BLOCK]
        strata = {
            "all": pure,
            "any": [row for row in pure if int(row["prior_st_lane_count"]) > 0],
            "full6": [row for row in pure if int(row["prior_st_lane_count"]) == 6],
        }
        out[variant] = {
            "all_period": aggregate(rows),
            "blocks_3_10": {name: aggregate(items) for name, items in strata.items()},
            "blocks": {
                str(block): aggregate([row for row, b in tagged if b == block])
                for block in range(1, BLOCKS + 1)
            },
        }
    return out


def selector_overlap(rows_by_variant: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    control = {row["date"]: row for row in rows_by_variant["control"]}
    variant = {row["date"]: row for row in rows_by_variant["strict_prior_st"]}
    common = sorted(set(control) & set(variant))
    rank1_same = sum(control[d]["race_id"] == variant[d]["race_id"] for d in common)
    top6 = [
        len(set(control[d]["selected_top6"]) & set(variant[d]["selected_top6"])) / 6.0
        for d in common
    ]
    return {
        "common_days": len(common),
        "rank1_same_days": rank1_same,
        "rank1_overlap_percent": round(100.0 * rank1_same / len(common), 6) if common else None,
        "mean_top6_overlap_percent": round(100.0 * sum(top6) / len(top6), 6) if top6 else None,
    }


def load_prior_st_history(cur) -> tuple[dict[int, list[tuple[date, int, str]]], dict[int, list[float]]]:
    end_exclusive = date.fromisoformat(END_DATE) + timedelta(days=1)
    cur.execute(
        """
        select re.racer_number, r.race_date::date race_date,
               coalesce(r.race_no,0)::int race_no, re.race_id::text race_id,
               re.start_timing::float8 start_timing
          from v2_result_entries re
          join v2_races r on r.race_id=re.race_id
         where re.racer_number is not null
           and re.start_timing is not null
           and re.start_timing >= 0.0 and re.start_timing <= 0.99
           and coalesce(re.source,'')=%s
           and r.race_date < %s
         order by re.racer_number,r.race_date,race_no,re.race_id
        """,
        (OFFICIAL_RESULT_ENTRY_SOURCE, end_exclusive),
    )
    keys: dict[int, list[tuple[date, int, str]]] = defaultdict(list)
    vals: dict[int, list[float]] = defaultdict(list)
    for row in cur.fetchall():
        racer = int(row["racer_number"])
        keys[racer].append((row["race_date"], int(row["race_no"]), str(row["race_id"])))
        vals[racer].append(float(row["start_timing"]))
    return dict(keys), dict(vals)


def latest_prior_st(
    racer_number: int,
    target_day: date,
    history_keys: Mapping[int, list[tuple[date, int, str]]],
    history_values: Mapping[int, list[float]],
) -> float | None:
    keys = history_keys.get(racer_number, [])
    if not keys:
        return None
    idx = bisect.bisect_left(keys, (target_day, -1, "")) - 1
    if idx < 0:
        return None
    return float(history_values[racer_number][idx])


def prior_st_map(entries, day, history_keys, history_values) -> dict[int, float]:
    out: dict[int, float] = {}
    for entry in entries:
        lane = int(entry.get("lane") or 0)
        racer = int(entry.get("racer_number") or 0)
        if lane not in range(1, 7) or racer <= 0:
            continue
        value = latest_prior_st(racer, day, history_keys, history_values)
        if value is not None:
            out[lane] = value
    return out


def prepare_day(helper, cur, day, history_keys, history_values) -> dict[str, Any]:
    races, entries_by, course_by, opponent_by = helper.fetch_day_inputs(cur, day)
    cutoff = helper.cutoff_for(day)
    distributions = {"control": {}, "strict_prior_st": {}}
    meta: dict[str, dict[str, Any]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = helper.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        try:
            base = helper.base_raw(entries, str(race.get("venue_id") or ""))
        except Exception:
            continue
        course = helper.course_map(
            entries=entries, deadline=deadline, cutoff=cutoff, course_by=course_by
        )
        opponent = helper.opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = helper.motor_map(entries)
        prior = prior_st_map(entries, day, history_keys, history_values)
        distributions["control"][rid] = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        distributions["strict_prior_st"][rid] = v4.build_v4_distribution(
            base_raw=adjust_base_raw(base, prior),
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        meta[rid] = {
            "deadline_at": deadline,
            "prior_st_lane_count": len(prior),
        }

    selected = {
        variant: v4.select_daily(
            distributions[variant],
            race_cap=v4.CORE_RACES,
            ticket_count=v4.CORE_TICKETS,
        )
        for variant in distributions
    }
    return {"distributions": distributions, "selected": selected, "meta": meta, "cutoff": cutoff}


def selected_ids(rows) -> list[str]:
    return [str(row["race_id"]) for row in rows]


def evaluated(prepared, variant: str, results: Mapping[str, Any]) -> bool:
    rows = prepared["selected"][variant]
    if len(rows) != v4.CORE_RACES:
        return False
    ids = selected_ids(rows)
    if any(prepared["meta"][rid]["deadline_at"] <= prepared["cutoff"] for rid in ids):
        return False
    return all(rid in results for rid in ids)


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    helper = load_long_helper()
    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)

    print(f"V4_PRIOR_ST_VERSION={VERSION}", flush=True)
    print(f"PINNED_LONG_HELPER_SHA={PINNED_LONG_HELPER_SHA}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY STRICT_PRIOR_DATE OFFICIAL_K_ONLY NO_SAME_DAY "
        "NO_ODDS NO_EV NO_THRESHOLD_SEARCH NO_RETUNE PURCHASE_FALSE",
        flush=True,
    )

    track_a = {"control": [], "strict_prior_st": []}
    track_b = {"control": [], "strict_prior_st": []}
    status = {"control": Counter(), "strict_prior_st": Counter()}
    calendar_days = 0
    history_rows = history_racers = 0

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='20min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            history_keys, history_values = load_prior_st_history(cur)
            history_racers = len(history_keys)
            history_rows = sum(len(v) for v in history_keys.values())
            print(
                f"PRIOR_ST_HISTORY_ROWS={history_rows} RACERS={history_racers}",
                flush=True,
            )

            for idx, day in enumerate(daterange(start, end), 1):
                calendar_days += 1
                prepared = prepare_day(helper, cur, day, history_keys, history_values)

                # Freeze BOTH variants and selectors before the first target-day result query.
                union_ids = sorted(
                    {
                        rid
                        for variant in ("control", "strict_prior_st")
                        for rid in selected_ids(prepared["selected"][variant])
                    }
                )
                results = helper.fetch_selected_results(cur, day, union_ids)

                flags = {
                    variant: evaluated(prepared, variant, results)
                    for variant in ("control", "strict_prior_st")
                }
                for variant, flag in flags.items():
                    status[variant]["EVALUATED_EXACT_SIX" if flag else "UNEVALUATED"] += 1

                if flags["control"]:
                    ids = selected_ids(prepared["selected"]["control"])
                    rid = ids[0]
                    result = results[rid]
                    actual = helper.norm_ticket(result.get("trifecta_ticket"))
                    payout = result.get("trifecta_payout_yen")
                    if actual is None or not isinstance(payout, int) or payout <= 0:
                        raise RuntimeError(f"malformed control rank1 result: {rid}")
                    count = int(prepared["meta"][rid]["prior_st_lane_count"])
                    for variant in ("control", "strict_prior_st"):
                        track_a[variant].append(
                            prediction_record(
                                day=day,
                                variant=variant,
                                race_id=rid,
                                probs=prepared["distributions"][variant][rid],
                                actual_ticket=actual,
                                payout_yen=payout,
                                selected_top6=ids,
                                prior_st_lane_count=count,
                            )
                        )

                for variant in ("control", "strict_prior_st"):
                    if not flags[variant]:
                        continue
                    ids = selected_ids(prepared["selected"][variant])
                    rid = ids[0]
                    result = results[rid]
                    actual = helper.norm_ticket(result.get("trifecta_ticket"))
                    payout = result.get("trifecta_payout_yen")
                    if actual is None or not isinstance(payout, int) or payout <= 0:
                        raise RuntimeError(f"malformed {variant} rank1 result: {rid}")
                    track_b[variant].append(
                        prediction_record(
                            day=day,
                            variant=variant,
                            race_id=rid,
                            probs=prepared["distributions"][variant][rid],
                            actual_ticket=actual,
                            payout_yen=payout,
                            selected_top6=ids,
                            prior_st_lane_count=int(prepared["meta"][rid]["prior_st_lane_count"]),
                        )
                    )

                if idx % 25 == 0:
                    print(
                        f"PROGRESS={day.isoformat()} control_days={len(track_b['control'])}",
                        flush=True,
                    )
        conn.rollback()

    control_dates = sorted(row["date"] for row in track_b["control"])
    if len(control_dates) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError(
            f"control evaluated-day drift: expected {EXPECTED_CONTROL_DAYS}, got {len(control_dates)}"
        )
    if len(track_a["control"]) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError("Track A control-day drift")
    bounds = block_bounds(control_dates)
    result = {
        "contract": "v4_strict_prior_st_missing_information_v1",
        "version": VERSION,
        "pinned_long_helper_sha": PINNED_LONG_HELPER_SHA,
        "preregistered_contract": contract_metadata(),
        "policy": {
            "db_transaction_read_only": True,
            "strict_prior_date": True,
            "same_day_results_allowed": False,
            "result_query_after_both_variant_freezes": True,
            "odds_used": False,
            "ev_used": False,
            "threshold_search": False,
            "coefficient_retune": False,
            "production_change": False,
            "line": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": calendar_days,
            "control_evaluated_days": len(control_dates),
            "prior_st_history_rows": history_rows,
            "prior_st_history_racers": history_racers,
            "status_by_variant": {k: dict(v) for k, v in status.items()},
        },
        "canonical_control_block_bounds": bounds,
        "track_a_fixed_control_rank1": summarize(track_a, bounds),
        "track_b_variant_reselection": summarize(track_b, bounds),
        "track_b_selector_overlap_vs_control": selector_overlap(track_b),
        "track_a_records": track_a,
        "track_b_records": track_b,
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    for label, summary in (
        ("TRACK_A", result["track_a_fixed_control_rank1"]),
        ("TRACK_B", result["track_b_variant_reselection"]),
    ):
        print(f"=== {label} BLOCKS_3_10 ===", flush=True)
        for variant in ("control", "strict_prior_st"):
            for stratum in ("all", "any", "full6"):
                row = summary[variant]["blocks_3_10"][stratum]
                print(
                    f"{variant} {stratum} DAYS={row['days']} "
                    f"HEAD_ACC={row['head_accuracy_percent']} "
                    f"LOGLOSS={row['head_log_loss']} BRIER={row['head_brier']} "
                    f"TOP2={row['formal_top2_hit_rate_percent']} "
                    f"ROI={row['roi_percent']} PROFIT={row['profit_yen']}",
                    flush=True,
                )
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
