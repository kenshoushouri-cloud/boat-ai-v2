# -*- coding: utf-8 -*-
"""Past-only conservative blend of current V4 tail and learned conditional tail.

This is iterative historical research after the full-replacement position-
conditional challenger failed exact Top2 despite improving conditional second
choice.

For each selected race:
- keep current V4 P(first) exactly;
- build learned P(second|first)*P(third|first,second) from prior-block weights;
- convex-blend the full current distribution and learned distribution.

Five alpha candidates are frozen in source.  Block 2 is forced to alpha=0
(current control).  For block 3 onward, the alpha used for the current block is
chosen only from cumulative candidate results on earlier unseen blocks.
All alpha tickets are frozen before current-block result access.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_position_conditional_tail_walkforward_pg as pos

VERSION = "2026-09-23 v4-position-conditional-blend-v1"
START_DATE = date.fromisoformat(os.getenv("V4_POSBLEND_START_DATE", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("V4_POSBLEND_END_DATE", "2026-09-22"))
BLOCKS = int(os.getenv("V4_POSBLEND_BLOCKS", "10"))
OUTPUT_JSON = Path(
    os.getenv(
        "V4_POSBLEND_OUTPUT_JSON",
        "v4-position-conditional-blend-walkforward.json",
    )
)
UNIT_YEN = 100

ALPHAS: dict[str, float] = {
    "a000": 0.00,
    "a025": 0.25,
    "a050": 0.50,
    "a075": 0.75,
    "a100": 1.00,
}

if BLOCKS < 3:
    raise RuntimeError("V4_POSBLEND_BLOCKS must be >= 3")
if END_DATE < START_DATE:
    raise RuntimeError("invalid position-conditional blend period")
if tuple(ALPHAS.values()) != (0.0, 0.25, 0.5, 0.75, 1.0):
    raise RuntimeError("alpha family drift")


def first_marginals(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in probs.items():
        out[int(str(ticket).split("-", 1)[0])] += float(prob)
    return out


def blend_distribution(
    control_probs: Mapping[str, float],
    learned_probs: Mapping[str, float],
    alpha: float,
) -> dict[str, float]:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be in [0,1]")
    control = v4._normalize_tickets(control_probs)
    learned = v4._normalize_tickets(learned_probs)
    if set(control) != set(learned):
        raise ValueError("ticket support mismatch")
    out = {
        ticket: (1.0 - alpha) * control[ticket] + alpha * learned[ticket]
        for ticket in control
    }
    out = v4._normalize_tickets(out)

    before = first_marginals(control)
    learned_heads = first_marginals(learned)
    after = first_marginals(out)
    for lane in v4.LANES:
        if abs(learned_heads[lane] - before[lane]) > 1e-12:
            raise RuntimeError("learned first-place marginal drift")
        if abs(after[lane] - before[lane]) > 1e-12:
            raise RuntimeError("blend first-place marginal drift")
    return out


def build_day_snapshot(
    cur: psycopg.Cursor[Any],
    day: date,
    *,
    second_model: pos.PairwiseLogit,
    third_model: pos.PairwiseLogit,
) -> list[dict[str, Any]]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    distributions: dict[str, dict[str, float]] = {}
    features: dict[str, dict[int, tuple[float, ...]]] = {}

    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        venue = str(race.get("venue_id") or "").zfill(2)
        try:
            base_raw = hist.base_raw(entries, venue)
            base_features = pos.lane_base_feature_map(entries, venue)
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
        distributions[rid] = v4.build_v4_distribution(
            base_raw=base_raw,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
        features[rid] = base_features

    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )

    frozen: list[dict[str, Any]] = []
    for row in selected:
        rid = str(row["race_id"])
        control = distributions[rid]
        learned, _ = pos.challenger_distribution(
            control_probs=control,
            base_features=features[rid],
            second_model=second_model,
            third_model=third_model,
        )
        candidate_probs: dict[str, dict[str, float]] = {}
        candidate_top2: dict[str, list[str]] = {}
        for label, alpha in ALPHAS.items():
            probs = blend_distribution(control, learned, alpha)
            candidate_probs[label] = probs
            candidate_top2[label] = list(v4.top_tickets(probs, 2))

        if candidate_top2["a000"] != list(row["tickets"]):
            raise RuntimeError(f"alpha0 control reproduction drift: {rid}")

        frozen.append(
            {
                "race_id": rid,
                "candidate_top2": candidate_top2,
                "candidate_probs": candidate_probs,
                "base_features": {
                    str(lane): list(features[rid][lane]) for lane in v4.LANES
                },
            }
        )
    return frozen


def evaluate_day(
    *,
    day: date,
    frozen: list[dict[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]] | None:
    if len(frozen) != v4.CORE_RACES:
        return None

    totals = {
        label: {
            "date": day.isoformat(),
            "races": v4.CORE_RACES,
            "investment_yen": v4.CORE_RACES * v4.CORE_TICKETS * UNIT_YEN,
            "gross_return_yen": 0,
            "top2_hits": 0,
            "log_loss_sum": 0.0,
            "actual_prob_sum": 0.0,
        }
        for label in ALPHAS
    }
    training_rows: list[dict[str, Any]] = []

    for row in frozen:
        rid = str(row["race_id"])
        result = results.get(rid)
        if not result:
            return None
        actual = hist.norm_ticket(result.get("trifecta_ticket"))
        payout = int(result.get("trifecta_payout_yen") or 0)
        if actual is None or payout <= 0:
            return None

        for label in ALPHAS:
            top2 = row["candidate_top2"][label]
            probs = row["candidate_probs"][label]
            actual_prob = float(probs.get(actual, 0.0))
            if actual_prob <= 0.0 or not math.isfinite(actual_prob):
                raise RuntimeError("invalid blended actual probability")
            hit = actual in top2
            totals[label]["top2_hits"] += int(hit)
            totals[label]["gross_return_yen"] += payout if hit else 0
            totals[label]["log_loss_sum"] += -math.log(max(actual_prob, 1e-15))
            totals[label]["actual_prob_sum"] += actual_prob

        a, b, c = (int(x) for x in actual.split("-"))
        training_rows.append(
            {
                "race_id": rid,
                "actual": [a, b, c],
                "base_features": row["base_features"],
            }
        )

    for label in ALPHAS:
        investment = int(totals[label]["investment_yen"])
        gross = int(totals[label]["gross_return_yen"])
        totals[label]["profit_yen"] = gross - investment
    return totals, training_rows


def aggregate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(rows)
    races = sum(int(row["races"]) for row in items)
    investment = sum(int(row["investment_yen"]) for row in items)
    gross = sum(int(row["gross_return_yen"]) for row in items)
    hits = sum(int(row["top2_hits"]) for row in items)
    log_loss_sum = sum(float(row["log_loss_sum"]) for row in items)
    actual_prob_sum = sum(float(row["actual_prob_sum"]) for row in items)
    return {
        "days": len(items),
        "races": races,
        "investment_yen": investment,
        "gross_return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3)
        if investment else 0.0,
        "top2_hits": hits,
        "top2_hit_rate_percent": round(hits / races * 100.0, 3)
        if races else 0.0,
        "mean_log_loss": round(log_loss_sum / races, 6)
        if races else 0.0,
        "mean_actual_prob": round(actual_prob_sum / races, 8)
        if races else 0.0,
    }


def paired_day_bootstrap(
    challenger_rows: Iterable[dict[str, Any]],
    control_rows: Iterable[dict[str, Any]],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    challenger = sorted(list(challenger_rows), key=lambda row: str(row["date"]))
    control = sorted(list(control_rows), key=lambda row: str(row["date"]))
    if len(challenger) != len(control):
        raise ValueError("paired bootstrap requires equal day counts")
    if not challenger:
        return {
            "days": 0,
            "samples": samples,
            "seed": seed,
            "observed_top2_hit_rate_pp": 0.0,
            "ci95_low_pp": 0.0,
            "ci95_high_pp": 0.0,
            "positive_share_percent": 0.0,
        }

    pairs = []
    for left, right in zip(challenger, control):
        if str(left["date"]) != str(right["date"]):
            raise ValueError("paired bootstrap date mismatch")
        if int(left["races"]) != int(right["races"]):
            raise ValueError("paired bootstrap race-count mismatch")
        pairs.append(
            (
                int(left["top2_hits"]) - int(right["top2_hits"]),
                int(left["races"]),
            )
        )

    total_hit_diff = sum(hit_diff for hit_diff, _ in pairs)
    total_races = sum(races for _, races in pairs)
    observed = total_hit_diff / total_races * 100.0

    rng = random.Random(seed)
    diffs: list[float] = []
    n = len(pairs)
    for _ in range(samples):
        sampled_hit_diff = 0
        sampled_races = 0
        for _ in range(n):
            hit_diff, races = pairs[rng.randrange(n)]
            sampled_hit_diff += hit_diff
            sampled_races += races
        diffs.append(sampled_hit_diff / sampled_races * 100.0)

    diffs.sort()
    low_idx = max(0, min(len(diffs) - 1, int(0.025 * len(diffs))))
    high_idx = max(0, min(len(diffs) - 1, int(0.975 * len(diffs)) - 1))
    positive = sum(1 for value in diffs if value > 0.0)
    return {
        "days": n,
        "samples": samples,
        "seed": seed,
        "observed_top2_hit_rate_pp": round(observed, 3),
        "ci95_low_pp": round(diffs[low_idx], 3),
        "ci95_high_pp": round(diffs[high_idx], 3),
        "positive_share_percent": round(positive / samples * 100.0, 3),
    }


def choose_alpha(
    prior_oos: Mapping[str, list[dict[str, Any]]],
) -> tuple[str, dict[str, Any] | None]:
    if not prior_oos["a000"]:
        return "a000", None

    ranked = []
    for label, alpha in ALPHAS.items():
        metrics = aggregate(prior_oos[label])
        ranked.append(
            (
                -float(metrics["top2_hit_rate_percent"]),
                float(metrics["mean_log_loss"]),
                float(alpha),
                label,
                metrics,
            )
        )
    ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    _, _, _, label, metrics = ranked[0]
    return label, metrics


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    all_days = [d.isoformat() for d in hist.daterange(START_DATE, END_DATE)]
    calendar_blocks = hist.split_blocks(all_days, BLOCKS)
    second_model = pos.PairwiseLogit(pos.SECOND_DIM)
    third_model = pos.PairwiseLogit(pos.THIRD_DIM)

    prior_oos: dict[str, list[dict[str, Any]]] = {
        label: [] for label in ALPHAS
    }
    all_oos: dict[str, list[dict[str, Any]]] = {
        label: [] for label in ALPHAS
    }
    selected_oos_rows: list[dict[str, Any]] = []
    control_oos_rows: list[dict[str, Any]] = []
    selected_alpha_counts: dict[str, int] = {label: 0 for label in ALPHAS}
    block_results: list[dict[str, Any]] = []

    print(f"V4_POSBLEND_VERSION={VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "POLICY=READ_ONLY CURRENT_SIX_FIXED FIRST_PLACE_MARGINAL_FIXED "
        "ALPHA_SELECTED_FROM_PRIOR_UNSEEN_BLOCKS_ONLY "
        "ALL_ALPHA_TOP2_FROZEN_BEFORE_RESULT NO_ODDS NO_RETUNE",
        flush=True,
    )
    print(
        "ALPHAS=" + ",".join(f"{label}:{alpha:.2f}" for label, alpha in ALPHAS.items()),
        flush=True,
    )

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

            for block_index, block_day_set in enumerate(calendar_blocks, 1):
                block_days = sorted(block_day_set)
                block_candidate_rows: dict[str, list[dict[str, Any]]] = {
                    label: [] for label in ALPHAS
                }
                block_training_rows: list[dict[str, Any]] = []

                if block_index == 1:
                    chosen_label = "warmup_only"
                    chosen_prior_metrics = None
                elif block_index == 2:
                    # No earlier OOS blend evidence exists yet.
                    chosen_label = "a000"
                    chosen_prior_metrics = None
                else:
                    chosen_label, chosen_prior_metrics = choose_alpha(prior_oos)

                for day_text in block_days:
                    day = date.fromisoformat(day_text)
                    frozen = build_day_snapshot(
                        cur,
                        day,
                        second_model=second_model,
                        third_model=third_model,
                    )
                    selected_ids = [str(row["race_id"]) for row in frozen]
                    # All five alpha Top2 sets are frozen before result access.
                    results = hist.fetch_selected_results(cur, day, selected_ids)
                    evaluated = evaluate_day(
                        day=day,
                        frozen=frozen,
                        results=results,
                    )
                    if evaluated is None:
                        continue
                    candidate_rows, training_rows = evaluated
                    for label in ALPHAS:
                        block_candidate_rows[label].append(candidate_rows[label])
                    block_training_rows.extend(training_rows)

                block_metrics = {
                    label: aggregate(rows)
                    for label, rows in block_candidate_rows.items()
                }

                if block_index > 1:
                    for label in ALPHAS:
                        prior_oos[label].extend(block_candidate_rows[label])
                        all_oos[label].extend(block_candidate_rows[label])
                    selected_alpha_counts[chosen_label] += 1
                    selected_oos_rows.extend(block_candidate_rows[chosen_label])
                    control_oos_rows.extend(block_candidate_rows["a000"])

                block_results.append(
                    {
                        "block": block_index,
                        "start_date": block_days[0],
                        "end_date": block_days[-1],
                        "calendar_days": len(block_days),
                        "chosen_alpha": chosen_label,
                        "chosen_prior_oos_metrics": chosen_prior_metrics,
                        "candidate_metrics": block_metrics,
                        "training_races_added": len(block_training_rows),
                        "second_model_updates_before_train": second_model.updates,
                        "third_model_updates_before_train": third_model.updates,
                    }
                )

                # Current block outcomes may train the model only after all
                # current-block alpha candidates were frozen and evaluated.
                pos.train_block(
                    second_model=second_model,
                    third_model=third_model,
                    training_rows=block_training_rows,
                )
                block_results[-1]["second_model_updates_after_train"] = second_model.updates
                block_results[-1]["third_model_updates_after_train"] = third_model.updates

                if block_index == 1:
                    print(
                        f"BLOCK=1 {block_days[0]}..{block_days[-1]} "
                        f"WARMUP_RACES={len(block_training_rows)}",
                        flush=True,
                    )
                else:
                    chosen = block_metrics[chosen_label]
                    control = block_metrics["a000"]
                    print(
                        f"BLOCK={block_index} {block_days[0]}..{block_days[-1]} "
                        f"CHOSEN={chosen_label} "
                        f"CHOSEN_TOP2={chosen['top2_hit_rate_percent']:.3f} "
                        f"CONTROL_TOP2={control['top2_hit_rate_percent']:.3f} "
                        f"EVAL_RACES={control['races']}",
                        flush=True,
                    )

            conn.rollback()

    selected = aggregate(selected_oos_rows)
    control = aggregate(control_oos_rows)
    fixed_oos = {
        label: aggregate(rows) for label, rows in all_oos.items()
    }
    selected_block_wins = sum(
        1
        for row in block_results[1:]
        if row["candidate_metrics"][row["chosen_alpha"]]["top2_hit_rate_percent"]
        > row["candidate_metrics"]["a000"]["top2_hit_rate_percent"]
    )
    selected_block_ties = sum(
        1
        for row in block_results[1:]
        if row["candidate_metrics"][row["chosen_alpha"]]["top2_hit_rate_percent"]
        == row["candidate_metrics"]["a000"]["top2_hit_rate_percent"]
    )
    selected_bootstrap = paired_day_bootstrap(
        selected_oos_rows,
        control_oos_rows,
    )
    fixed_a025_bootstrap = paired_day_bootstrap(
        all_oos["a025"],
        all_oos["a000"],
    )

    result = {
        "contract": "v4_position_conditional_blend_walkforward_v1",
        "version": VERSION,
        "period": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
        },
        "alpha_family": ALPHAS,
        "policy": {
            "iterative_historical_hypothesis_refinement": True,
            "current_daily_six_fixed": True,
            "first_place_marginal_preserved": True,
            "formal_ticket_count": 2,
            "alpha0_is_exact_control": True,
            "block2_forced_control": True,
            "alpha_choice_uses_prior_unseen_blocks_only": True,
            "all_alpha_top2_frozen_before_result": True,
            "model_training_uses_completed_blocks_only": True,
            "odds_used_for_selection": False,
            "db_write": False,
            "production_change_allowed": False,
            "promotion_allowed": False,
            "purchase_action": False,
        },
        "walkforward": {
            "warmup_block": 1,
            "unseen_test_blocks": max(0, len(calendar_blocks) - 1),
            "selected_alpha_counts": {
                key: value for key, value in selected_alpha_counts.items() if value
            },
            "selected_strategy": selected,
            "control_same_test_days": control,
            "delta": {
                "top2_hit_rate_pp": round(
                    selected["top2_hit_rate_percent"]
                    - control["top2_hit_rate_percent"],
                    3,
                ),
                "mean_log_loss": round(
                    selected["mean_log_loss"] - control["mean_log_loss"],
                    6,
                ),
                "roi_pp": round(
                    selected["roi_percent"] - control["roi_percent"], 3
                ),
            },
            "selected_top2_block_wins": selected_block_wins,
            "selected_top2_block_ties": selected_block_ties,
            "paired_day_bootstrap_selected_vs_control": selected_bootstrap,
            "paired_day_bootstrap_fixed_a025_vs_control": fixed_a025_bootstrap,
            "fixed_alpha_oos_descriptive": fixed_oos,
            "block_results": block_results,
        },
        "model": {
            "second_dim": pos.SECOND_DIM,
            "third_dim": pos.THIRD_DIM,
            "epochs_per_block": pos.EPOCHS_PER_BLOCK,
            "base_lr": pos.BASE_LR,
            "l2": pos.L2,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== BLEND UNSEEN WALKFORWARD ===", flush=True)
    print(json.dumps(result["walkforward"], sort_keys=True), flush=True)
    print(f"OUTPUT_JSON={OUTPUT_JSON}", flush=True)
    print("RESULT=PASS_READ_ONLY_POSITION_CONDITIONAL_BLEND", flush=True)


if __name__ == "__main__":
    main()
