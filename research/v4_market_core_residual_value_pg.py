# -*- coding: utf-8 -*-
"""Market-core residual value audit for V4 alpha=0.25.

Iterative historical research after unrestricted all-120 residual EV failed.

The hypothesis is deliberately small:
- preserve the current V4 exact six selected races;
- use only the frozen alpha=0.25 probability source;
- use timing-safe coherent 5-minute market snapshots;
- restrict candidates to market ranks <= 5, 10 or 20;
- within that market core, keep only tickets alpha0.25 rates above the
  de-vigged market probability;
- rank by log(alpha0.25 / market) and buy the best 2 or 3.

No ROI threshold, odds band, venue/date rule or model coefficient is fitted from
the test results. All six policies are frozen before any result is read.
Positive history can only nominate a prospective Forward shadow.
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_timing_safe_profit_gate_pg as base

VERSION = "2026-09-23 v4-market-core-residual-v1"
OUTPUT_JSON = Path(
    os.getenv("V4_MARKET_CORE_OUTPUT_JSON", "v4-market-core-residual-value.json")
)
MARKET_RANK_CAPS = (5, 10, 20)
POINT_COUNTS = (2, 3)
UNIT_YEN = 100
BOOTSTRAP_SAMPLES = int(os.getenv("V4_MARKET_CORE_BOOTSTRAP_SAMPLES", "20000"))
BOOTSTRAP_SEED = int(os.getenv("V4_MARKET_CORE_BOOTSTRAP_SEED", "20260923"))

if base.ODDS_CUTOFF_MINUTES != 5:
    raise RuntimeError("market-core residual requires frozen deadline-5m odds")
if base.TEST_START.isoformat() != "2026-08-25" or base.TEST_END.isoformat() != "2026-09-22":
    raise RuntimeError("market-core residual test period drift")


def policy_id(cap: int, points: int) -> str:
    return f"market_top{cap}_residual_p{points}"


def freeze_race(
    row: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    odds = {ticket: float(value) for ticket, value in odds_row["odds"].items()}
    market = base.market_probs(odds)
    model = v4._normalize_tickets(row["probabilities"]["alpha025"])
    if set(market) != set(model):
        raise RuntimeError("market/model support mismatch")

    market_ranked = sorted(
        market,
        key=lambda ticket: (-float(market[ticket]), ticket),
    )
    market_rank = {ticket: idx for idx, ticket in enumerate(market_ranked, 1)}

    candidates = []
    for ticket in market_ranked:
        m = float(market[ticket])
        p = float(model[ticket])
        ratio = p / m if m > 0.0 else 0.0
        candidates.append(
            {
                "ticket": ticket,
                "market_rank": market_rank[ticket],
                "market_prob": m,
                "model_prob": p,
                "residual_ratio": ratio,
                "residual_log": math.log(max(ratio, 1e-15)),
                "odds": odds[ticket],
                "raw_model_ev": p * odds[ticket],
            }
        )

    frozen: dict[str, list[dict[str, Any]]] = {}
    for cap in MARKET_RANK_CAPS:
        eligible = [
            item
            for item in candidates
            if int(item["market_rank"]) <= cap
            and float(item["residual_ratio"]) > 1.0
        ]
        eligible.sort(
            key=lambda item: (
                -float(item["residual_log"]),
                -float(item["model_prob"]),
                int(item["market_rank"]),
                str(item["ticket"]),
            )
        )
        for points in POINT_COUNTS:
            frozen[policy_id(cap, points)] = [
                dict(item) for item in eligible[:points]
            ]
    return frozen


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            str(row["race_date"]),
            str(row["race_id"]),
            int(row["rank"]),
        ),
    )
    bets = len(ordered)
    investment = bets * UNIT_YEN
    gross = sum(int(row["return_yen"]) for row in ordered)
    hits = sum(int(bool(row["hit"])) for row in ordered)
    returns = sorted(
        (int(row["return_yen"]) for row in ordered if row["hit"]),
        reverse=True,
    )

    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    equity = peak = max_dd = losing = max_losing = 0
    for row in ordered:
        profit = int(row["return_yen"]) - UNIT_YEN
        equity += profit
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if row["hit"]:
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        by_date[str(row["race_date"])].append(row)

    daily = []
    for day, rr in sorted(by_date.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(int(row["return_yen"]) for row in rr)
        daily.append(
            {
                "date": day,
                "bets": len(rr),
                "investment_yen": inv,
                "return_yen": ret,
            }
        )

    ratios = [float(row["residual_ratio"]) for row in ordered]
    market_ranks = [int(row["market_rank"]) for row in ordered]
    return {
        "bets": bets,
        "races_bet": len({str(row["race_id"]) for row in ordered}),
        "hits": hits,
        "hit_rate_percent": round(hits / bets * 100.0, 3) if bets else None,
        "investment_yen": investment,
        "return_yen": gross,
        "profit_yen": gross - investment,
        "roi_percent": round(gross / investment * 100.0, 3)
        if investment else None,
        "max_hit_yen": returns[0] if returns else 0,
        "largest_hit_share_percent": round(
            returns[0] / gross * 100.0, 3
        ) if returns and gross else 0.0,
        "max_losing_streak_bets": max_losing,
        "max_drawdown_yen": max_dd,
        "mean_residual_ratio": round(sum(ratios) / len(ratios), 6)
        if ratios else None,
        "mean_market_rank": round(sum(market_ranks) / len(market_ranks), 4)
        if market_ranks else None,
        "daily": daily,
    }


def halves(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dates = sorted({str(row["race_date"]) for row in rows})
    if len(dates) < 2:
        return [dict(row) for row in rows], []
    cut = max(1, len(dates) // 2)
    early = set(dates[:cut])
    return (
        [dict(row) for row in rows if str(row["race_date"]) in early],
        [dict(row) for row in rows if str(row["race_date"]) not in early],
    )


def bootstrap_roi(
    daily: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not daily:
        return {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": BOOTSTRAP_SEED,
            "p025": None,
            "median": None,
            "p975": None,
            "positive_share_percent": None,
        }
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(daily)
    values = []
    for _ in range(BOOTSTRAP_SAMPLES):
        inv = ret = 0
        for _ in range(n):
            row = daily[rng.randrange(n)]
            inv += int(row["investment_yen"])
            ret += int(row["return_yen"])
        if inv:
            values.append(ret / inv * 100.0)
    values.sort()

    def q(p: float) -> float | None:
        if not values:
            return None
        idx = int(round((len(values) - 1) * p))
        return round(values[max(0, min(idx, len(values) - 1))], 3)

    positive = sum(1 for value in values if value > 100.0)
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "p025": q(0.025),
        "median": q(0.50),
        "p975": q(0.975),
        "positive_share_percent": round(
            positive / len(values) * 100.0, 3
        ) if values else None,
    }


def candidate_gate(
    summary: Mapping[str, Any],
    early: Mapping[str, Any],
    late: Mapping[str, Any],
    boot: Mapping[str, Any],
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
        and boot["positive_share_percent"] is not None
        and float(boot["positive_share_percent"]) >= 90.0
    )
    return {
        "passed": passed,
        "minimum_bets": 30,
        "overall_roi_gt_100": (
            summary["roi_percent"] is not None
            and float(summary["roi_percent"]) > 100.0
        ),
        "both_halves_roi_gt_100": (
            early["roi_percent"] is not None
            and late["roi_percent"] is not None
            and float(early["roi_percent"]) > 100.0
            and float(late["roi_percent"]) > 100.0
        ),
        "largest_hit_share_lt_50": float(
            summary["largest_hit_share_percent"]
        ) < 50.0,
        "bootstrap_positive_share_ge_90": (
            boot["positive_share_percent"] is not None
            and float(boot["positive_share_percent"]) >= 90.0
        ),
        "promotion_allowed": False,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_MARKET_CORE_VERSION={VERSION}", flush=True)
    print(
        f"PERIOD={base.TEST_START}..{base.TEST_END} "
        f"ODDS_CUTOFF={base.ODDS_CUTOFF_MINUTES}m",
        flush=True,
    )
    print(
        "POLICIES=market_rank_caps:5,10,20 points:2,3 "
        "RULE=alpha025_prob_gt_devig_market rank_by_log_residual",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY ALL_POLICIES_FROZEN_BEFORE_RESULT "
        "ITERATIVE_HISTORY_FORWARD_HYPOTHESIS_ONLY NO_DB_WRITE NO_LINE NO_BUY",
        flush=True,
    )

    policy_rows: dict[str, list[dict[str, Any]]] = {
        policy_id(cap, points): []
        for cap in MARKET_RANK_CAPS
        for points in POINT_COUNTS
    }
    coverage = {
        "calendar_days": (base.TEST_END - base.TEST_START).days + 1,
        "selected_races": 0,
        "timing_safe_odds_races": 0,
        "settled_races": 0,
    }

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            second_model, third_model, training = base.train_position_models_to_cutoff(cur)
            print("TRAINING=" + json.dumps(training, sort_keys=True), flush=True)

            for day in hist.daterange(base.TEST_START, base.TEST_END):
                selected = base.build_test_day(
                    cur,
                    day,
                    second_model=second_model,
                    third_model=third_model,
                )
                if len(selected) != v4.CORE_RACES:
                    continue
                coverage["selected_races"] += len(selected)
                odds_by = base.latest_coherent_odds(cur, selected)
                frozen = {}
                for row in selected:
                    rid = str(row["race_id"])
                    if rid not in odds_by:
                        continue
                    frozen[rid] = freeze_race(row, odds_by[rid])
                coverage["timing_safe_odds_races"] += len(frozen)

                # Settlement starts only after all six candidate policies are
                # frozen for every odds-ready selected race.
                results = hist.fetch_selected_results(cur, day, sorted(frozen))
                selected_by_id = {
                    str(row["race_id"]): row for row in selected
                }
                for rid, policies in frozen.items():
                    result = results.get(rid)
                    if not result:
                        continue
                    actual = hist.norm_ticket(result.get("trifecta_ticket"))
                    payout = int(result.get("trifecta_payout_yen") or 0)
                    if actual is None or payout <= 0:
                        continue
                    coverage["settled_races"] += 1
                    for pid, bets in policies.items():
                        for rank, bet in enumerate(bets, 1):
                            hit = str(bet["ticket"]) == actual
                            policy_rows[pid].append(
                                {
                                    "race_id": rid,
                                    "race_date": day.isoformat(),
                                    "rank": rank,
                                    "ticket": str(bet["ticket"]),
                                    "market_rank": int(bet["market_rank"]),
                                    "residual_ratio": round(
                                        float(bet["residual_ratio"]), 8
                                    ),
                                    "raw_model_ev": round(
                                        float(bet["raw_model_ev"]), 8
                                    ),
                                    "odds": round(float(bet["odds"]), 4),
                                    "hit": hit,
                                    "return_yen": payout if hit else 0,
                                }
                            )
            conn.rollback()

    reports = {}
    passed = []
    for pid, rows in sorted(policy_rows.items()):
        summary = summarize(rows)
        early_rows, late_rows = halves(rows)
        early = summarize(early_rows)
        late = summarize(late_rows)
        boot = bootstrap_roi(summary["daily"])
        gate = candidate_gate(summary, early, late, boot)
        if gate["passed"]:
            passed.append(pid)
        reports[pid] = {
            "summary": summary,
            "early": early,
            "late": late,
            "bootstrap_roi_percent": boot,
            "research_candidate_gate": gate,
        }

    out = {
        "contract": "v4_market_core_residual_value_v1",
        "version": VERSION,
        "training": training,
        "period": {
            "start": base.TEST_START.isoformat(),
            "end": base.TEST_END.isoformat(),
            "odds_cutoff_minutes": base.ODDS_CUTOFF_MINUTES,
        },
        "design": {
            "probability_source": "alpha025_frozen_before_test",
            "market_rank_caps": list(MARKET_RANK_CAPS),
            "point_counts": list(POINT_COUNTS),
            "eligibility": "alpha025_probability_gt_devig_market_probability",
            "ranking": "descending_log_alpha025_over_market",
            "profit_used_for_rule_selection": False,
            "iterative_historical_research": True,
        },
        "coverage": coverage,
        "policies": reports,
        "research_candidate_gate": {
            "passed_policy_ids": passed,
            "multiple_comparison_warning": True,
            "positive_requires_new_prospective_freeze": True,
        },
        "policy": {
            "production_change_allowed": False,
            "threshold_change_allowed": False,
            "ticket_count_change_allowed": False,
            "purchase_action": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)
    for pid, report in sorted(reports.items()):
        s = report["summary"]
        b = report["bootstrap_roi_percent"]
        g = report["research_candidate_gate"]
        print(
            f"POLICY={pid} BETS={s['bets']} RACES={s['races_bet']} "
            f"HITS={s['hits']} ROI={s['roi_percent']} PROFIT={s['profit_yen']} "
            f"EARLY_ROI={report['early']['roi_percent']} "
            f"LATE_ROI={report['late']['roi_percent']} "
            f"MEAN_MARKET_RANK={s['mean_market_rank']} "
            f"MEAN_RESIDUAL={s['mean_residual_ratio']} "
            f"MAX_HIT_SHARE={s['largest_hit_share_percent']} "
            f"BOOT_POS={b['positive_share_percent']} "
            f"BOOT95=[{b['p025']},{b['p975']}] GATE={int(g['passed'])}",
            flush=True,
        )
    print("PASSED_POLICIES=" + json.dumps(passed), flush=True)
    print("PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_MARKET_CORE_RESIDUAL", flush=True)


if __name__ == "__main__":
    main()
