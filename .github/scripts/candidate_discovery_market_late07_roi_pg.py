# -*- coding: utf-8 -*-
"""Read-only market corroboration proxy restricted to the pre-existing Bao late window.

The 0-7 minute lead window is NOT chosen from ROI outcomes. It is the frozen
late-market collection window already used by bao_early_late_market_shadow.py.
All other rules are inherited unchanged from candidate_discovery_market_corroboration_roi_pg.py.
No DB writes, result-table reads, LINE, BUY, schema or Production changes.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "candidate_discovery_market_corroboration_roi_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_market_corroboration_roi_pg", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(base)

OUTPUT = Path(os.getenv("CANDIDATE_MARKET_LATE07_OUTPUT", "candidate-discovery-market-late07-roi.json"))
LATE_MIN_LO = 0.0
LATE_MIN_HI = 7.0


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("CANDIDATE_MARKET_LATE07_MODE=read_only_existing_bao_window", flush=True)
    print(f"CANDIDATE_MARKET_LATE07_PERIOD={base.START_DATE}..{base.END_DATE}", flush=True)
    print("CANDIDATE_MARKET_LATE07_PROXY=V2_MOTOR2_FACTOR_TOP6_NOT_V4_PRODUCTION_BACKTEST", flush=True)
    print("CANDIDATE_MARKET_LATE07_WINDOW=0.0_7.0_minutes_predeadline_existing_bao_contract", flush=True)
    print("CANDIDATE_MARKET_LATE07_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        labels = base.latest_complete_labels(conn)
        races, entries_by, odds_by = base.load_cards_and_odds(conn, labels)
        conn.rollback()

    selected, structural_probs = base.structural_top6(races, entries_by)
    all_frozen = base.freeze_rows(labels, selected, structural_probs, odds_by)
    frozen = [row for row in all_frozen if LATE_MIN_LO <= float(row["lead_minutes"]) <= LATE_MIN_HI]
    unique_races = {row["race_id"] for row in frozen}
    days = sorted({row["race_date"] for row in frozen})
    leads = [float(row["lead_minutes"]) for row in frozen if row["bet_type"] == "trifecta"]
    coverage = {
        "all_complete_timing_safe_market_races": len(labels),
        "all_structural_top6_market_overlap_races": len({row["race_id"] for row in all_frozen}),
        "late07_structural_overlap_races": len(unique_races),
        "late07_frozen_bet_rows": len(frozen),
        "late07_days": len(days),
        "lead_minutes": base.quantiles(leads),
    }
    print("CANDIDATE_MARKET_LATE07_COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)

    payouts, k_errors = base.fetch_payouts(days)
    print("CANDIDATE_MARKET_LATE07_K_ERRORS=" + json.dumps(k_errors, ensure_ascii=False, sort_keys=True), flush=True)

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    missing = 0
    for row in frozen:
        official = payouts.get(row["race_date"], {}).get((row["venue_id"], row["race_no"], row["bet_type"]))
        if official is None:
            missing += 1
            continue
        evaluated = dict(row)
        evaluated["hit"] = str(official["ticket"]) == row["structural_top1"]
        evaluated["return_yen"] = int(official["payout_yen"]) if evaluated["hit"] else 0
        buckets[(row["bet_type"], "baseline_market_ready")].append(evaluated)
        if row["market_top2_support"]:
            buckets[(row["bet_type"], "market_top2_support")].append(evaluated)
        if row["market_top1_agree"]:
            buckets[(row["bet_type"], "market_top1_agree")].append(evaluated)

    reports = {
        f"{bt}|{view}": base.aggregate(buckets.get((bt, view), []))
        for bt in base.BET_TYPES for view in base.VIEWS
    }
    out = {
        "contract": "candidate_discovery_market_late07_roi_proxy_v1",
        "period": {"start": base.START_DATE, "end": base.END_DATE},
        "window_provenance": "pre-existing Bao late window 0-7 minutes, not outcome-selected",
        "proxy_only": True,
        "proxy_model": "V2_MOTOR2_FACTOR_TOP6",
        "coverage": coverage,
        "k_errors": k_errors,
        "missing_payout_rows": missing,
        "reports": reports,
        "promotion_allowed": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for key in sorted(reports):
        print(f"CANDIDATE_MARKET_LATE07={key} " + json.dumps(reports[key], sort_keys=True), flush=True)
    print(f"CANDIDATE_MARKET_LATE07_MISSING_PAYOUT_ROWS={missing}", flush=True)
    print("CANDIDATE_MARKET_LATE07_PROMOTION=BLOCK_PROXY_ONLY", flush=True)
    print("CANDIDATE_MARKET_LATE07_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
