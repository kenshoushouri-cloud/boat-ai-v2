# -*- coding: utf-8 -*-
"""One-shot read-only V4 input-information ablation replay.

This implements PR #387 exactly:
- frozen variants: control / no_course / no_opponent / no_motor / base_only;
- Track A evaluates every variant on the same control daily-rank-1 race;
- Track B lets the unchanged current select_daily choose each variant's own rank1;
- all variant distributions and selections are frozen before any result query;
- PostgreSQL transaction is READ ONLY;
- no odds/EV, retune, threshold search, DB write, LINE, or purchase action.

Historical input-loading/timing helpers are pinned to the immutable PR #378 helper
commit used by the canonical long-history replay.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research.v4_input_ablation_contract import (
    BLOCKS,
    END_DATE,
    FORMAL_TICKETS,
    PURE_EVAL_START_BLOCK,
    START_DATE,
    UNIT_YEN,
    VARIANTS,
    contract_metadata,
    variant_inputs,
)

VERSION = "2026-09-25 v4-input-ablation-replay-v1"
PINNED_LONG_HELPER_SHA = "ac91c9a2e9570d3af3589e2e98b6529a77c14756"
EXPECTED_CONTROL_DAYS = 432
OUTPUT_JSON = Path(
    os.getenv("V4_INPUT_ABLATION_OUTPUT_JSON", "v4-input-ablation-replay.json")
)
LONG_HELPER_PATH = Path(
    os.getenv(
        "V4_LONG_HELPER_PATH",
        ".v4-long-helper/research/v4_long_history_walkforward_pg.py",
    )
)
EPS = 1e-15


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def load_long_helper():
    if not LONG_HELPER_PATH.is_file():
        raise RuntimeError(f"pinned long-history helper missing: {LONG_HELPER_PATH}")
    spec = importlib.util.spec_from_file_location(
        "v4_long_history_walkforward_pinned", LONG_HELPER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pinned long-history helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def first_place_marginal(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in probs.items():
        lane = int(str(ticket).split("-", 1)[0])
        out[lane] += float(prob)
    total = sum(out.values())
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("invalid first-place marginal")
    return {lane: value / total for lane, value in out.items()}


def max_drawdown(profits: list[int]) -> int:
    running = 0
    peak = 0
    drawdown = 0
    for profit in profits:
        running += int(profit)
        peak = max(peak, running)
        drawdown = max(drawdown, peak - running)
    return drawdown


def split_blocks(days: list[str], blocks: int = BLOCKS) -> list[set[str]]:
    if not days:
        return []
    blocks = min(blocks, len(days))
    base, extra = divmod(len(days), blocks)
    out: list[set[str]] = []
    start = 0
    for idx in range(blocks):
        size = base + (1 if idx < extra else 0)
        out.append(set(days[start : start + size]))
        start += size
    return out


def canonical_block_bounds(control_dates: list[str]) -> list[dict[str, Any]]:
    groups = split_blocks(sorted(control_dates), BLOCKS)
    return [
        {
            "block": idx,
            "start_date": min(group),
            "end_date": max(group),
            "control_days": len(group),
        }
        for idx, group in enumerate(groups, 1)
    ]


def block_for_date(day: str, bounds: list[dict[str, Any]]) -> int:
    if not bounds:
        raise ValueError("block bounds required")
    for row in bounds:
        if day <= row["end_date"]:
            return int(row["block"])
    return int(bounds[-1]["block"])


def prediction_record(
    *,
    day: date,
    variant: str,
    race_id: str,
    probs: Mapping[str, float],
    actual_ticket: str,
    payout_yen: int,
    selected_top6: list[str],
    meta: Mapping[str, Any],
) -> dict[str, Any]:
    first = first_place_marginal(probs)
    actual_first = int(actual_ticket.split("-", 1)[0])
    predicted_first = sorted(first.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    p_actual = max(EPS, min(1.0, first[actual_first]))
    log_loss = -math.log(p_actual)
    brier = sum(
        (first[lane] - (1.0 if lane == actual_first else 0.0)) ** 2
        for lane in v4.LANES
    )
    top2 = list(v4.top_tickets(probs, FORMAL_TICKETS))
    hit = actual_ticket in top2
    gross = int(payout_yen) if hit else 0
    investment = FORMAL_TICKETS * UNIT_YEN
    return {
        "date": day.isoformat(),
        "variant": variant,
        "race_id": race_id,
        "predicted_first": predicted_first,
        "actual_first": actual_first,
        "head_correct": predicted_first == actual_first,
        "head_log_loss": float(log_loss),
        "head_brier": float(brier),
        "formal_top2": top2,
        "actual_trifecta": actual_ticket,
        "top2_hit": bool(hit),
        "payout_yen": int(payout_yen),
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "selected_top6": list(selected_top6),
        "course_lane_count": int(meta["course_lane_count"]),
        "opponent_available": bool(meta["opponent_available"]),
        "motor_available": bool(meta["motor_available"]),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    investment = sum(int(row["investment_yen"]) for row in rows)
    gross = sum(int(row["gross_return_yen"]) for row in rows)
    return {
        "days": n,
        "top1_head_accuracy_percent": round(
            100.0 * sum(int(bool(row["head_correct"])) for row in rows) / n, 3
        )
        if n
        else None,
        "head_log_loss": round(
            sum(float(row["head_log_loss"]) for row in rows) / n, 6
        )
        if n
        else None,
        "head_brier": round(sum(float(row["head_brier"]) for row in rows) / n, 6)
        if n
        else None,
        "formal_top2_hit_rate_percent": round(
            100.0 * sum(int(bool(row["top2_hit"])) for row in rows) / n, 3
        )
        if n
        else None,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(100.0 * gross / investment, 3) if investment else None,
        "profitable_day_rate_percent": round(
            100.0 * sum(int(int(row["profit_yen"]) > 0) for row in rows) / n, 3
        )
        if n
        else None,
        "max_drawdown_yen": max_drawdown(
            [int(row["profit_yen"]) for row in sorted(rows, key=lambda x: x["date"])]
        ),
        "feature_coverage": {
            "course_any_days": sum(int(int(row["course_lane_count"]) > 0) for row in rows),
            "course_full6_days": sum(int(int(row["course_lane_count"]) == 6) for row in rows),
            "opponent_days": sum(int(bool(row["opponent_available"])) for row in rows),
            "motor_days": sum(int(bool(row["motor_available"])) for row in rows),
        },
    }


def summarize(rows_by_variant: dict[str, list[dict[str, Any]]], bounds):
    out: dict[str, Any] = {}
    for variant in VARIANTS:
        rows = [dict(row, block=block_for_date(row["date"], bounds)) for row in rows_by_variant[variant]]
        blocks = {
            str(block): aggregate([row for row in rows if row["block"] == block])
            for block in range(1, BLOCKS + 1)
        }
        out[variant] = {
            "all_period": aggregate(rows),
            "blocks_3_10": aggregate(
                [row for row in rows if row["block"] >= PURE_EVAL_START_BLOCK]
            ),
            "blocks": blocks,
        }
    return out


def metric_delta(current, control) -> dict[str, Any]:
    keys = (
        "top1_head_accuracy_percent",
        "head_log_loss",
        "head_brier",
        "formal_top2_hit_rate_percent",
        "roi_percent",
        "profit_yen",
    )
    out = {}
    for key in keys:
        a = current.get(key)
        b = control.get(key)
        out[key] = None if a is None or b is None else round(float(a) - float(b), 6)
    return out


def add_deltas(summary: dict[str, Any]) -> dict[str, Any]:
    control_all = summary["control"]["all_period"]
    control_pure = summary["control"]["blocks_3_10"]
    for variant in VARIANTS:
        summary[variant]["delta_vs_control"] = {
            "all_period": metric_delta(summary[variant]["all_period"], control_all),
            "blocks_3_10": metric_delta(summary[variant]["blocks_3_10"], control_pure),
        }
        if variant == "control":
            continue
        stable = {
            "compared_blocks": 0,
            "head_accuracy_better_blocks": 0,
            "log_loss_better_blocks": 0,
            "brier_better_blocks": 0,
        }
        for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1):
            a = summary[variant]["blocks"][str(block)]
            c = summary["control"]["blocks"][str(block)]
            if not a["days"] or not c["days"]:
                continue
            stable["compared_blocks"] += 1
            stable["head_accuracy_better_blocks"] += int(
                a["top1_head_accuracy_percent"] > c["top1_head_accuracy_percent"]
            )
            stable["log_loss_better_blocks"] += int(
                a["head_log_loss"] < c["head_log_loss"]
            )
            stable["brier_better_blocks"] += int(a["head_brier"] < c["head_brier"])
        summary[variant]["blocks_3_10_stability_vs_control"] = stable
    return summary


def selector_overlap(rows_by_variant: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    control = {row["date"]: row for row in rows_by_variant["control"]}
    out: dict[str, Any] = {}
    for variant in VARIANTS:
        rows = {row["date"]: row for row in rows_by_variant[variant]}
        common = sorted(set(control) & set(rows))
        rank1_same = sum(int(rows[d]["race_id"] == control[d]["race_id"]) for d in common)
        top6_fracs = [
            len(set(rows[d]["selected_top6"]) & set(control[d]["selected_top6"])) / 6.0
            for d in common
        ]
        out[variant] = {
            "common_evaluable_days_with_control": len(common),
            "rank1_same_days": rank1_same,
            "rank1_overlap_percent": round(100.0 * rank1_same / len(common), 3)
            if common
            else None,
            "mean_top6_overlap_percent": round(
                100.0 * sum(top6_fracs) / len(top6_fracs), 3
            )
            if top6_fracs
            else None,
        }
    return out


def prepare_day(helper, cur, day: date) -> dict[str, Any]:
    races, entries_by, course_by, opponent_by = helper.fetch_day_inputs(cur, day)
    cutoff = helper.cutoff_for(day)
    distributions = {variant: {} for variant in VARIANTS}
    meta: dict[str, dict[str, Any]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = helper.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue

        base = helper.base_raw(entries, str(race.get("venue_id") or ""))
        course = helper.course_map(
            entries=entries,
            deadline=deadline,
            cutoff=cutoff,
            course_by=course_by,
        )
        opponent = helper.opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = helper.motor_map(entries)
        meta[rid] = {
            "deadline_at": deadline,
            "course_lane_count": len(course),
            "opponent_available": opponent is not None,
            "motor_available": bool(motor),
        }
        for variant in VARIANTS:
            inputs = variant_inputs(
                variant,
                course_top3=course,
                opponent_delta=opponent,
                motor_place2=motor,
            )
            distributions[variant][rid] = v4.build_v4_distribution(
                base_raw=base,
                **inputs,
            )

    selected = {
        variant: v4.select_daily(
            distributions[variant],
            race_cap=v4.CORE_RACES,
            ticket_count=v4.CORE_TICKETS,
        )
        for variant in VARIANTS
    }
    return {
        "cutoff": cutoff,
        "distributions": distributions,
        "meta": meta,
        "selected": selected,
    }


def selected_ids(selected_rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["race_id"]) for row in selected_rows]


def evaluable_status(prepared, variant: str, results: Mapping[str, Any]) -> str:
    selected = prepared["selected"][variant]
    if len(selected) != v4.CORE_RACES:
        return "UNEVALUABLE_NOT_EXACT_SIX_SELECTED"
    ids = selected_ids(selected)
    if any(
        prepared["meta"][rid]["deadline_at"] <= prepared["cutoff"]
        for rid in ids
    ):
        return "UNEVALUABLE_SELECTED_DEADLINE_AT_OR_BEFORE_CUTOFF"
    if any(rid not in results for rid in ids):
        return "UNEVALUABLE_MISSING_OFFICIAL_SELECTED_RESULT"
    return "EVALUATED_EXACT_SIX"


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    helper = load_long_helper()
    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)

    print(f"V4_INPUT_ABLATION_VERSION={VERSION}", flush=True)
    print(f"PINNED_LONG_HELPER_SHA={PINNED_LONG_HELPER_SHA}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY ALL_VARIANTS_FROZEN_BEFORE_RESULT "
        "NO_ODDS NO_EV NO_THRESHOLD_SEARCH NO_RETUNE PURCHASE_FALSE",
        flush=True,
    )

    track_a = {variant: [] for variant in VARIANTS}
    track_b = {variant: [] for variant in VARIANTS}
    status_counts = {variant: Counter() for variant in VARIANTS}
    calendar_days = 0

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='20min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for idx, day in enumerate(daterange(start, end), 1):
                calendar_days += 1

                # Freeze every variant distribution + selector output before result access.
                prepared = prepare_day(helper, cur, day)
                frozen_union = sorted(
                    {
                        rid
                        for variant in VARIANTS
                        for rid in selected_ids(prepared["selected"][variant])
                    }
                )

                # The first result access is intentionally after every variant freeze.
                results = helper.fetch_selected_results(cur, day, frozen_union)

                statuses = {
                    variant: evaluable_status(prepared, variant, results)
                    for variant in VARIANTS
                }
                for variant, status in statuses.items():
                    status_counts[variant][status] += 1

                if statuses["control"] == "EVALUATED_EXACT_SIX":
                    control_selected = prepared["selected"]["control"]
                    control_ids = selected_ids(control_selected)
                    rid = control_ids[0]
                    result = results[rid]
                    actual = helper.norm_ticket(result.get("trifecta_ticket"))
                    payout = result.get("trifecta_payout_yen")
                    if actual is None or not isinstance(payout, int) or payout <= 0:
                        raise RuntimeError(f"malformed control rank1 result: {rid}")
                    for variant in VARIANTS:
                        track_a[variant].append(
                            prediction_record(
                                day=day,
                                variant=variant,
                                race_id=rid,
                                probs=prepared["distributions"][variant][rid],
                                actual_ticket=actual,
                                payout_yen=payout,
                                selected_top6=control_ids,
                                meta=prepared["meta"][rid],
                            )
                        )

                for variant in VARIANTS:
                    if statuses[variant] != "EVALUATED_EXACT_SIX":
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
                            meta=prepared["meta"][rid],
                        )
                    )

                if idx % 25 == 0:
                    print(
                        f"PROGRESS={day.isoformat()} control_days="
                        f"{len(track_b['control'])}",
                        flush=True,
                    )

        conn.rollback()

    control_dates = sorted(row["date"] for row in track_b["control"])
    if len(control_dates) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError(
            f"control evaluated-day drift: expected {EXPECTED_CONTROL_DAYS}, "
            f"got {len(control_dates)}"
        )
    if len(track_a["control"]) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError("Track A control-day drift")

    bounds = canonical_block_bounds(control_dates)
    track_a_summary = add_deltas(summarize(track_a, bounds))
    track_b_summary = add_deltas(summarize(track_b, bounds))
    overlap = selector_overlap(track_b)

    result = {
        "contract": "v4_input_information_ablation_replay_v1",
        "version": VERSION,
        "pinned_long_helper_sha": PINNED_LONG_HELPER_SHA,
        "preregistered_contract": contract_metadata(),
        "policy": {
            "db_transaction_read_only": True,
            "result_query_after_all_variant_freezes": True,
            "odds_used": False,
            "ev_used": False,
            "threshold_search": False,
            "coefficient_retune": False,
            "new_feature": False,
            "production_change": False,
            "line": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": calendar_days,
            "control_evaluated_days": len(control_dates),
            "track_a_days_by_variant": {
                variant: len(track_a[variant]) for variant in VARIANTS
            },
            "track_b_days_by_variant": {
                variant: len(track_b[variant]) for variant in VARIANTS
            },
            "status_counts_by_variant": {
                variant: dict(sorted(status_counts[variant].items()))
                for variant in VARIANTS
            },
        },
        "canonical_control_block_bounds": bounds,
        "track_a_fixed_control_rank1": track_a_summary,
        "track_b_variant_reselection": track_b_summary,
        "track_b_selector_overlap_vs_control": overlap,
        "track_a_records": track_a,
        "track_b_records": track_b,
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    for track_name, summary in (
        ("TRACK_A", track_a_summary),
        ("TRACK_B", track_b_summary),
    ):
        print(f"=== {track_name} BLOCKS_3_10 ===", flush=True)
        for variant in VARIANTS:
            row = summary[variant]["blocks_3_10"]
            print(
                f"{variant} DAYS={row['days']} "
                f"HEAD_ACC={row['top1_head_accuracy_percent']} "
                f"LOGLOSS={row['head_log_loss']} "
                f"BRIER={row['head_brier']} "
                f"TOP2={row['formal_top2_hit_rate_percent']} "
                f"ROI={row['roi_percent']} PROFIT={row['profit_yen']}",
                flush=True,
            )

    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
