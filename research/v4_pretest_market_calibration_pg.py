# -*- coding: utf-8 -*-
"""Pre-test calibrated market/current-V4 residual value audit.

Calibration:
  2026-07-01..2026-08-24, timing-safe complete 120-ticket 5m odds only.
Held-out:
  2026-08-25..2026-09-22, never used to choose beta.

Only current V4 is blended with the de-vigged market, so calibration dates do
not depend on the later position-conditional alpha0.25 training cutoff.

Beta is chosen by calibration multiclass LogLoss (Brier, then smaller beta),
never by ROI.  The chosen beta is frozen for the entire held-out period.
All beta distributions and candidate bets are frozen before result access.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_position_conditional_tail_walkforward_pg as pos
from research import v4_timing_safe_profit_gate_pg as base
from research import v4_market_residual_value_walkforward_pg as mr

VERSION = "2026-09-23 v4-pretest-market-calibration-v1"
CALIB_START = date(2026, 7, 1)
CALIB_END = date(2026, 8, 24)
HOLD_START = date(2026, 8, 25)
HOLD_END = date(2026, 9, 22)
OUTPUT_JSON = Path(
    os.getenv(
        "V4_PRETEST_MARKET_OUTPUT_JSON",
        "v4-pretest-market-calibration.json",
    )
)
BOOTSTRAP_SAMPLES = int(os.getenv("V4_PRETEST_MARKET_BOOTSTRAP_SAMPLES", "20000"))
BOOTSTRAP_SEED = int(os.getenv("V4_PRETEST_MARKET_BOOTSTRAP_SEED", "20260923"))

if base.ODDS_CUTOFF_MINUTES != 5:
    raise RuntimeError("pre-test calibration requires frozen 5m odds contract")


def freeze_current_race(
    race: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> dict[str, Any]:
    odds = {ticket: float(value) for ticket, value in odds_row["odds"].items()}
    market = base.market_probs(odds)
    model = race["probabilities"]["current"]
    beta_probs = {
        f"{beta:.2f}": mr.geometric_blend(market, model, beta)
        for beta in mr.BETA_GRID
    }

    value_tickets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for beta in mr.BETA_GRID:
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
        for points in mr.POINT_COUNTS:
            for threshold in mr.EV_THRESHOLDS:
                pid = f"p{points}_ev{threshold:.2f}"
                value_tickets[label][pid] = [
                    item for item in ranked
                    if float(item["raw_ev"]) >= threshold
                ][:points]

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
        "market_probs": market,
        "beta_probs": beta_probs,
        "value_tickets": value_tickets,
        "market_top3": market_ranked[:3],
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_PRETEST_MARKET_VERSION={VERSION}", flush=True)
    print(
        f"CALIBRATION={CALIB_START}..{CALIB_END} "
        f"HELDOUT={HOLD_START}..{HOLD_END}",
        flush=True,
    )
    print(
        f"ODDS_CUTOFF={base.ODDS_CUTOFF_MINUTES}m "
        f"BETAS={','.join(f'{b:.2f}' for b in mr.BETA_GRID)}",
        flush=True,
    )
    print(
        "DESIGN=BETA_FROM_PRETEST_LOGLOSS_ONLY HELDOUT_PROFIT_NEVER_SELECTS_BETA "
        "CURRENT_V4_ONLY RESULT_AFTER_ALL_BETA_FREEZE",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY NO_DB_WRITE NO_LINE NO_BUY NO_PROMOTION",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    # Zero tail models are passed only because the shared day builder also
    # constructs alpha025; this audit reads current probabilities only.
    dummy_second = pos.PairwiseLogit(pos.SECOND_DIM)
    dummy_third = pos.PairwiseLogit(pos.THIRD_DIM)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            for day in hist.daterange(CALIB_START, HOLD_END):
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

                # Freeze every beta/value candidate before results are read.
                frozen = {
                    rid: freeze_current_race(selected_by_id[rid], odds_row)
                    for rid, odds_row in odds_by.items()
                }
                results = hist.fetch_selected_results(
                    cur,
                    day,
                    sorted(frozen),
                )
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
            conn.rollback()

    calibration_rows = [
        row for row in rows
        if CALIB_START <= date.fromisoformat(str(row["race_date"])) <= CALIB_END
    ]
    heldout_rows = [
        row for row in rows
        if HOLD_START <= date.fromisoformat(str(row["race_date"])) <= HOLD_END
    ]

    selected_beta, calibration = mr.choose_beta(calibration_rows)
    predictive = {
        "market": mr.predictive_metrics(heldout_rows, 0.0),
        "selected": mr.predictive_metrics(heldout_rows, selected_beta),
        "model_only": mr.predictive_metrics(heldout_rows, 1.0),
    }
    predictive["selected_minus_market"] = {
        key: round(
            float(predictive["selected"][key])
            - float(predictive["market"][key]),
            8 if key in ("log_loss", "brier") else 4,
        )
        for key in ("log_loss", "brier", "mean_rank")
    }

    market_baselines = {}
    for points in mr.POINT_COUNTS:
        bets = mr.settle_market_top(heldout_rows, points)
        market_baselines[f"market_top{points}"] = base.summarize_bets(bets)

    policies: dict[str, Any] = {}
    passed: list[str] = []
    for points in mr.POINT_COUNTS:
        for threshold in mr.EV_THRESHOLDS:
            pid = f"selected_beta_p{points}_ev{threshold:.2f}"
            bets = mr.settle_bets(
                heldout_rows,
                beta=selected_beta,
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
            gate = mr.candidate_gate(summary, early, late, bootstrap)
            if gate["passed"]:
                passed.append(pid)
            policies[pid] = {
                "summary": summary,
                "early": early,
                "late": late,
                "bootstrap_roi_percent": bootstrap,
                "research_candidate_gate": gate,
            }

    coverage = {
        "calibration_races": len(calibration_rows),
        "heldout_races": len(heldout_rows),
        "calibration_dates": sorted(
            {str(row["race_date"]) for row in calibration_rows}
        ),
        "heldout_dates": sorted(
            {str(row["race_date"]) for row in heldout_rows}
        ),
    }
    out = {
        "contract": "v4_pretest_market_calibration_v1",
        "version": VERSION,
        "period": {
            "calibration_start": CALIB_START.isoformat(),
            "calibration_end": CALIB_END.isoformat(),
            "heldout_start": HOLD_START.isoformat(),
            "heldout_end": HOLD_END.isoformat(),
        },
        "design": {
            "probability_source": "current_v4_only",
            "beta_grid": list(mr.BETA_GRID),
            "beta_selection": "pretest_log_loss_then_brier_then_smaller_beta",
            "heldout_profit_used_for_beta_selection": False,
            "point_caps": list(mr.POINT_COUNTS),
            "ev_thresholds": list(mr.EV_THRESHOLDS),
        },
        "coverage": coverage,
        "calibration": calibration,
        "selected_beta": selected_beta,
        "predictive_heldout": predictive,
        "market_baselines_heldout": market_baselines,
        "value_policies_heldout": policies,
        "research_candidate_gate": {
            "passed_policy_ids": passed,
            "positive_requires_new_prospective_freeze": True,
            "promotion_allowed": False,
        },
        "policy": {
            "db_write": False,
            "production_change_allowed": False,
            "ticket_count_change_allowed": False,
            "threshold_change_allowed": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)
    print("CALIBRATION=" + json.dumps(calibration, sort_keys=True), flush=True)
    print(f"SELECTED_BETA={selected_beta:.2f}", flush=True)
    print("PREDICTIVE=" + json.dumps(predictive, sort_keys=True), flush=True)
    print(
        "MARKET_BASELINES=" + json.dumps(market_baselines, sort_keys=True),
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
    print("RESULT=PASS_READ_ONLY_PRETEST_MARKET_CALIBRATION", flush=True)


if __name__ == "__main__":
    main()
