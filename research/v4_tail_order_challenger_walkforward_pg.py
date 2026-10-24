# -*- coding: utf-8 -*-
"""Read-only V4 second/third-order challenger walk-forward.

The current V4 daily six-race selection and first-place probability marginal are
held fixed. Challengers only reweight second/third ordering with an additional
pre-result place2 signal built from national/local place2 rates.

Every candidate top-two set is frozen before any result/payout access.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist

VERSION = "2026-09-23 v4-tail-order-challenger-v1"
START_DATE = date.fromisoformat(os.getenv("V4_TAIL_BT_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("V4_TAIL_BT_END_DATE", "2026-09-22"))
BLOCKS = int(os.getenv("V4_TAIL_BT_BLOCKS", "10"))
UNIT_YEN = 100
OUTPUT_JSON = Path(
    os.getenv("V4_TAIL_BT_OUTPUT_JSON", "v4-tail-order-challenger-walkforward.json")
)

# name -> (boost, second_weight, third_weight)
CANDIDATES: dict[str, tuple[float, float, float]] = {
    "control": (0.0, 0.0, 0.0),
    "p2_b010_s100_t050": (0.10, 1.00, 0.50),
    "p2_b020_s100_t050": (0.20, 1.00, 0.50),
    "p2_b030_s100_t050": (0.30, 1.00, 0.50),
    "p2_b040_s100_t050": (0.40, 1.00, 0.50),
    "p2_b050_s100_t050": (0.50, 1.00, 0.50),
    "p2_b030_s100_t100": (0.30, 1.00, 1.00),
    "p2_b030_s150_t050": (0.30, 1.50, 0.50),
    "p2_b030_s050_t100": (0.30, 0.50, 1.00),
}

if BLOCKS < 2:
    raise RuntimeError("V4_TAIL_BT_BLOCKS must be >= 2")
if END_DATE < START_DATE:
    raise RuntimeError("invalid tail backtest period")
if len(CANDIDATES) != 9:
    raise RuntimeError("tail candidate family drift")


def zscore6(values: Mapping[int, float]) -> dict[int, float]:
    xs = [float(values[lane]) for lane in v4.LANES]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd < 1e-12:
        return {lane: 0.0 for lane in v4.LANES}
    return {lane: (float(values[lane]) - mean) / sd for lane in v4.LANES}


def place2_signal(entries: list[dict[str, Any]]) -> dict[int, float]:
    by_lane = {int(row.get("lane") or 0): row for row in entries}
    if set(by_lane) != set(v4.LANES):
        raise ValueError("six lanes required")
    nat = {}
    local = {}
    for lane in v4.LANES:
        row = by_lane[lane]
        nat_value = hist.finite(row.get("national_place2_rate"))
        loc_value = hist.finite(row.get("local_place2_rate"))
        nat[lane] = 32.0 if nat_value is None else nat_value
        local[lane] = 30.0 if loc_value is None else loc_value
    zn = zscore6(nat)
    zl = zscore6(local)
    return {lane: (zn[lane] + zl[lane]) / 2.0 for lane in v4.LANES}


def head_masses(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in probs.items():
        out[int(str(ticket).split("-", 1)[0])] += float(prob)
    return out


def reweight_tail_preserve_head(
    control_probs: Mapping[str, float],
    signal: Mapping[int, float],
    *,
    boost: float,
    second_weight: float,
    third_weight: float,
) -> dict[str, float]:
    control = v4._normalize_tickets(control_probs)
    if boost == 0.0:
        return dict(control)
    original_heads = head_masses(control)
    out: dict[str, float] = {}
    for head in v4.LANES:
        group: list[tuple[str, float]] = []
        for ticket, prob in control.items():
            a, b, c = (int(x) for x in ticket.split("-"))
            if a != head:
                continue
            factor = math.exp(
                boost
                * (
                    second_weight * float(signal[b])
                    + third_weight * float(signal[c])
                )
            )
            group.append((ticket, float(prob) * factor))
        subtotal = sum(value for _, value in group)
        if subtotal <= 0:
            raise RuntimeError("invalid tail reweight subtotal")
        scale = original_heads[head] / subtotal
        for ticket, value in group:
            out[ticket] = value * scale

    if len(out) != 120:
        raise RuntimeError("tail reweight must preserve 120 tickets")
    after_heads = head_masses(out)
    for lane in v4.LANES:
        if abs(after_heads[lane] - original_heads[lane]) > 1e-12:
            raise RuntimeError("first-place marginal drift")
    return v4._normalize_tickets(out)


def build_day(
    cur: psycopg.Cursor[Any], day: date
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[int, float]],
    list[dict[str, Any]],
]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    control_distributions: dict[str, dict[str, float]] = {}
    signals: dict[str, dict[int, float]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        try:
            base = hist.base_raw(entries, str(race.get("venue_id") or ""))
            signal = place2_signal(entries)
        except Exception:
            continue
        course = hist.course_map(
            entries=entries,
            deadline=deadline,
            cutoff=cutoff,
            course_by=course_by,
        )
        opponent = hist.opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = hist.motor_map(entries)
        control_distributions[rid] = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        signals[rid] = signal

    selected = v4.select_daily(
        control_distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )
    return control_distributions, signals, selected


def freeze_candidate_tickets(
    control_distributions: Mapping[str, Mapping[str, float]],
    signals: Mapping[str, Mapping[int, float]],
    selected: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, dict[str, float]]],
    dict[str, dict[str, list[str]]],
]:
    candidate_probs: dict[str, dict[str, dict[str, float]]] = {
        name: {} for name in CANDIDATES
    }
    frozen_top2: dict[str, dict[str, list[str]]] = {
        name: {} for name in CANDIDATES
    }
    for row in selected:
        rid = str(row["race_id"])
        control = control_distributions[rid]
        for name, (boost, w2, w3) in CANDIDATES.items():
            probs = reweight_tail_preserve_head(
                control,
                signals[rid],
                boost=boost,
                second_weight=w2,
                third_weight=w3,
            )
            candidate_probs[name][rid] = probs
            frozen_top2[name][rid] = list(v4.top_tickets(probs, 2))
        if frozen_top2["control"][rid] != list(row["tickets"]):
            raise RuntimeError(f"control Top2 reproduction drift: {rid}")
    return candidate_probs, frozen_top2


def evaluate_day(
    *,
    day: date,
    selected: list[dict[str, Any]],
    candidate_probs: Mapping[str, Mapping[str, Mapping[str, float]]],
    frozen_top2: Mapping[str, Mapping[str, list[str]]],
    results: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]] | None:
    if len(selected) != v4.CORE_RACES:
        return None
    ids = [str(row["race_id"]) for row in selected]
    parsed_results: dict[str, tuple[str, int]] = {}
    for rid in ids:
        result = results.get(rid)
        if not result:
            return None
        actual = hist.norm_ticket(result.get("trifecta_ticket"))
        payout = int(result.get("trifecta_payout_yen") or 0)
        if actual is None or payout <= 0:
            return None
        parsed_results[rid] = (actual, payout)

    metrics: dict[str, dict[str, Any]] = {}
    for name in CANDIDATES:
        gross = top1_hits = top2_hits = 0
        log_loss_sum = actual_prob_sum = 0.0
        for rid in ids:
            actual, payout = parsed_results[rid]
            top2 = frozen_top2[name][rid]
            probs = candidate_probs[name][rid]
            actual_prob = float(probs.get(actual, 0.0))
            if actual_prob <= 0.0 or not math.isfinite(actual_prob):
                raise RuntimeError("invalid actual probability")
            top1_hit = actual == top2[0]
            top2_hit = actual in top2
            top1_hits += int(top1_hit)
            top2_hits += int(top2_hit)
            gross += payout if top2_hit else 0
            log_loss_sum += -math.log(max(actual_prob, 1e-15))
            actual_prob_sum += actual_prob
        metrics[name] = {
            "date": day.isoformat(),
            "races": len(ids),
            "investment_yen": len(ids) * 2 * UNIT_YEN,
            "gross_return_yen": gross,
            "profit_yen": gross - len(ids) * 2 * UNIT_YEN,
            "top1_hits": top1_hits,
            "top2_hits": top2_hits,
            "log_loss_sum": log_loss_sum,
            "actual_prob_sum": actual_prob_sum,
        }

    control_head_correct = 0
    head_correct_top2_miss = 0
    second_prefix_fail = 0
    third_completion_fail = 0
    for row in selected:
        rid = str(row["race_id"])
        actual, _ = parsed_results[rid]
        actual_parts = tuple(int(x) for x in actual.split("-"))
        structural = v4.structural_metrics(control_distributions_for_diag[rid])
        head_correct = int(structural["head_lane"]) == actual_parts[0]
        control_head_correct += int(head_correct)
        control_top2 = [
            tuple(int(x) for x in ticket.split("-"))
            for ticket in frozen_top2["control"][rid]
        ]
        if head_correct and actual_parts not in control_top2:
            head_correct_top2_miss += 1
            if any(ticket[:2] == actual_parts[:2] for ticket in control_top2):
                third_completion_fail += 1
            else:
                second_prefix_fail += 1
    diagnostic = {
        "date": day.isoformat(),
        "head_correct": control_head_correct,
        "head_correct_top2_miss": head_correct_top2_miss,
        "second_prefix_fail": second_prefix_fail,
        "third_completion_fail": third_completion_fail,
    }
    return metrics, diagnostic


def aggregate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(rows)
    races = sum(int(row["races"]) for row in items)
    investment = sum(int(row["investment_yen"]) for row in items)
    gross = sum(int(row["gross_return_yen"]) for row in items)
    top1_hits = sum(int(row["top1_hits"]) for row in items)
    top2_hits = sum(int(row["top2_hits"]) for row in items)
    log_loss_sum = sum(float(row["log_loss_sum"]) for row in items)
    actual_prob_sum = sum(float(row["actual_prob_sum"]) for row in items)
    return {
        "days": len(items),
        "races": races,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3) if investment else 0.0,
        "top1_hits": top1_hits,
        "top1_hit_rate_percent": round(top1_hits / races * 100.0, 3) if races else 0.0,
        "top2_hits": top2_hits,
        "top2_hit_rate_percent": round(top2_hits / races * 100.0, 3) if races else 0.0,
        "mean_log_loss": round(log_loss_sum / races, 6) if races else 0.0,
        "mean_actual_prob": round(actual_prob_sum / races, 8) if races else 0.0,
    }


def choose_candidate(
    by_candidate: Mapping[str, Mapping[str, dict[str, Any]]],
    train_days: list[str],
) -> tuple[str, dict[str, Any]]:
    ranked = []
    for name in sorted(CANDIDATES):
        metrics = aggregate(by_candidate[name][day] for day in train_days)
        ranked.append(
            (
                -float(metrics["top2_hit_rate_percent"]),
                float(metrics["mean_log_loss"]),
                name,
                metrics,
            )
        )
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    _, _, name, metrics = ranked[0]
    return name, metrics


# Bound only inside main, after pre-result construction, for diagnostic use.
control_distributions_for_diag: dict[str, dict[str, float]] = {}


def main() -> None:
    global control_distributions_for_diag

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_TAIL_ORDER_VERSION={VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY CURRENT_SIX_FIXED FIRST_MARGINAL_FIXED "
        "ALL_TOP2_FROZEN_BEFORE_RESULT PAST_ONLY_WALKFORWARD NO_RETUNE",
        flush=True,
    )
    print(f"CANDIDATE_COUNT={len(CANDIDATES)}", flush=True)

    by_candidate: dict[str, dict[str, dict[str, Any]]] = {
        name: {} for name in CANDIDATES
    }
    diagnostics: list[dict[str, Any]] = []
    day_audit: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for idx, day in enumerate(hist.daterange(START_DATE, END_DATE), 1):
                control, signals, selected = build_day(cur, day)
                candidate_probs, frozen_top2 = freeze_candidate_tickets(
                    control, signals, selected
                )
                selected_ids = [str(row["race_id"]) for row in selected]
                # Result/payout access starts only after all candidate Top2 are frozen.
                results = hist.fetch_selected_results(cur, day, selected_ids)

                control_distributions_for_diag = dict(control)
                evaluated = evaluate_day(
                    day=day,
                    selected=selected,
                    candidate_probs=candidate_probs,
                    frozen_top2=frozen_top2,
                    results=results,
                )
                if evaluated is not None:
                    metrics, diagnostic = evaluated
                    for name, row in metrics.items():
                        by_candidate[name][day.isoformat()] = row
                    diagnostics.append(diagnostic)

                day_audit.append(
                    {
                        "date": day.isoformat(),
                        "selected_races": len(selected),
                        "evaluable": evaluated is not None,
                    }
                )
                if idx % 30 == 0:
                    print(
                        f"PROGRESS day={day} calendar_days={idx} "
                        f"selected={len(selected)} evaluable={int(evaluated is not None)}",
                        flush=True,
                    )
            conn.rollback()

    evaluated_days = sorted(by_candidate["control"])
    fixed = [
        {
            "candidate": name,
            "metrics": aggregate(by_candidate[name][day] for day in evaluated_days),
        }
        for name in sorted(CANDIDATES)
    ]

    blocks = hist.split_blocks(evaluated_days, BLOCKS)
    walkforward = []
    adaptive_rows = []
    control_rows = []
    chosen_counts: Counter[str] = Counter()
    for idx in range(1, len(blocks)):
        train_days = sorted(set().union(*blocks[:idx]))
        test_days = sorted(blocks[idx])
        chosen, train_metrics = choose_candidate(by_candidate, train_days)
        chosen_counts[chosen] += 1
        chosen_test_rows = [by_candidate[chosen][day] for day in test_days]
        control_test_rows = [by_candidate["control"][day] for day in test_days]
        adaptive_rows.extend(chosen_test_rows)
        control_rows.extend(control_test_rows)
        chosen_test = aggregate(chosen_test_rows)
        control_test = aggregate(control_test_rows)
        walkforward.append(
            {
                "test_block": idx + 1,
                "train_start": min(train_days),
                "train_end": max(train_days),
                "test_start": min(test_days),
                "test_end": max(test_days),
                "chosen_candidate": chosen,
                "chosen_train_metrics": train_metrics,
                "chosen_test_metrics": chosen_test,
                "control_test_metrics": control_test,
                "test_delta": {
                    "top2_hit_rate_pp": round(
                        chosen_test["top2_hit_rate_percent"]
                        - control_test["top2_hit_rate_percent"],
                        3,
                    ),
                    "roi_pp": round(
                        chosen_test["roi_percent"] - control_test["roi_percent"], 3
                    ),
                    "mean_log_loss": round(
                        chosen_test["mean_log_loss"]
                        - control_test["mean_log_loss"],
                        6,
                    ),
                },
            }
        )

    adaptive = aggregate(adaptive_rows)
    control_same_test = aggregate(control_rows)
    head_correct = sum(int(row["head_correct"]) for row in diagnostics)
    head_miss = sum(int(row["head_correct_top2_miss"]) for row in diagnostics)
    second_fail = sum(int(row["second_prefix_fail"]) for row in diagnostics)
    third_fail = sum(int(row["third_completion_fail"]) for row in diagnostics)

    result = {
        "contract": "v4_tail_order_challenger_walkforward_v1",
        "version": VERSION,
        "period": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "candidate_family": {
            name: {
                "boost": values[0],
                "second_weight": values[1],
                "third_weight": values[2],
            }
            for name, values in CANDIDATES.items()
        },
        "policy": {
            "current_daily_six_fixed": True,
            "first_place_marginal_preserved": True,
            "formal_ticket_count": 2,
            "all_candidate_top2_frozen_before_result": True,
            "walkforward_choice_uses_past_only": True,
            "odds_used_for_selection": False,
            "db_write": False,
            "production_change_allowed": False,
            "coefficient_change_allowed": False,
            "ticket_count_change_allowed": False,
            "purchase_action": False,
        },
        "coverage": {
            "calendar_days": len(day_audit),
            "evaluated_days": len(evaluated_days),
            "evaluated_races": len(evaluated_days) * v4.CORE_RACES,
        },
        "control_error_decomposition": {
            "head_correct": head_correct,
            "head_correct_top2_miss": head_miss,
            "second_prefix_fail": second_fail,
            "third_completion_fail": third_fail,
            "second_prefix_fail_share_percent": round(
                second_fail / head_miss * 100.0, 3
            ) if head_miss else 0.0,
            "third_completion_fail_share_percent": round(
                third_fail / head_miss * 100.0, 3
            ) if head_miss else 0.0,
        },
        "fixed_candidate_comparison": fixed,
        "walkforward_blocks": walkforward,
        "adaptive_walkforward": {
            "test_blocks": max(0, len(blocks) - 1),
            "chosen_candidate_counts": dict(sorted(chosen_counts.items())),
            "challenger": adaptive,
            "control_same_test_days": control_same_test,
            "delta": {
                "top2_hit_rate_pp": round(
                    adaptive["top2_hit_rate_percent"]
                    - control_same_test["top2_hit_rate_percent"],
                    3,
                ),
                "roi_pp": round(
                    adaptive["roi_percent"] - control_same_test["roi_percent"], 3
                ),
                "mean_log_loss": round(
                    adaptive["mean_log_loss"]
                    - control_same_test["mean_log_loss"],
                    6,
                ),
            },
        },
        "day_audit": day_audit,
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== COVERAGE ===", flush=True)
    print(json.dumps(result["coverage"], sort_keys=True), flush=True)
    print("=== CONTROL ERROR DECOMPOSITION ===", flush=True)
    print(json.dumps(result["control_error_decomposition"], sort_keys=True), flush=True)
    print("=== FIXED TAIL CANDIDATES ===", flush=True)
    for row in fixed:
        m = row["metrics"]
        print(
            f"CANDIDATE={row['candidate']} TOP2_HIT={m['top2_hit_rate_percent']:.3f} "
            f"ROI={m['roi_percent']:.3f} LOGLOSS={m['mean_log_loss']:.6f}",
            flush=True,
        )
    print("=== ADAPTIVE WALKFORWARD ===", flush=True)
    print(json.dumps(result["adaptive_walkforward"], sort_keys=True), flush=True)
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY_TAIL_ORDER_CHALLENGER", flush=True)


if __name__ == "__main__":
    main()
