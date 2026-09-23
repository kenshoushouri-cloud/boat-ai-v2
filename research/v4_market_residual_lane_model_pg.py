# -*- coding: utf-8 -*-
"""Low-dimensional market-residual learner with a fully held-out profit test.

Calibration data:
  2026-07-01..2026-08-24, coherent complete 120-ticket odds available by
  deadline-5m, current V4 selected races only.

Held-out data:
  2026-08-25..2026-09-22 under the identical timing-safe contract.

The market probability is the fixed offset.  A small residual softmax learns
only:
- log(current_V4_prob / market_prob), clipped to +/-3;
- first-lane one-hot;
- second-lane one-hot;
- third-lane one-hot.

The 19 weights, epoch count, learning rate and L2 are fixed in source.  There is
no hyperparameter search and no calibration on held-out outcomes.  Held-out
residual probabilities and all EV ticket grids are frozen before result access.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_position_conditional_tail_walkforward_pg as pos
from research import v4_timing_safe_profit_gate_pg as base
from research import v4_market_residual_value_walkforward_pg as mr

VERSION = "2026-09-23 v4-market-residual-lane-model-v1"
CALIB_START = date(2026, 7, 1)
CALIB_END = date(2026, 8, 24)
HOLD_START = date(2026, 8, 25)
HOLD_END = date(2026, 9, 22)

EPOCHS = 200
LEARNING_RATE = 0.10
L2 = 0.10
LOG_RATIO_CLIP = 3.0
FEATURE_DIM = 19

OUTPUT_JSON = Path(
    os.getenv(
        "V4_RESIDUAL_LANE_OUTPUT_JSON",
        "v4-market-residual-lane-model.json",
    )
)
BOOTSTRAP_SAMPLES = int(
    os.getenv("V4_RESIDUAL_LANE_BOOTSTRAP_SAMPLES", "20000")
)
BOOTSTRAP_SEED = int(
    os.getenv("V4_RESIDUAL_LANE_BOOTSTRAP_SEED", "20260923")
)

if base.ODDS_CUTOFF_MINUTES != 5:
    raise RuntimeError("residual learner requires frozen deadline-5m odds")
if CALIB_END >= HOLD_START:
    raise RuntimeError("calibration must end before held-out starts")


def one_hot(lane: int) -> tuple[float, ...]:
    return tuple(1.0 if lane == idx else 0.0 for idx in v4.LANES)


def ticket_features(
    ticket: str,
    market_prob: float,
    model_prob: float,
) -> tuple[float, ...]:
    a, b, c = (int(x) for x in ticket.split("-"))
    ratio = math.log(max(float(model_prob), 1e-15)) - math.log(
        max(float(market_prob), 1e-15)
    )
    ratio = max(-LOG_RATIO_CLIP, min(LOG_RATIO_CLIP, ratio))
    out = (ratio, *one_hot(a), *one_hot(b), *one_hot(c))
    if len(out) != FEATURE_DIM:
        raise RuntimeError("feature dimension drift")
    return out


def dot(weights: Sequence[float], features: Sequence[float]) -> float:
    return sum(float(w) * float(x) for w, x in zip(weights, features))


def residual_probs(
    market: Mapping[str, float],
    model: Mapping[str, float],
    weights: Sequence[float],
) -> dict[str, float]:
    m = mr.normalize(market)
    p = mr.normalize(model)
    if set(m) != set(p):
        raise ValueError("market/model support mismatch")
    if len(weights) != FEATURE_DIM:
        raise ValueError("weight dimension mismatch")
    scores = {}
    for ticket in m:
        x = ticket_features(ticket, m[ticket], p[ticket])
        scores[ticket] = math.log(max(m[ticket], 1e-15)) + dot(weights, x)
    mx = max(scores.values())
    exp_scores = {
        ticket: math.exp(score - mx) for ticket, score in scores.items()
    }
    return mr.normalize(exp_scores)


def mean_log_loss(
    rows: Sequence[Mapping[str, Any]],
    weights: Sequence[float],
) -> float | None:
    if not rows:
        return None
    total = 0.0
    for row in rows:
        probs = residual_probs(
            row["market_probs"],
            row["model_probs"],
            weights,
        )
        total += -math.log(max(probs[str(row["actual"])], 1e-15))
    return total / len(rows)


def fit_residual(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[float], dict[str, Any]]:
    weights = [0.0] * FEATURE_DIM
    initial_loss = mean_log_loss(rows, weights)
    if not rows:
        return weights, {
            "races": 0,
            "initial_log_loss": None,
            "final_log_loss": None,
        }

    for epoch in range(EPOCHS):
        grad = [0.0] * FEATURE_DIM
        for row in rows:
            market = mr.normalize(row["market_probs"])
            model = mr.normalize(row["model_probs"])
            actual = str(row["actual"])
            probs = residual_probs(market, model, weights)
            actual_x = ticket_features(
                actual,
                market[actual],
                model[actual],
            )
            expected = [0.0] * FEATURE_DIM
            for ticket, probability in probs.items():
                x = ticket_features(
                    ticket,
                    market[ticket],
                    model[ticket],
                )
                for idx in range(FEATURE_DIM):
                    expected[idx] += float(probability) * float(x[idx])
            for idx in range(FEATURE_DIM):
                grad[idx] += float(actual_x[idx]) - expected[idx]

        scale = 1.0 / len(rows)
        for idx in range(FEATURE_DIM):
            update = (
                LEARNING_RATE
                * (
                    grad[idx] * scale
                    - L2 * weights[idx]
                )
            )
            weights[idx] += update
            weights[idx] = max(-3.0, min(3.0, weights[idx]))

    final_loss = mean_log_loss(rows, weights)
    return weights, {
        "races": len(rows),
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "l2": L2,
        "initial_log_loss": (
            round(float(initial_loss), 8) if initial_loss is not None else None
        ),
        "final_log_loss": (
            round(float(final_loss), 8) if final_loss is not None else None
        ),
        "weights": [round(float(w), 8) for w in weights],
    }


def predictive_metrics(
    rows: Sequence[Mapping[str, Any]],
    source: str,
    weights: Sequence[float],
) -> dict[str, Any]:
    if not rows:
        return {
            "races": 0,
            "log_loss": None,
            "brier": None,
            "mean_rank": None,
        }
    ll = br = rank_total = 0.0
    for row in rows:
        if source == "market":
            probs = row["market_probs"]
        elif source == "current":
            probs = row["model_probs"]
        elif source == "residual":
            probs = residual_probs(
                row["market_probs"],
                row["model_probs"],
                weights,
            )
        else:
            raise ValueError(source)
        actual = str(row["actual"])
        actual_prob = max(float(probs[actual]), 1e-15)
        ll += -math.log(actual_prob)
        br += mr.brier(probs, actual)
        target = float(probs[actual])
        rank_total += 1 + sum(
            1
            for ticket, prob in probs.items()
            if float(prob) > target
            or (float(prob) == target and ticket < actual)
        )
    n = len(rows)
    return {
        "races": n,
        "log_loss": round(ll / n, 8),
        "brier": round(br / n, 8),
        "mean_rank": round(rank_total / n, 4),
    }


def freeze_base_race(
    race: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> dict[str, Any]:
    odds = {
        ticket: float(value)
        for ticket, value in odds_row["odds"].items()
    }
    market = base.market_probs(odds)
    model = race["probabilities"]["current"]
    return {
        "race_id": str(race["race_id"]),
        "race_date": str(race["race_date"]),
        "daily_rank": int(race["daily_rank"]),
        "snapshot_label": str(odds_row["snapshot_label"]),
        "minutes_before_deadline": round(
            float(odds_row["minutes_before_deadline"]),
            4,
        ),
        "odds": odds,
        "market_probs": market,
        "model_probs": model,
    }


def freeze_residual_value(
    row: Mapping[str, Any],
    weights: Sequence[float],
) -> dict[str, Any]:
    probs = residual_probs(
        row["market_probs"],
        row["model_probs"],
        weights,
    )
    ranked = sorted(
        (
            {
                "ticket": ticket,
                "prob": float(probs[ticket]),
                "odds": float(row["odds"][ticket]),
                "raw_ev": float(probs[ticket])
                * float(row["odds"][ticket]),
            }
            for ticket in probs
        ),
        key=lambda item: (
            -float(item["raw_ev"]),
            -float(item["prob"]),
            item["ticket"],
        ),
    )
    policies: dict[str, list[dict[str, Any]]] = {}
    for points in mr.POINT_COUNTS:
        for threshold in mr.EV_THRESHOLDS:
            pid = f"residual_p{points}_ev{threshold:.2f}"
            policies[pid] = [
                item
                for item in ranked
                if float(item["raw_ev"]) >= threshold
            ][:points]
    return {
        **dict(row),
        "residual_probs": probs,
        "value_tickets": policies,
    }


def settle_residual_bets(
    rows: Sequence[Mapping[str, Any]],
    *,
    points: int,
    threshold: float,
) -> list[dict[str, Any]]:
    pid = f"residual_p{points}_ev{threshold:.2f}"
    out: list[dict[str, Any]] = []
    for row in rows:
        for rank, bet in enumerate(row["value_tickets"][pid], 1):
            hit = str(bet["ticket"]) == str(row["actual"])
            out.append(
                {
                    "race_id": str(row["race_id"]),
                    "race_date": str(row["race_date"]),
                    "rank": rank,
                    "ticket": str(bet["ticket"]),
                    "prob": round(float(bet["prob"]), 12),
                    "odds": round(float(bet["odds"]), 4),
                    "raw_ev": round(float(bet["raw_ev"]), 8),
                    "hit": hit,
                    "return_yen": (
                        int(row["payout_yen"]) if hit else 0
                    ),
                }
            )
    return out


def gather_calibration(
    cur: psycopg.Cursor[Any],
) -> list[dict[str, Any]]:
    dummy_second = pos.PairwiseLogit(pos.SECOND_DIM)
    dummy_third = pos.PairwiseLogit(pos.THIRD_DIM)
    rows: list[dict[str, Any]] = []

    for day in hist.daterange(CALIB_START, CALIB_END):
        selected = base.build_test_day(
            cur,
            day,
            second_model=dummy_second,
            third_model=dummy_third,
        )
        if len(selected) != v4.CORE_RACES:
            continue
        odds_by = base.latest_coherent_odds(cur, selected)
        selected_by_id = {
            str(row["race_id"]): row for row in selected
        }
        # Freeze market/current maps before calibration results are read.
        frozen = {
            rid: freeze_base_race(selected_by_id[rid], odds_row)
            for rid, odds_row in odds_by.items()
        }
        results = hist.fetch_selected_results(cur, day, sorted(frozen))
        for rid, row in frozen.items():
            result = results.get(rid)
            if not result:
                continue
            actual = hist.norm_ticket(result.get("trifecta_ticket"))
            payout = int(result.get("trifecta_payout_yen") or 0)
            if actual is None or payout <= 0:
                continue
            rows.append(
                {
                    **row,
                    "actual": actual,
                    "payout_yen": payout,
                }
            )
    return rows


def gather_heldout(
    cur: psycopg.Cursor[Any],
    weights: Sequence[float],
) -> list[dict[str, Any]]:
    dummy_second = pos.PairwiseLogit(pos.SECOND_DIM)
    dummy_third = pos.PairwiseLogit(pos.THIRD_DIM)
    rows: list[dict[str, Any]] = []

    for day in hist.daterange(HOLD_START, HOLD_END):
        selected = base.build_test_day(
            cur,
            day,
            second_model=dummy_second,
            third_model=dummy_third,
        )
        if len(selected) != v4.CORE_RACES:
            continue
        odds_by = base.latest_coherent_odds(cur, selected)
        selected_by_id = {
            str(row["race_id"]): row for row in selected
        }

        # Freeze residual probabilities and every EV policy before result access.
        frozen = {
            rid: freeze_residual_value(
                freeze_base_race(selected_by_id[rid], odds_row),
                weights,
            )
            for rid, odds_row in odds_by.items()
        }
        results = hist.fetch_selected_results(cur, day, sorted(frozen))
        for rid, row in frozen.items():
            result = results.get(rid)
            if not result:
                continue
            actual = hist.norm_ticket(result.get("trifecta_ticket"))
            payout = int(result.get("trifecta_payout_yen") or 0)
            if actual is None or payout <= 0:
                continue
            rows.append(
                {
                    **row,
                    "actual": actual,
                    "payout_yen": payout,
                }
            )
    return rows


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_RESIDUAL_LANE_VERSION={VERSION}", flush=True)
    print(
        f"CALIBRATION={CALIB_START}..{CALIB_END} "
        f"HELDOUT={HOLD_START}..{HOLD_END}",
        flush=True,
    )
    print(
        f"MODEL=MARKET_OFFSET_PLUS_19D_RESIDUAL epochs:{EPOCHS} "
        f"lr:{LEARNING_RATE} l2:{L2} ratio_clip:{LOG_RATIO_CLIP}",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY CALIBRATION_ONLY_TRAINING "
        "HELDOUT_WEIGHTS_FIXED RESULT_AFTER_POLICY_FREEZE "
        "NO_HYPERPARAM_SEARCH NO_DB_WRITE NO_LINE NO_BUY NO_PROMOTION",
        flush=True,
    )

    with psycopg.connect(
        db,
        row_factory=dict_row,
        autocommit=False,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            calibration_rows = gather_calibration(cur)
            weights, training = fit_residual(calibration_rows)
            heldout_rows = gather_heldout(cur, weights)
            conn.rollback()

    predictive = {
        source: predictive_metrics(
            heldout_rows,
            source,
            weights,
        )
        for source in ("market", "current", "residual")
    }
    predictive["residual_minus_market"] = {
        key: round(
            float(predictive["residual"][key])
            - float(predictive["market"][key]),
            8 if key in ("log_loss", "brier") else 4,
        )
        for key in ("log_loss", "brier", "mean_rank")
    }

    policies: dict[str, Any] = {}
    passed: list[str] = []
    for points in mr.POINT_COUNTS:
        for threshold in mr.EV_THRESHOLDS:
            pid = f"residual_p{points}_ev{threshold:.2f}"
            bets = settle_residual_bets(
                heldout_rows,
                points=points,
                threshold=threshold,
            )
            summary = base.summarize_bets(bets)
            early_rows, late_rows = mr.test_halves(bets)
            early = base.summarize_bets(early_rows)
            late = base.summarize_bets(late_rows)
            bootstrap = base.bootstrap_roi(
                summary["daily"],
                samples=BOOTSTRAP_SAMPLES,
                seed=BOOTSTRAP_SEED,
            )
            gate = mr.candidate_gate(
                summary,
                early,
                late,
                bootstrap,
            )
            if gate["passed"]:
                passed.append(pid)
            policies[pid] = {
                "summary": summary,
                "early": early,
                "late": late,
                "bootstrap_roi_percent": bootstrap,
                "research_candidate_gate": gate,
            }

    market_baselines = {
        f"market_top{points}": base.summarize_bets(
            mr.settle_market_top(heldout_rows, points)
        )
        for points in mr.POINT_COUNTS
    }

    out = {
        "contract": "v4_market_residual_lane_model_v1",
        "version": VERSION,
        "period": {
            "calibration_start": CALIB_START.isoformat(),
            "calibration_end": CALIB_END.isoformat(),
            "heldout_start": HOLD_START.isoformat(),
            "heldout_end": HOLD_END.isoformat(),
        },
        "model": {
            "feature_dim": FEATURE_DIM,
            "features": [
                "log_current_over_market",
                "first_lane_onehot_1_to_6",
                "second_lane_onehot_1_to_6",
                "third_lane_onehot_1_to_6",
            ],
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "l2": L2,
            "log_ratio_clip": LOG_RATIO_CLIP,
            "hyperparameter_search": False,
        },
        "coverage": {
            "calibration_races": len(calibration_rows),
            "heldout_races": len(heldout_rows),
            "calibration_dates": sorted(
                {str(row["race_date"]) for row in calibration_rows}
            ),
            "heldout_dates": sorted(
                {str(row["race_date"]) for row in heldout_rows}
            ),
        },
        "training": training,
        "predictive_heldout": predictive,
        "market_baselines_heldout": market_baselines,
        "value_policies_heldout": policies,
        "research_candidate_gate": {
            "passed_policy_ids": passed,
            "positive_requires_separate_prospective_freeze": True,
            "promotion_allowed": False,
        },
        "policy": {
            "heldout_weights_fixed": True,
            "heldout_used_for_training": False,
            "db_write": False,
            "production_change_allowed": False,
            "ticket_count_change_allowed": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "COVERAGE=" + json.dumps(out["coverage"], sort_keys=True),
        flush=True,
    )
    print("TRAINING=" + json.dumps(training, sort_keys=True), flush=True)
    print("PREDICTIVE=" + json.dumps(predictive, sort_keys=True), flush=True)
    print(
        "MARKET_BASELINES="
        + json.dumps(market_baselines, sort_keys=True),
        flush=True,
    )
    for pid, report in sorted(policies.items()):
        s = report["summary"]
        b = report["bootstrap_roi_percent"]
        g = report["research_candidate_gate"]
        print(
            f"POLICY={pid} BETS={s['bets']} RACES={s['races_bet']} "
            f"HITS={s['hits']} ROI={s['roi_percent']} PROFIT={s['profit_yen']} "
            f"EARLY_ROI={report['early']['roi_percent']} "
            f"LATE_ROI={report['late']['roi_percent']} "
            f"MAX_HIT_SHARE={s['largest_hit_share_percent']} "
            f"BOOT_POS={b['positive_share_percent']} "
            f"BOOT95=[{b['p025']},{b['p975']}] "
            f"GATE={int(g['passed'])}",
            flush=True,
        )
    print("PASSED_POLICIES=" + json.dumps(passed), flush=True)
    print("PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_MARKET_RESIDUAL_LANE", flush=True)


if __name__ == "__main__":
    main()
