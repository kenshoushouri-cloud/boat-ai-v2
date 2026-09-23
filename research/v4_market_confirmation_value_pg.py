# -*- coding: utf-8 -*-
"""Held-out V4 market-confirmation profitability audit.

This study is separate from raw-EV filtering.  It asks whether current V4 top
tickets become economically useful when the pre-deadline market independently
confirms the same race/ticket structure.

The 2026-08-25..2026-09-22 timing-safe sample is split deterministically into
five chronological eligible-day blocks.  Blocks 1-2 are calibration-only and
are not used for reported profit decisions.  Fixed policies are evaluated only
on blocks 3-5.

All market gates and ticket sets are frozen before result access.
Research only; no Production writes, LINE or purchase behavior.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist
from research import v4_timing_safe_profit_gate_pg as value

VERSION = "2026-09-23 v4-market-confirmation-heldout-v1"
TEST_START = date.fromisoformat(os.getenv("V4_CONFIRM_START", "2026-08-25"))
TEST_END = date.fromisoformat(os.getenv("V4_CONFIRM_END", "2026-09-22"))
OUTPUT_JSON = Path(
    os.getenv("V4_CONFIRM_OUTPUT_JSON", "v4-market-confirmation-heldout.json")
)
BOOTSTRAP_SAMPLES = int(os.getenv("V4_CONFIRM_BOOTSTRAP_SAMPLES", "20000"))
BOOTSTRAP_SEED = int(os.getenv("V4_CONFIRM_BOOTSTRAP_SEED", "20260923"))
UNIT_YEN = 100

SOURCES = ("current", "alpha025")
POINT_COUNTS = (2, 3)
GATES = ("head_agree", "ticket_market10", "head_agree_market10")
MIN_ODDS = (None, 3.0)

if TEST_END < TEST_START:
    raise RuntimeError("invalid confirmation test period")
if BOOTSTRAP_SAMPLES < 100:
    raise RuntimeError("bootstrap samples too small")


def min_odds_label(x: float | None) -> str:
    return "anyodds" if x is None else f"oddsge{x:.1f}"


def policy_id(
    source: str,
    points: int,
    gate: str,
    min_odds: float | None,
) -> str:
    return f"{source}_p{points}_{gate}_{min_odds_label(min_odds)}"


def market_ranks(odds: Mapping[str, float]) -> dict[str, int]:
    ranked = sorted(
        ((ticket, float(odd)) for ticket, odd in odds.items()),
        key=lambda item: (item[1], item[0]),
    )
    if len(ranked) != 120:
        raise ValueError("complete 120 odds required")
    return {
        ticket: idx
        for idx, (ticket, _) in enumerate(ranked, 1)
    }


def first_marginals(probs: Mapping[str, float]) -> dict[int, float]:
    out = {lane: 0.0 for lane in v4.LANES}
    for ticket, prob in v4._normalize_tickets(probs).items():
        out[int(ticket.split("-", 1)[0])] += float(prob)
    return out


def top_head(probs: Mapping[str, float]) -> int:
    heads = first_marginals(probs)
    return sorted(heads.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def freeze_confirmation_policies(
    selected_row: Mapping[str, Any],
    odds_row: Mapping[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    odds = odds_row["odds"]
    market = value.market_probs(odds)
    ranks = market_ranks(odds)
    market_head = top_head(market)
    frozen: dict[str, list[dict[str, Any]]] = {}

    diag = {
        "market_head": market_head,
        "market_top10": list(
            sorted(ranks, key=lambda ticket: ranks[ticket])[:10]
        ),
        "source_head": {},
    }

    for source in SOURCES:
        probs = selected_row["probabilities"][source]
        source_head = top_head(probs)
        diag["source_head"][source] = source_head
        head_agree = source_head == market_head
        top3 = list(v4.top_tickets(probs, 3))

        for points in POINT_COUNTS:
            base = top3[:points]
            for gate in GATES:
                for min_odd in MIN_ODDS:
                    pid = policy_id(source, points, gate, min_odd)
                    bets = []
                    for rank, ticket in enumerate(base, 1):
                        odd = float(odds[ticket])
                        if min_odd is not None and odd < min_odd:
                            continue
                        ticket_market10 = ranks[ticket] <= 10
                        allowed = (
                            (gate == "head_agree" and head_agree)
                            or (gate == "ticket_market10" and ticket_market10)
                            or (
                                gate == "head_agree_market10"
                                and head_agree
                                and ticket_market10
                            )
                        )
                        if not allowed:
                            continue
                        bets.append(
                            {
                                "ticket": ticket,
                                "rank": rank,
                                "prob": float(probs[ticket]),
                                "odds": odd,
                                "market_rank": int(ranks[ticket]),
                                "head_agree": head_agree,
                            }
                        )
                    frozen[pid] = bets
    return frozen, diag


def split_eligible_dates(dates: list[str]) -> list[list[str]]:
    unique = sorted(set(dates))
    blocks = hist.split_blocks(unique, 5)
    return [sorted(block) for block in blocks]


def heldout_halves(rows: list[dict[str, Any]], heldout_dates: list[str]) -> dict[str, Any]:
    midpoint = max(1, len(heldout_dates) // 2)
    early_dates = set(heldout_dates[:midpoint])
    late_dates = set(heldout_dates[midpoint:])
    early = [row for row in rows if row["race_date"] in early_dates]
    late = [row for row in rows if row["race_date"] in late_dates]
    return {
        "early_dates": sorted(early_dates),
        "late_dates": sorted(late_dates),
        "early": value.summarize_bets(early),
        "late": value.summarize_bets(late),
    }


def candidate_gate(
    summary: Mapping[str, Any],
    halves: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
) -> dict[str, Any]:
    early_roi = halves["early"]["roi_percent"]
    late_roi = halves["late"]["roi_percent"]
    passed = bool(
        int(summary["bets"]) >= 30
        and summary["roi_percent"] is not None
        and float(summary["roi_percent"]) > 100.0
        and early_roi is not None
        and float(early_roi) > 100.0
        and late_roi is not None
        and float(late_roi) > 100.0
        and float(summary["largest_hit_share_percent"]) < 50.0
        and bootstrap["positive_share_percent"] is not None
        and float(bootstrap["positive_share_percent"]) >= 90.0
    )
    return {
        "passed": passed,
        "minimum_bets": 30,
        "overall_roi_gt_100": bool(
            summary["roi_percent"] is not None
            and float(summary["roi_percent"]) > 100.0
        ),
        "both_heldout_halves_roi_gt_100": bool(
            early_roi is not None
            and late_roi is not None
            and float(early_roi) > 100.0
            and float(late_roi) > 100.0
        ),
        "largest_hit_share_lt_50": bool(
            float(summary["largest_hit_share_percent"]) < 50.0
        ),
        "bootstrap_positive_share_ge_90": bool(
            bootstrap["positive_share_percent"] is not None
            and float(bootstrap["positive_share_percent"]) >= 90.0
        ),
        "promotion_allowed": False,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_CONFIRM_VERSION={VERSION}", flush=True)
    print(
        f"PERIOD={TEST_START}..{TEST_END} ODDS_CUTOFF={value.ODDS_CUTOFF_MINUTES}m",
        flush=True,
    )
    print(
        "DESIGN=FIRST_2_OF_5_ELIGIBLE_DAY_BLOCKS_CALIBRATION_ONLY "
        "LAST_3_BLOCKS_HELDOUT FIXED_24_POLICIES",
        flush=True,
    )
    print(
        "SAFETY=READ_ONLY ALL_CONFIRMATION_POLICIES_FROZEN_BEFORE_RESULT "
        "NO_HELDOUT_POLICY_SELECTION NO_DB_WRITE NO_LINE NO_BUY NO_PROMOTION",
        flush=True,
    )

    frozen_by_race: dict[str, dict[str, Any]] = {}
    settlement: dict[str, dict[str, Any]] = {}
    eligible_dates: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='30min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            second_model, third_model, training = value.train_position_models_to_cutoff(cur)
            print("TRAINING=" + json.dumps(training, sort_keys=True), flush=True)

            for day in hist.daterange(TEST_START, TEST_END):
                selected = value.build_test_day(
                    cur,
                    day,
                    second_model=second_model,
                    third_model=third_model,
                )
                if len(selected) != v4.CORE_RACES:
                    continue
                odds_by = value.latest_coherent_odds(cur, selected)
                selected_by_id = {
                    str(row["race_id"]): row for row in selected
                }

                # Freeze every policy before result access.
                for rid, odds_row in odds_by.items():
                    policies, diag = freeze_confirmation_policies(
                        selected_by_id[rid],
                        odds_row,
                    )
                    frozen_by_race[rid] = {
                        "race_id": rid,
                        "race_date": day.isoformat(),
                        "policies": policies,
                        "diagnostic": diag,
                    }

                result_ids = sorted(
                    rid
                    for rid, row in frozen_by_race.items()
                    if row["race_date"] == day.isoformat()
                )
                results = hist.fetch_selected_results(cur, day, result_ids)
                day_settled = 0
                for rid in result_ids:
                    result = results.get(rid)
                    if not result:
                        continue
                    actual = hist.norm_ticket(result.get("trifecta_ticket"))
                    payout = int(result.get("trifecta_payout_yen") or 0)
                    if actual is None or payout <= 0:
                        continue
                    settlement[rid] = {
                        "actual": actual,
                        "payout_yen": payout,
                    }
                    day_settled += 1
                if day_settled:
                    eligible_dates.append(day.isoformat())

            conn.rollback()

    blocks = split_eligible_dates(eligible_dates)
    calibration_dates = [d for block in blocks[:2] for d in block]
    heldout_dates = [d for block in blocks[2:] for d in block]
    heldout_set = set(heldout_dates)

    policy_rows: dict[str, list[dict[str, Any]]] = {
        policy_id(source, points, gate, min_odd): []
        for source in SOURCES
        for points in POINT_COUNTS
        for gate in GATES
        for min_odd in MIN_ODDS
    }
    head_agree_races = 0
    heldout_races = 0

    for rid, frozen in sorted(
        frozen_by_race.items(),
        key=lambda item: (item[1]["race_date"], item[0]),
    ):
        if frozen["race_date"] not in heldout_set or rid not in settlement:
            continue
        heldout_races += 1
        if (
            frozen["diagnostic"]["source_head"]["current"]
            == frozen["diagnostic"]["market_head"]
        ):
            head_agree_races += 1

        actual = settlement[rid]["actual"]
        payout = int(settlement[rid]["payout_yen"])
        for pid, bets in frozen["policies"].items():
            for bet in bets:
                hit = bet["ticket"] == actual
                policy_rows[pid].append(
                    {
                        "race_id": rid,
                        "race_date": frozen["race_date"],
                        "rank": int(bet["rank"]),
                        "ticket": bet["ticket"],
                        "odds": round(float(bet["odds"]), 4),
                        "market_rank": int(bet["market_rank"]),
                        "head_agree": bool(bet["head_agree"]),
                        "hit": hit,
                        "return_yen": payout if hit else 0,
                    }
                )

    policies: dict[str, Any] = {}
    passed: list[str] = []
    for pid, rows in sorted(policy_rows.items()):
        summary = value.summarize_bets(rows)
        halves = heldout_halves(rows, heldout_dates)
        bootstrap = value.bootstrap_roi(
            summary["daily"],
            samples=BOOTSTRAP_SAMPLES,
            seed=BOOTSTRAP_SEED,
        )
        gate = candidate_gate(summary, halves, bootstrap)
        if gate["passed"]:
            passed.append(pid)
        policies[pid] = {
            "summary": summary,
            "heldout_halves": halves,
            "bootstrap_roi_percent": bootstrap,
            "research_candidate_gate": gate,
        }

    coverage = {
        "settled_timing_safe_dates": sorted(set(eligible_dates)),
        "blocks": [
            {
                "block": idx,
                "role": "calibration" if idx <= 2 else "heldout",
                "dates": block,
            }
            for idx, block in enumerate(blocks, 1)
        ],
        "calibration_dates": calibration_dates,
        "heldout_dates": heldout_dates,
        "heldout_races": heldout_races,
        "head_agree_races": head_agree_races,
        "head_agree_percent": round(
            head_agree_races / heldout_races * 100.0,
            3,
        ) if heldout_races else 0.0,
    }

    out = {
        "contract": "v4_market_confirmation_heldout_v1",
        "version": VERSION,
        "training": training,
        "period": {
            "start": TEST_START.isoformat(),
            "end": TEST_END.isoformat(),
        },
        "design": {
            "sources": list(SOURCES),
            "point_counts": list(POINT_COUNTS),
            "gates": list(GATES),
            "min_odds": [
                "none" if x is None else x for x in MIN_ODDS
            ],
            "policy_count": len(policy_rows),
            "heldout_policy_selection": False,
            "multiple_comparison_warning": True,
        },
        "coverage": coverage,
        "policies": policies,
        "research_candidate_gate": {
            "passed_policy_ids": passed,
            "historical_positive_is_forward_hypothesis_only": True,
            "promotion_allowed": False,
        },
        "policy": {
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
    for pid, report in sorted(policies.items()):
        s = report["summary"]
        h = report["heldout_halves"]
        b = report["bootstrap_roi_percent"]
        g = report["research_candidate_gate"]
        print(
            f"POLICY={pid} BETS={s['bets']} RACES={s['races_bet']} "
            f"HITS={s['hits']} ROI={s['roi_percent']} PROFIT={s['profit_yen']} "
            f"EARLY_ROI={h['early']['roi_percent']} "
            f"LATE_ROI={h['late']['roi_percent']} "
            f"MAX_HIT_SHARE={s['largest_hit_share_percent']} "
            f"BOOT_POS={b['positive_share_percent']} "
            f"BOOT95=[{b['p025']},{b['p975']}] "
            f"GATE={int(g['passed'])}",
            flush=True,
        )
    print("PASSED_POLICIES=" + json.dumps(passed), flush=True)
    print("PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_MARKET_CONFIRMATION", flush=True)


if __name__ == "__main__":
    main()
