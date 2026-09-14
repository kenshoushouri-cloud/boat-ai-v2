# -*- coding: utf-8 -*-
"""Read-only fixed-stake ROI audit for the timing-safe Bao Value follow-up.

This script is intentionally downstream of the market-residual gate. It reuses the
same frozen Motor2=0.06 + exhibition-time=0.06 model and the same actionable odds
contract from ``value_bao_post_exhibition_market_residual_pg.py``.

Selection contract, frozen before reading this audit's ROI output:
- one ticket maximum per race;
- choose the ticket with the largest ``p_adjusted * observed_odds``;
- evaluate the predeclared gates 1.02 / 1.05 / 1.10 / 1.15 / 1.20;
- flat 100 yen stake only;
- selection uses the earliest coherent 120-ticket odds label captured after the
  exhibition snapshot and before deadline;
- settlement uses official ``v2_results.trifecta_payout_yen`` rather than the
  earlier displayed odds.

All thresholds are reported; this script does not select a winning threshold.
Three forward dates are not enough for Production promotion even if ROI is >100%.
No DB writes, no LINE sends, no purchases, no Production behavior changes.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

import value_bao_post_exhibition_market_residual_pg as base

DB = (os.getenv("DATABASE_URL") or "").strip()
OUTPUT = Path(os.getenv("VALUE_BAO_ROI_OUTPUT", "value-bao-post-exhibition-roi.json"))
THRESHOLDS = (1.02, 1.05, 1.10, 1.15, 1.20)
STAKE_YEN = 100
ODDS_BANDS = (
    (1.5, 2.0, "1.5-2.0"),
    (2.0, 3.0, "2.0-3.0"),
    (3.0, 5.5, "3.0-5.5"),
    (5.5, 10.0, "5.5-10"),
    (10.0, 20.0, "10-20"),
    (20.0, float("inf"), "20+"),
)


def odds_band(odds: float) -> str:
    for lo, hi, label in ODDS_BANDS:
        if lo <= odds < hi:
            return label
    return "<1.5"


def load_payouts(conn: psycopg.Connection[Any], race_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not race_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,result_status,race_status,trifecta_ticket,trifecta_payout_yen
              from v2_results
             where race_id = any(%s)
            """,
            (race_ids,),
        )
        return {str(r["race_id"]): dict(r) for r in cur.fetchall()}


def max_losing_streak(records: list[dict[str, Any]]) -> int:
    longest = current = 0
    for row in sorted(records, key=lambda x: (x["race_date"], x["race_id"])):
        if row["hit"]:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    if not n:
        return {
            "bets": 0,
            "stake_yen": 0,
            "return_yen": 0,
            "profit_yen": 0,
            "roi_pct": None,
            "hits": 0,
            "hit_pct": None,
            "mean_value": None,
            "mean_observed_odds": None,
            "median_observed_odds": None,
            "max_losing_streak": 0,
            "dates": 0,
        }
    stake = n * STAKE_YEN
    returns = sum(int(x["return_yen"]) for x in records)
    hits = sum(int(x["hit"]) for x in records)
    return {
        "bets": n,
        "stake_yen": stake,
        "return_yen": returns,
        "profit_yen": returns - stake,
        "roi_pct": 100.0 * returns / stake,
        "hits": hits,
        "hit_pct": 100.0 * hits / n,
        "mean_value": sum(float(x["value"]) for x in records) / n,
        "mean_observed_odds": sum(float(x["observed_odds"]) for x in records) / n,
        "median_observed_odds": statistics.median(float(x["observed_odds"]) for x in records),
        "max_losing_streak": max_losing_streak(records),
        "dates": len({x["race_date"] for x in records}),
    }


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_BAO_ROI_MODE=read_only_fixed_contract", flush=True)
    print("VALUE_BAO_ROI_MODEL=frozen_motor2_0.06_plus_exhibition_0.06", flush=True)
    print("VALUE_BAO_ROI_SELECTION=top1_value_per_race_flat_100yen", flush=True)
    print("VALUE_BAO_ROI_THRESHOLDS=" + ",".join(f"{x:.2f}" for x in THRESHOLDS), flush=True)
    print("VALUE_BAO_ROI_SETTLEMENT=official_trifecta_payout_yen", flush=True)
    print("VALUE_BAO_ROI_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local idle_in_transaction_session_timeout='30s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")
        rows = base.load_market_rows(conn)
        race_ids = [str(x["race_id"]) for x in rows]
        entries_by = base.load_entries(conn, race_ids)
        payouts = load_payouts(conn, race_ids)
        conn.rollback()

    coverage = Counter()
    top_rows: list[dict[str, Any]] = []
    hit_price_ratios: list[float] = []

    coverage["exhibition_forward_rows"] = len(rows)
    for row in rows:
        rid = str(row["race_id"])
        if row.get("odds_map") is None:
            coverage["no_post_exhibition_complete_market"] += 1
            continue
        result = payouts.get(rid)
        if not result:
            coverage["missing_result"] += 1
            continue
        if str(result.get("result_status") or "").lower() != "official" or str(result.get("race_status") or "").lower() != "official":
            coverage["pending_result"] += 1
            continue
        actual = base.nt(result.get("trifecta_ticket"))
        payout = result.get("trifecta_payout_yen")
        try:
            payout_yen = int(payout)
        except Exception:
            payout_yen = 0
        if actual not in base.TICKETS or payout_yen <= 0:
            coverage["invalid_official_payout"] += 1
            continue

        q = base.devig(row["odds_map"])
        if q is None:
            coverage["invalid_market"] += 1
            continue
        scores = base.feature_scores(row, entries_by.get(rid, []))
        if scores is None:
            coverage["invalid_features"] += 1
            continue
        motor, exhibition = scores
        p = base.adjusted(q, motor, exhibition)

        ranked = []
        for ticket in base.TICKETS:
            try:
                odd = float(row["odds_map"][ticket])
            except Exception:
                continue
            value = float(p[ticket]) * odd
            ranked.append((value, float(p[ticket]), odd, ticket))
        if len(ranked) != 120:
            coverage["invalid_ticket_grid"] += 1
            continue
        value, prob, observed_odds, ticket = max(ranked, key=lambda x: (x[0], x[1], -x[2], x[3]))
        hit = int(ticket == actual)
        return_yen = payout_yen if hit else 0
        if hit and observed_odds > 0:
            hit_price_ratios.append((payout_yen / STAKE_YEN) / observed_odds)

        top_rows.append(
            {
                "race_id": rid,
                "race_date": str(row.get("race_date")),
                "ticket": ticket,
                "prob": prob,
                "value": value,
                "observed_odds": observed_odds,
                "odds_band": odds_band(observed_odds),
                "hit": hit,
                "official_payout_yen": payout_yen,
                "return_yen": return_yen,
            }
        )
        coverage["evaluable_top1"] += 1

    thresholds: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        selected = [x for x in top_rows if x["value"] >= threshold]
        by_date: dict[str, Any] = {}
        for rd in sorted({x["race_date"] for x in selected}):
            by_date[rd] = summarize([x for x in selected if x["race_date"] == rd])
        by_band: dict[str, Any] = {}
        for _, _, band in ODDS_BANDS:
            part = [x for x in selected if x["odds_band"] == band]
            by_band[band] = summarize(part)
        low = [x for x in selected if x["odds_band"] == "<1.5"]
        by_band["<1.5"] = summarize(low)
        thresholds[f"{threshold:.2f}"] = {
            "overall": summarize(selected),
            "by_date": by_date,
            "by_odds_band": by_band,
        }
        m = thresholds[f"{threshold:.2f}"]["overall"]
        print(
            f"VALUE_BAO_ROI_GATE={threshold:.2f} bets:{m['bets']} hits:{m['hits']} "
            f"stake:{m['stake_yen']} return:{m['return_yen']} profit:{m['profit_yen']} "
            f"roi:{m['roi_pct']} max_losing_streak:{m['max_losing_streak']}",
            flush=True,
        )

    # A diagnostic of settlement slippage on winning selections. This does not use
    # the displayed odds as return; official payout is always used above.
    slippage = {
        "winning_top1_n": len(hit_price_ratios),
        "final_payout_multiple_over_observed_odds_mean": (
            sum(hit_price_ratios) / len(hit_price_ratios) if hit_price_ratios else None
        ),
        "final_payout_multiple_over_observed_odds_median": (
            statistics.median(hit_price_ratios) if hit_price_ratios else None
        ),
    }

    profitable_gates = [
        gate for gate, payload in thresholds.items()
        if payload["overall"]["bets"] > 0 and (payload["overall"]["roi_pct"] or 0.0) > 100.0
    ]
    enough_bets_gates = [
        gate for gate, payload in thresholds.items() if payload["overall"]["bets"] >= 30
    ]
    # Deliberately no winner selection: the sample spans only three forward dates.
    status = (
        "PROMISING_BUT_NEEDS_LONGER_FORWARD"
        if profitable_gates and enough_bets_gates
        else "PROFITABILITY_NOT_ESTABLISHED"
    )

    summary = {
        "contract": "value_bao_post_exhibition_roi_v1",
        "selection": {
            "tickets_per_race_max": 1,
            "ranking": "max_adjusted_probability_times_observed_odds",
            "thresholds": list(THRESHOLDS),
            "stake_yen": STAKE_YEN,
            "settlement": "official_trifecta_payout_yen",
            "threshold_winner_selection": False,
        },
        "coverage": dict(coverage),
        "evaluable_top1_dates": sorted({x["race_date"] for x in top_rows}),
        "threshold_results": thresholds,
        "settlement_slippage": slippage,
        "profitable_gates_observed": profitable_gates,
        "gates_with_at_least_30_bets": enough_bets_gates,
        "status": status,
        "sample_warning": "Only three forward dates; no Production promotion or monthly-profit extrapolation is allowed.",
        "promotion_allowed": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"VALUE_BAO_ROI_COVERAGE={json.dumps(dict(coverage), sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_ROI_PROFITABLE_GATES={json.dumps(profitable_gates)}", flush=True)
    print(f"VALUE_BAO_ROI_SETTLEMENT_SLIPPAGE={json.dumps(slippage, sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_ROI_STATUS={status}", flush=True)
    print("VALUE_BAO_ROI_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_BAO_ROI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"VALUE_BAO_ROI_ERROR={type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:700]}",
            flush=True,
        )
        raise
