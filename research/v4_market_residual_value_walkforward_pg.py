# -*- coding: utf-8 -*-
"""Market-relative V4 value walk-forward on the frozen 5-minute odds contract.

This is iterative historical research after the direct V4 raw-EV gate failed.

The position-conditional model is frozen using data through 2026-08-09.  On the
2026-08-25..2026-09-22 timing-safe 5m sample, five market/model blend strengths
are generated for every race *before* results are read.

The first two chronological eligible-day blocks are calibration only.  One beta
is selected by multiclass log loss (Brier, then smaller beta as deterministic
tie-break), not by profit.  That beta is then frozen for the final three blocks.

On the held-out blocks, value tickets are chosen from all 120 trifecta tickets by
q(ticket) * observed_5m_odds, capped at 2 or 3 tickets/race.  This tests genuine
market-relative value rather than merely buying the model's top-ranked tickets.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_timing_safe_profit_gate_pg as base

VERSION = "2026-09-23 v4-market-residual-value-walkforward-v1"
OUTPUT_JSON = Path(
    os.getenv(
        "V4_MARKET_VALUE_OUTPUT_JSON",
        "v4-market-residual-value-walkforward.json",
    )
)
BETA_GRID = (0.0, 0.10, 0.25, 0.50, 1.0)
POINT_COUNTS = (2, 3)
EV_THRESHOLDS = (1.00, 1.05, 1.10)
BLOCKS = 5
WARMUP_BLOCKS = 2
EPS = 1e-15

if base.ODDS_CUTOFF_MINUTES != 5:
    raise RuntimeError("market-relative audit requires the frozen 5m odds contract")
if WARMUP_BLOCKS >= BLOCKS:
    raise RuntimeError("warmup must leave held-out blocks")


def normalize(values: Mapping[str, float]) -> dict[str, float]:
    out = {ticket: max(EPS, float(value)) for ticket, value in values.items()}
    total = sum(out.values())
    if len(out) != 120 or not math.isfinite(total) or total <= 0.0:
        raise ValueError("complete 120-ticket probability map required")
    return {ticket: value / total for ticket, value in out.items()}


def geometric_blend(
    market: Mapping[str, float],
    model: Mapping[str, float],
    beta: float,
) -> dict[str, float]:
    if beta not in BETA_GRID:
        raise ValueError("beta outside preregistered grid")
    m = normalize(market)
    p = normalize(model)
    if set(m) != set(p):
        raise ValueError("market/model ticket support mismatch")
    logs = {
        ticket: (1.0 - beta) * math.log(max(m[ticket], EPS))
        + beta * math.log(max(p[ticket], EPS))
        for ticket in m
    }
    mx = max(logs.values())
    return normalize({ticket: math.exp(value - mx) for ticket, value in logs.items()})


def brier(probs: Mapping[str, float], actual: str) -> float:
    return sum(
        (float(prob) - (1.0 if ticket == actual else 0.0)) ** 2
        for ticket, prob in probs.items()
    )


def predictive_metrics(
    rows: Sequence[Mapping[str, Any]],
    beta: float,
) -> dict[str, Any]:
    if not rows:
        return {"races": 0, "log_loss": None, "brier": None, "mean_rank": None}
    ll = br = rank_sum = 0.0
    for row in rows:
        probs = row["beta_probs"][f"{beta:.2f}"]
        actual = str(row["actual"])
        actual_prob = max(float(probs[actual]), EPS)
        ll += -math.log(actual_prob)
        br += brier(probs, actual)
        target = float(probs[actual])
        rank_sum += 1 + sum(
            1
            for ticket, prob in probs.items()
            if float(prob) > target or (
                float(prob) == target and ticket < actual
            )
        )
    n = len(rows)
    return {
        "races": n,
        "log_loss": round(ll / n, 8),
        "brier": round(br / n, 8),
        "mean_rank": round(rank_sum / n, 4),
    }


def choose_beta(calibration_rows: Sequence[Mapping[str, Any]]) -> tuple[float, dict[str, Any]]:
    metrics = {beta: predictive_metrics(calibration_rows, beta) for beta in BETA_GRID}
    if not calibration_rows:
        return 0.0, {"grid": {f"{b:.2f}": metrics[b] for b in BETA_GRID}}
    chosen = min(
        BETA_GRID,
        key=lambda beta: (
            float(metrics[beta]["log_loss"]),
            float(metrics[beta]["brier"]),
            beta,
        ),
    )
    return chosen, {
        "grid": {f"{b:.2f}": metrics[b] for b in BETA_GRID},
        "selected_beta": chosen,
        "selection_metric": "min_log_loss_then_brier_then_smaller_beta",
    }


def freeze_race(
    race: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> dict[str, Any]:
    odds = {ticket: float(value) for ticket, value in odds_row["odds"].items()}
    market = base.market_probs(odds)
    model = race["probabilities"]["alpha025"]
    beta_probs = {
        f"{beta:.2f}": geometric_blend(market, model, beta)
        for beta in BETA_GRID
    }
    value_tickets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for beta in BETA_GRID:
        label = f"{beta:.2f}"
        probs = beta_probs[label]
        ranked = sorted(
            (
                {
                    "ticket": ticket,
                    "prob": float(probs[ticket]),
                    "odds": odds[ticket],
                    "raw_ev": float(probs[ticket]) * odds[ticket],
                }
                for ticket in probs
            ),
            key=lambda item: (
                -float(item["raw_ev"]),
                -float(item["prob"]),
                item["ticket"],
            ),
        )
        value_tickets[label] = {}
        for points in POINT_COUNTS:
            for threshold in EV_THRESHOLDS:
                pid = f"p{points}_ev{threshold:.2f}"
                eligible = [
                    item for item in ranked
                    if float(item["raw_ev"]) >= threshold
                ][:points]
                value_tickets[label][pid] = eligible

    market_ranked = sorted(
        market,
        key=lambda ticket: (-float(market[ticket]), ticket),
    )
    return {
        "race_id": str(race["race_id"]),
        "race_date": str(race["race_date"]),
        "daily_rank": int(race["daily_rank"]),
        "snapshot_label": str(odds_row["snapshot_label"]),
        "minutes_before_deadline": round(
            float(odds_row["minutes_before_deadline"]), 4
        ),
        "odds": odds,
        "market_probs": market,
        "beta_probs": beta_probs,
        "value_tickets": value_tickets,
        "market_top3": market_ranked[:3],
    }


def settle_bets(
    rows: Sequence[Mapping[str, Any]],
    *,
    beta: float,
    points: int,
    threshold: float,
) -> list[dict[str, Any]]:
    label = f"{beta:.2f}"
    pid = f"p{points}_ev{threshold:.2f}"
    out: list[dict[str, Any]] = []
    for row in rows:
        for rank, bet in enumerate(row["value_tickets"][label][pid], 1):
            hit = str(bet["ticket"]) == str(row["actual"])
            out.append(
                {
                    "race_id": row["race_id"],
                    "race_date": row["race_date"],
                    "rank": rank,
                    "ticket": bet["ticket"],
                    "prob": round(float(bet["prob"]), 12),
                    "odds": round(float(bet["odds"]), 4),
                    "raw_ev": round(float(bet["raw_ev"]), 8),
                    "hit": hit,
                    "return_yen": int(row["payout_yen"]) if hit else 0,
                }
            )
    return out


def settle_market_top(
    rows: Sequence[Mapping[str, Any]],
    points: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        for rank, ticket in enumerate(row["market_top3"][:points], 1):
            hit = ticket == str(row["actual"])
            out.append(
                {
                    "race_id": row["race_id"],
                    "race_date": row["race_date"],
                    "rank": rank,
                    "ticket": ticket,
                    "hit": hit,
                    "return_yen": int(row["payout_yen"]) if hit else 0,
                }
            )
    return out


def split_blocks(rows: Sequence[Mapping[str, Any]]) -> list[list[dict[str, Any]]]:
    dates = sorted({str(row["race_date"]) for row in rows})
    raw_blocks = hist.split_blocks(dates, BLOCKS)
    out: list[list[dict[str, Any]]] = []
    for block_days in raw_blocks:
        allowed = set(block_days)
        out.append(
            [
                dict(row) for row in rows
                if str(row["race_date"]) in allowed
            ]
        )
    return out


def test_halves(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dates = sorted({str(row["race_date"]) for row in rows})
    if len(dates) < 2:
        return list(rows), []
    cut = max(1, len(dates) // 2)
    early_dates = set(dates[:cut])
    late_dates = set(dates[cut:])
    return (
        [dict(row) for row in rows if str(row["race_date"]) in early_dates],
        [dict(row) for row in rows if str(row["race_date"]) in late_dates],
    )


def candidate_gate(
    summary: Mapping[str, Any],
    early: Mapping[str, Any],
    late: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
) -> dict[str, Any]:
    passed = bool(
        int(summary["bets"]) >= 30
        and summary["roi_percent"] is not None
        and float(summary["roi_percent"]) > 100.0
        and early["roi_percent"] is not None
        and late["roi_percent"] is not None
        and float(early["roi_percent"]) > 100.0
        and float(late["roi_percent"]) > 100.0
        and float(summary["largest_hit_share_percent"]) < 50.0
        and bootstrap["positive_share_percent"] is not None
        and float(bootstrap["positive_share_percent"]) >= 90.0
    )
    return {
        "passed": passed,
        "minimum_bets": 30,
        "overall_roi_gt_100": (
            summary["roi_percent"] is not None
            and float(summary["roi_percent"]) > 100.0
        ),
        "both_heldout_halves_roi_gt_100": (
            early["roi_percent"] is not None
            and late["roi_percent"] is not None
            and float(early["roi_percent"]) > 100.0
            and float(late["roi_percent"]) > 100.0
        ),
        "largest_hit_share_lt_50": float(
            summary["largest_hit_share_percent"]
        ) < 50.0,
        "bootstrap_positive_share_ge_90": (
            bootstrap["positive_share_percent"] is not None
            and float(bootstrap["positive_share_percent"]) >= 90.0
        ),
        "promotion_allowed": False,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_MARKET_VALUE_VERSION={VERSION}", flush=True)
    print(
        f"PERIOD={base.TEST_START}..{base.TEST_END} ODDS_CUTOFF=5m "
        f"BETAS={','.join(f'{b:.2f}' for b in BETA_GRID)}",
        flush=True,
    )
    print(
        "DESIGN=FIRST_2_OF_5_ELIGIBLE_DAY_BLOCKS_CALIBRATION_ONLY "
        "LAST_3_BLOCKS_HELD_OUT VALUE_RANK_ALL_120",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY ALL_BETA_CANDIDATES_FROZEN_BEFORE_RESULT "
        "BETA_SELECTED_BY_LOGLOSS_NOT_PROFIT NO_DB_WRITE NO_LINE NO_BUY",
        flush=True,
    )

    frozen_rows: list[dict[str, Any]] = []
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            second_model, third_model, training = base.train_position_models_to_cutoff(cur)

            for day in hist.daterange(base.TEST_START, base.TEST_END):
                selected = base.build_test_day(
                    cur,
                    day,
                    second_model=second_model,
                    third_model=third_model,
                )
                if len(selected) != v4.CORE_RACES:
                    continue
                odds_by = base.latest_coherent_odds(cur, selected)
                # Every beta distribution and all value-ticket grids are frozen
                # before the result query below.
                day_frozen = [
                    freeze_race(row, odds_by[str(row["race_id"])])
                    for row in selected
                    if str(row["race_id"]) in odds_by
                ]
                result_ids = sorted(str(row["race_id"]) for row in day_frozen)
                results = hist.fetch_selected_results(cur, day, result_ids)

                for row in day_frozen:
                    result = results.get(str(row["race_id"]))
                    if not result:
                        continue
                    actual = hist.norm_ticket(result.get("trifecta_ticket"))
                    payout = int(result.get("trifecta_payout_yen") or 0)
                    if actual is None or payout <= 0:
                        continue
                    row["actual"] = actual
                    row["payout_yen"] = payout
                    frozen_rows.append(row)

            conn.rollback()

    blocks = split_blocks(frozen_rows)
    calibration_rows = [
        row
        for block in blocks[:WARMUP_BLOCKS]
        for row in block
    ]
    heldout_rows = [
        row
        for block in blocks[WARMUP_BLOCKS:]
        for row in block
    ]
    selected_beta, calibration = choose_beta(calibration_rows)

    predictive = {
        "market": predictive_metrics(heldout_rows, 0.0),
        "selected": predictive_metrics(heldout_rows, selected_beta),
        "model_only": predictive_metrics(heldout_rows, 1.0),
    }
    predictive["selected_minus_market"] = {
        key: round(
            float(predictive["selected"][key])
            - float(predictive["market"][key]),
            8 if key != "mean_rank" else 4,
        )
        for key in ("log_loss", "brier", "mean_rank")
    }

    market_baselines: dict[str, Any] = {}
    for points in POINT_COUNTS:
        bets = settle_market_top(heldout_rows, points)
        market_baselines[f"market_top{points}"] = base.summarize_bets(bets)

    policies: dict[str, Any] = {}
    passed: list[str] = []
    early_rows, late_rows = test_halves(heldout_rows)
    for points in POINT_COUNTS:
        for threshold in EV_THRESHOLDS:
            pid = f"selected_beta_p{points}_ev{threshold:.2f}"
            bets = settle_bets(
                heldout_rows,
                beta=selected_beta,
                points=points,
                threshold=threshold,
            )
            early_bets = settle_bets(
                early_rows,
                beta=selected_beta,
                points=points,
                threshold=threshold,
            )
            late_bets = settle_bets(
                late_rows,
                beta=selected_beta,
                points=points,
                threshold=threshold,
            )
            summary = base.summarize_bets(bets)
            early_summary = base.summarize_bets(early_bets)
            late_summary = base.summarize_bets(late_bets)
            bootstrap = base.bootstrap_roi(
                summary["daily"],
                samples=base.BOOTSTRAP_SAMPLES,
                seed=base.BOOTSTRAP_SEED,
            )
            gate = candidate_gate(
                summary,
                early_summary,
                late_summary,
                bootstrap,
            )
            if gate["passed"]:
                passed.append(pid)
            policies[pid] = {
                "summary": summary,
                "early": early_summary,
                "late": late_summary,
                "bootstrap_roi_percent": bootstrap,
                "research_candidate_gate": gate,
            }

    block_summary = [
        {
            "block": idx + 1,
            "dates": sorted({str(row["race_date"]) for row in block}),
            "races": len(block),
            "role": "calibration" if idx < WARMUP_BLOCKS else "heldout",
        }
        for idx, block in enumerate(blocks)
    ]

    out = {
        "contract": "v4_market_residual_value_walkforward_v1",
        "version": VERSION,
        "training": training,
        "period": {
            "start": base.TEST_START.isoformat(),
            "end": base.TEST_END.isoformat(),
            "odds_cutoff_minutes": 5,
        },
        "design": {
            "beta_grid": list(BETA_GRID),
            "blocks": BLOCKS,
            "warmup_blocks": WARMUP_BLOCKS,
            "beta_selection": "log_loss_then_brier_then_smaller_beta",
            "profit_used_for_beta_selection": False,
            "value_ticket_universe": 120,
            "point_caps": list(POINT_COUNTS),
            "ev_thresholds": list(EV_THRESHOLDS),
        },
        "coverage": {
            "settled_timing_safe_races": len(frozen_rows),
            "calibration_races": len(calibration_rows),
            "heldout_races": len(heldout_rows),
            "block_summary": block_summary,
        },
        "calibration": calibration,
        "selected_beta": selected_beta,
        "predictive_heldout": predictive,
        "market_baselines_heldout": market_baselines,
        "value_policies_heldout": policies,
        "research_candidate_gate": {
            "passed_policy_ids": passed,
            "iterative_historical_research": True,
            "positive_requires_new_prospective_freeze": True,
        },
        "policy": {
            "production_change_allowed": False,
            "model_change_allowed": False,
            "threshold_change_allowed": False,
            "ticket_count_change_allowed": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("COVERAGE=" + json.dumps(out["coverage"], sort_keys=True), flush=True)
    print("CALIBRATION=" + json.dumps(calibration, sort_keys=True), flush=True)
    print(f"SELECTED_BETA={selected_beta:.2f}", flush=True)
    print("PREDICTIVE=" + json.dumps(predictive, sort_keys=True), flush=True)
    print("MARKET_BASELINES=" + json.dumps(market_baselines, sort_keys=True), flush=True)
    for pid, report in sorted(policies.items()):
        s = report["summary"]
        b = report["bootstrap_roi_percent"]
        print(
            f"POLICY={pid} BETS={s['bets']} RACES={s['races_bet']} "
            f"HITS={s['hits']} ROI={s['roi_percent']} PROFIT={s['profit_yen']} "
            f"EARLY_ROI={report['early']['roi_percent']} "
            f"LATE_ROI={report['late']['roi_percent']} "
            f"MAX_HIT_SHARE={s['largest_hit_share_percent']} "
            f"BOOT_POS={b['positive_share_percent']} "
            f"BOOT95=[{b['p025']},{b['p975']}] "
            f"GATE={int(report['research_candidate_gate']['passed'])}",
            flush=True,
        )
    print("PASSED_POLICIES=" + json.dumps(passed), flush=True)
    print("PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_MARKET_RESIDUAL_VALUE", flush=True)


if __name__ == "__main__":
    main()
