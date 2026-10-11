# -*- coding: utf-8 -*-
"""One-shot read-only current-V4 exhibition-time-rank OOS replay.

All coefficient candidates for a target day are frozen before target-day
results are queried. Coefficients used in pure evaluation blocks are selected
only from strictly earlier canonical blocks.
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
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research.v4_exhibition_time_rank_contract import (
    BLOCKS,
    COEFFICIENT_GRID,
    END_DATE,
    EXHIBITION_SNAPSHOT_LABEL,
    EXPECTED_CONTROL_DAYS,
    FORMAL_TICKETS,
    MIN_LOGLOSS_BETTER_BLOCKS,
    MIN_POSITIVE_SELECTED_BLOCKS,
    PURE_EVAL_START_BLOCK,
    START_DATE,
    UNIT_YEN,
    adjust_base_raw,
    contract_metadata,
)

VERSION = "2026-09-27-v4-exhibition-time-rank-oos-v1"
PINNED_LONG_HELPER_SHA = "ac91c9a2e9570d3af3589e2e98b6529a77c14756"
OUTPUT_JSON = Path(
    os.getenv("V4_EXHIBITION_TIME_OUTPUT_JSON", "v4-exhibition-time-rank-oos.json")
)
LONG_HELPER_PATH = Path(
    os.getenv(
        "V4_LONG_HELPER_PATH",
        Path(__file__).resolve().parent / "v4_long_history_walkforward_pg.py",
    )
)
EPS = 1e-15


def load_long_helper():
    spec = importlib.util.spec_from_file_location("v4_exhibition_time_long_helper", LONG_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load long helper: {LONG_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
    if not bounds:
        raise ValueError("block bounds required")
    for item in bounds:
        if value <= str(item["end"]):
            return int(item["block"])
    return int(bounds[-1]["block"])


def coef_key(value: float) -> str:
    return f"ex_{value:.2f}"


def first_place_marginal(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in range(1, 7)}
    for ticket, prob in probs.items():
        lane = int(str(ticket).split("-", 1)[0])
        out[lane] += float(prob)
    total = sum(out.values())
    if total <= 0:
        raise RuntimeError("invalid first-place mass")
    return {lane: value / total for lane, value in out.items()}


def max_drawdown(profits: list[int]) -> int:
    running = peak = out = 0
    for profit in profits:
        running += profit
        peak = max(peak, running)
        out = max(out, peak - running)
    return out


def prediction_record(
    *,
    day: date,
    variant: str,
    coefficient: float,
    race_id: str,
    probs: Mapping[str, float],
    actual_ticket: str,
    payout_yen: int,
    selected_top6: list[str],
    exhibition_lane_count: int,
) -> dict[str, Any]:
    actual_head = int(actual_ticket.split("-", 1)[0])
    head = first_place_marginal(probs)
    predicted_head = min(range(1, 7), key=lambda lane: (-head[lane], lane))
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
        "coefficient": coefficient,
        "race_id": race_id,
        "selected_top6": selected_top6,
        "exhibition_lane_count": exhibition_lane_count,
        "predicted_head": predicted_head,
        "actual_head": actual_head,
        "head_correct": predicted_head == actual_head,
        "head_log_loss": -math.log(p_actual),
        "head_brier": brier,
        "formal_top2_hit": hit,
        "investment_yen": FORMAL_TICKETS * UNIT_YEN,
        "gross_return_yen": gross,
        "profit_yen": gross - FORMAL_TICKETS * UNIT_YEN,
    }


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
        "head_accuracy_percent": round(
            100.0 * sum(bool(r["head_correct"]) for r in rows) / n, 6
        ),
        "head_log_loss": round(
            sum(float(r["head_log_loss"]) for r in rows) / n, 9
        ),
        "head_brier": round(sum(float(r["head_brier"]) for r in rows) / n, 9),
        "formal_top2_hit_rate_percent": round(
            100.0 * sum(bool(r["formal_top2_hit"]) for r in rows) / n, 6
        ),
        "roi_percent": round(100.0 * gross / investment, 6) if investment else None,
        "profit_yen": gross - investment,
        "max_drawdown_yen": max_drawdown(profits),
    }


def complete_exhibition_ranks(rows: list[dict[str, Any]]) -> dict[int, int]:
    if len(rows) != 6:
        return {}
    out: dict[int, int] = {}
    for row in rows:
        try:
            lane = int(row.get("lane") or 0)
            rank = int(row.get("exhibition_time_rank") or 0)
        except Exception:
            return {}
        if lane not in range(1, 7) or rank not in range(1, 7) or lane in out:
            return {}
        out[lane] = rank
    if sorted(out) != [1, 2, 3, 4, 5, 6]:
        return {}
    if sorted(out.values()) != [1, 2, 3, 4, 5, 6]:
        return {}
    return out


def load_exhibition_rows(cur, race_ids: list[str]) -> tuple[dict[str, list[dict[str, Any]]], Counter]:
    if not race_ids:
        return {}, Counter()
    cur.execute(
        """
        select race_id::text race_id,lane,exhibition_time_rank,source
          from v2_realtime_exhibition_snapshots
         where race_id=any(%s)
           and snapshot_label=%s
         order by race_id,lane
        """,
        (race_ids, EXHIBITION_SNAPSHOT_LABEL),
    )
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sources: Counter = Counter()
    for row in cur.fetchall():
        item = dict(row)
        by[str(item["race_id"])].append(item)
        sources[str(item.get("source") or "")] += 1
    return dict(by), sources


def prepare_day(helper, cur, day: date) -> dict[str, Any]:
    races, entries_by, course_by, opponent_by = helper.fetch_day_inputs(cur, day)
    cutoff = helper.cutoff_for(day)
    race_ids = [str(row.get("race_id") or "") for row in races if row.get("race_id")]
    exhibition_by, source_counts = load_exhibition_rows(cur, race_ids)

    keys = ["control"] + [coef_key(value) for value in COEFFICIENT_GRID]
    distributions: dict[str, dict[str, dict[str, float]]] = {key: {} for key in keys}
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
        control = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        distributions["control"][rid] = control

        ranks = complete_exhibition_ranks(exhibition_by.get(rid, []))
        for coefficient in COEFFICIENT_GRID:
            distributions[coef_key(coefficient)][rid] = v4.build_v4_distribution(
                base_raw=adjust_base_raw(base, ranks, coefficient),
                course_top3=course,
                motor_place2=motor,
                opponent_delta=opponent,
            )
        meta[rid] = {
            "deadline_at": deadline,
            "exhibition_lane_count": 6 if ranks else 0,
        }

    selected = {
        key: v4.select_daily(
            distributions[key],
            race_cap=v4.CORE_RACES,
            ticket_count=v4.CORE_TICKETS,
        )
        for key in distributions
    }
    return {
        "distributions": distributions,
        "selected": selected,
        "meta": meta,
        "cutoff": cutoff,
        "source_counts": source_counts,
    }


def selected_ids(rows) -> list[str]:
    return [str(row["race_id"]) for row in rows]


def evaluated(prepared, key: str, results: Mapping[str, Any]) -> bool:
    rows = prepared["selected"][key]
    if len(rows) != v4.CORE_RACES:
        return False
    ids = selected_ids(rows)
    if any(prepared["meta"][rid]["deadline_at"] <= prepared["cutoff"] for rid in ids):
        return False
    return all(rid in results for rid in ids)


def metric_record_for(
    helper,
    *,
    day: date,
    key: str,
    coefficient: float,
    rid: str,
    probs: Mapping[str, float],
    selected_top6: list[str],
    meta: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    actual = helper.norm_ticket(result.get("trifecta_ticket"))
    payout = result.get("trifecta_payout_yen")
    if actual is None or not isinstance(payout, int) or payout <= 0:
        raise RuntimeError(f"malformed result: {rid}")
    return prediction_record(
        day=day,
        variant=key,
        coefficient=coefficient,
        race_id=rid,
        probs=probs,
        actual_ticket=actual,
        payout_yen=payout,
        selected_top6=selected_top6,
        exhibition_lane_count=int(meta["exhibition_lane_count"]),
    )


def select_coefficients(
    track_a: Mapping[str, list[dict[str, Any]]],
    bounds: list[dict[str, object]],
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1):
        scores: dict[float, dict[str, Any]] = {}
        for coefficient in COEFFICIENT_GRID:
            key = coef_key(coefficient)
            rows = [
                row
                for row in track_a[key]
                if block_for(str(row["date"]), bounds) < block
                and int(row["exhibition_lane_count"]) == 6
            ]
            if not rows:
                raise RuntimeError(
                    f"no prior full6 training rows for block {block} coefficient {coefficient}"
                )
            scores[coefficient] = {
                "n": len(rows),
                "head_log_loss": sum(float(row["head_log_loss"]) for row in rows) / len(rows),
            }
        best = min(
            COEFFICIENT_GRID,
            key=lambda coefficient: (scores[coefficient]["head_log_loss"], coefficient),
        )
        out[block] = {
            "coefficient": best,
            "training_rows": scores[best]["n"],
            "training_head_log_loss": round(scores[best]["head_log_loss"], 9),
            "grid_scores": {
                f"{coefficient:.2f}": {
                    "n": scores[coefficient]["n"],
                    "head_log_loss": round(scores[coefficient]["head_log_loss"], 9),
                }
                for coefficient in COEFFICIENT_GRID
            },
        }
    return out


def chosen_rows(
    rows_by_key: Mapping[str, list[dict[str, Any]]],
    bounds: list[dict[str, object]],
    selected: Mapping[int, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    control = [
        row
        for row in rows_by_key["control"]
        if block_for(str(row["date"]), bounds) >= PURE_EVAL_START_BLOCK
    ]
    chosen: list[dict[str, Any]] = []
    by_key_date = {
        key: {str(row["date"]): row for row in rows}
        for key, rows in rows_by_key.items()
        if key != "control"
    }
    for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1):
        coefficient = float(selected[block]["coefficient"])
        key = coef_key(coefficient)
        for day, row in sorted(by_key_date[key].items()):
            if block_for(day, bounds) == block:
                chosen.append(row)
    return control, chosen


def block_metrics(
    control_rows: list[dict[str, Any]],
    chosen_rows_: list[dict[str, Any]],
    bounds: list[dict[str, object]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1):
        c = [r for r in control_rows if block_for(str(r["date"]), bounds) == block]
        v = [r for r in chosen_rows_ if block_for(str(r["date"]), bounds) == block]
        out[str(block)] = {
            "control": aggregate(c),
            "exhibition_time_rank": aggregate(v),
        }
    return out


def selector_overlap(
    control_rows: list[dict[str, Any]],
    chosen_rows_: list[dict[str, Any]],
) -> dict[str, Any]:
    control = {str(row["date"]): row for row in control_rows}
    variant = {str(row["date"]): row for row in chosen_rows_}
    common = sorted(set(control) & set(variant))
    rank1_same = sum(control[d]["race_id"] == variant[d]["race_id"] for d in common)
    top6 = [
        len(set(control[d]["selected_top6"]) & set(variant[d]["selected_top6"])) / 6.0
        for d in common
    ]
    return {
        "common_days": len(common),
        "rank1_same_days": rank1_same,
        "rank1_overlap_percent": round(100.0 * rank1_same / len(common), 6)
        if common
        else None,
        "mean_top6_overlap_percent": round(100.0 * sum(top6) / len(top6), 6)
        if top6
        else None,
    }


def paired_head_changes(
    control_rows: list[dict[str, Any]],
    chosen_rows_: list[dict[str, Any]],
) -> dict[str, int]:
    control = {str(row["date"]): row for row in control_rows}
    variant = {str(row["date"]): row for row in chosen_rows_}
    common = sorted(set(control) & set(variant))
    return {
        "common_days": len(common),
        "predicted_head_changed": sum(
            int(control[d]["predicted_head"]) != int(variant[d]["predicted_head"])
            for d in common
        ),
        "control_wrong_variant_right": sum(
            (not bool(control[d]["head_correct"])) and bool(variant[d]["head_correct"])
            for d in common
        ),
        "control_right_variant_wrong": sum(
            bool(control[d]["head_correct"]) and (not bool(variant[d]["head_correct"]))
            for d in common
        ),
    }


def summarize_with_strata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "all": aggregate(rows),
        "full6": aggregate(
            [row for row in rows if int(row["exhibition_lane_count"]) == 6]
        ),
    }


def support_gate(
    track_a_control: list[dict[str, Any]],
    track_a_variant: list[dict[str, Any]],
    track_b_control: list[dict[str, Any]],
    track_b_variant: list[dict[str, Any]],
    blocks: Mapping[str, Any],
    selections: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    a0 = aggregate(track_a_control)
    a1 = aggregate(track_a_variant)
    b0 = aggregate(track_b_control)
    b1 = aggregate(track_b_variant)
    better_blocks = sum(
        blocks[str(block)]["exhibition_time_rank"]["head_log_loss"]
        < blocks[str(block)]["control"]["head_log_loss"]
        for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1)
    )
    positive_blocks = sum(
        float(selections[block]["coefficient"]) > 0.0
        for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1)
    )
    checks = {
        "track_a_logloss_better": a1["head_log_loss"] < a0["head_log_loss"],
        "track_a_brier_better": a1["head_brier"] < a0["head_brier"],
        "track_a_head_accuracy_better": (
            a1["head_accuracy_percent"] > a0["head_accuracy_percent"]
        ),
        "track_a_logloss_better_blocks": better_blocks >= MIN_LOGLOSS_BETTER_BLOCKS,
        "positive_coefficient_blocks": positive_blocks >= MIN_POSITIVE_SELECTED_BLOCKS,
        "track_b_logloss_not_worse": b1["head_log_loss"] <= b0["head_log_loss"],
        "track_b_brier_not_worse": b1["head_brier"] <= b0["head_brier"],
        "track_b_head_accuracy_not_worse": (
            b1["head_accuracy_percent"] >= b0["head_accuracy_percent"]
        ),
    }
    return {
        "checks": checks,
        "track_a_logloss_better_blocks": better_blocks,
        "positive_coefficient_blocks": positive_blocks,
        "supports_new_forward_research": all(checks.values()),
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    helper = load_long_helper()
    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)

    print(f"V4_EXHIBITION_TIME_VERSION={VERSION}", flush=True)
    print(f"PINNED_LONG_HELPER_SHA={PINNED_LONG_HELPER_SHA}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY EXHIBITION_TIME_RANK_ONLY GRID_0_005_010_020 "
        "TRAIN_PRIOR_BLOCKS_ONLY RESULT_AFTER_ALL_VARIANT_FREEZE NO_ODDS NO_EV "
        "NO_POST_RESULT_FILTER NO_PRODUCTION PURCHASE_FALSE",
        flush=True,
    )

    keys = ["control"] + [coef_key(value) for value in COEFFICIENT_GRID]
    track_a: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    track_b: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    status: dict[str, Counter] = {key: Counter() for key in keys}
    source_counts: Counter = Counter()
    calendar_days = 0

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='25min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for idx, day in enumerate(daterange(start, end), 1):
                calendar_days += 1
                prepared = prepare_day(helper, cur, day)
                source_counts.update(prepared["source_counts"])

                # Freeze control + ALL four coefficient candidates and selectors
                # before the first target-day result query.
                union_ids = sorted(
                    {
                        rid
                        for key in keys
                        for rid in selected_ids(prepared["selected"][key])
                    }
                )
                results = helper.fetch_selected_results(cur, day, union_ids)

                flags = {key: evaluated(prepared, key, results) for key in keys}
                for key, flag in flags.items():
                    status[key]["EVALUATED_EXACT_SIX" if flag else "UNEVALUATED"] += 1

                if flags["control"]:
                    control_ids = selected_ids(prepared["selected"]["control"])
                    rid = control_ids[0]
                    result = results[rid]
                    for key in keys:
                        coefficient = (
                            0.0 if key == "control" else float(key.removeprefix("ex_"))
                        )
                        track_a[key].append(
                            metric_record_for(
                                helper,
                                day=day,
                                key=key,
                                coefficient=coefficient,
                                rid=rid,
                                probs=prepared["distributions"][key][rid],
                                selected_top6=control_ids,
                                meta=prepared["meta"][rid],
                                result=result,
                            )
                        )

                for key in keys:
                    if not flags[key]:
                        continue
                    ids = selected_ids(prepared["selected"][key])
                    rid = ids[0]
                    coefficient = (
                        0.0 if key == "control" else float(key.removeprefix("ex_"))
                    )
                    track_b[key].append(
                        metric_record_for(
                            helper,
                            day=day,
                            key=key,
                            coefficient=coefficient,
                            rid=rid,
                            probs=prepared["distributions"][key][rid],
                            selected_top6=ids,
                            meta=prepared["meta"][rid],
                            result=results[rid],
                        )
                    )

                if idx % 25 == 0:
                    print(
                        f"PROGRESS={day.isoformat()} control_days={len(track_b['control'])}",
                        flush=True,
                    )
        conn.rollback()

    control_dates = sorted(str(row["date"]) for row in track_b["control"])
    if len(control_dates) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError(
            f"control evaluated-day drift: expected {EXPECTED_CONTROL_DAYS}, got {len(control_dates)}"
        )
    if len(track_a["control"]) != EXPECTED_CONTROL_DAYS:
        raise RuntimeError("Track A control-day drift")

    bounds = block_bounds(control_dates)
    selections = select_coefficients(track_a, bounds)

    a_control, a_variant = chosen_rows(track_a, bounds, selections)
    b_control, b_variant = chosen_rows(track_b, bounds, selections)
    a_blocks = block_metrics(a_control, a_variant, bounds)
    b_blocks = block_metrics(b_control, b_variant, bounds)
    gate = support_gate(
        a_control,
        a_variant,
        b_control,
        b_variant,
        a_blocks,
        selections,
    )

    result = {
        "contract": "current_v4_exhibition_time_rank_missing_information_v1",
        "version": VERSION,
        "pinned_long_helper_sha": PINNED_LONG_HELPER_SHA,
        "preregistered_contract": contract_metadata(),
        "policy": {
            "db_transaction_read_only": True,
            "historical_snapshot_is_prospective_timing_proof": False,
            "all_candidate_variants_frozen_before_target_results": True,
            "coefficient_training_prior_blocks_only": True,
            "odds_used": False,
            "ev_used": False,
            "threshold_search": False,
            "post_result_subgroup_adoption": False,
            "production_change": False,
            "line": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": calendar_days,
            "control_evaluated_days": len(control_dates),
            "status_by_key": {key: dict(value) for key, value in status.items()},
            "historical_source_row_counts": dict(source_counts),
        },
        "canonical_control_block_bounds": bounds,
        "selected_coefficients_by_block": {
            str(block): value for block, value in selections.items()
        },
        "track_a_fixed_control_rank1": {
            "control": summarize_with_strata(a_control),
            "exhibition_time_rank": summarize_with_strata(a_variant),
            "blocks": a_blocks,
            "paired_head_changes": paired_head_changes(a_control, a_variant),
        },
        "track_b_variant_reselection": {
            "control": summarize_with_strata(b_control),
            "exhibition_time_rank": summarize_with_strata(b_variant),
            "blocks": b_blocks,
            "selector_overlap": selector_overlap(b_control, b_variant),
        },
        "support_gate": gate,
        "track_a_candidate_records": track_a,
        "track_b_candidate_records": track_b,
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== COEFFICIENTS ===", flush=True)
    for block in range(PURE_EVAL_START_BLOCK, BLOCKS + 1):
        row = selections[block]
        print(
            f"BLOCK={block} COEF={row['coefficient']:.2f} "
            f"TRAIN_N={row['training_rows']} TRAIN_LL={row['training_head_log_loss']}",
            flush=True,
        )

    print("=== TRACK_A BLOCKS_3_10 ===", flush=True)
    for name, rows in (("control", a_control), ("exhibition_time_rank", a_variant)):
        for stratum, summary in summarize_with_strata(rows).items():
            print(
                f"{name} {stratum} DAYS={summary['days']} "
                f"HEAD_ACC={summary['head_accuracy_percent']} "
                f"LOGLOSS={summary['head_log_loss']} BRIER={summary['head_brier']} "
                f"TOP2={summary['formal_top2_hit_rate_percent']} "
                f"ROI={summary['roi_percent']} PROFIT={summary['profit_yen']}",
                flush=True,
            )

    print("=== TRACK_B BLOCKS_3_10 ===", flush=True)
    for name, rows in (("control", b_control), ("exhibition_time_rank", b_variant)):
        summary = aggregate(rows)
        print(
            f"{name} DAYS={summary['days']} HEAD_ACC={summary['head_accuracy_percent']} "
            f"LOGLOSS={summary['head_log_loss']} BRIER={summary['head_brier']} "
            f"TOP2={summary['formal_top2_hit_rate_percent']} "
            f"ROI={summary['roi_percent']} PROFIT={summary['profit_yen']}",
            flush=True,
        )

    print(
        "V4_EXHIBITION_TIME_GATE="
        + ("SUPPORTS_NEW_FORWARD_RESEARCH" if gate["supports_new_forward_research"] else "NO_FORWARD_SUPPORT"),
        flush=True,
    )
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
