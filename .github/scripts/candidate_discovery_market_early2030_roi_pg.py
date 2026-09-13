# -*- coding: utf-8 -*-
"""Read-only early-market negative-control audit using the pre-existing Bao 20-30m window.

The 20-30 minute window predates the ROI outcomes and is the established Bao
early market window. It is used as a timing control for the late 0-7m study,
not as an outcome-tuned selector. No DB writes, result-table reads, LINE, BUY,
schema or Production changes.
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

OUTPUT = Path(os.getenv("CANDIDATE_MARKET_EARLY2030_OUTPUT", "candidate-discovery-market-early2030-roi.json"))
EARLY_MIN_LO = 20.0
EARLY_MIN_HI = 30.0


def early_complete_labels(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with grouped as (
              select r.race_id,r.race_date,r.venue_id,r.venue_code,r.race_no,r.deadline_at,
                     o.snapshot_label,
                     count(*)::bigint row_count,
                     count(distinct o.ticket)::bigint ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint positive_odds_count,
                     min(o.snapshot_at) first_snapshot_at,
                     max(o.snapshot_at) last_snapshot_at
                from v2_races r
                join v2_realtime_odds_snapshots o on o.race_id=r.race_id
               where r.race_date between %s and %s
                 and r.deadline_at is not null
                 and o.snapshot_label is not null
               group by r.race_id,r.race_date,r.venue_id,r.venue_code,r.race_no,r.deadline_at,o.snapshot_label
            ), valid as (
              select *,extract(epoch from (last_snapshot_at-first_snapshot_at)) spread_seconds,
                       extract(epoch from (deadline_at-last_snapshot_at))/60.0 lead_minutes
                from grouped
               where row_count=120
                 and ticket_count=120
                 and positive_odds_count=120
                 and last_snapshot_at <= deadline_at
                 and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
            ), windowed as (
              select * from valid where lead_minutes >= %s and lead_minutes <= %s
            )
            select distinct on (race_id)
                   race_id,race_date,venue_id,venue_code,race_no,deadline_at,snapshot_label,
                   first_snapshot_at,last_snapshot_at,spread_seconds,lead_minutes
              from windowed
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (base.START_DATE, base.END_DATE, base.MAX_LABEL_SPREAD_SECONDS, EARLY_MIN_LO, EARLY_MIN_HI),
        )
        return [dict(row) for row in cur.fetchall()]


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("CANDIDATE_MARKET_EARLY2030_MODE=read_only_existing_bao_window_negative_control", flush=True)
    print(f"CANDIDATE_MARKET_EARLY2030_PERIOD={base.START_DATE}..{base.END_DATE}", flush=True)
    print("CANDIDATE_MARKET_EARLY2030_PROXY=V2_MOTOR2_FACTOR_TOP6_NOT_V4_PRODUCTION_BACKTEST", flush=True)
    print("CANDIDATE_MARKET_EARLY2030_WINDOW=20.0_30.0_minutes_predeadline_existing_bao_contract", flush=True)
    print("CANDIDATE_MARKET_EARLY2030_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        labels = early_complete_labels(conn)
        races, entries_by, odds_by = base.load_cards_and_odds(conn, labels)
        conn.rollback()

    selected, structural_probs = base.structural_top6(races, entries_by)
    frozen = base.freeze_rows(labels, selected, structural_probs, odds_by)
    unique_races = {row["race_id"] for row in frozen}
    days = sorted({row["race_date"] for row in frozen})
    leads = [float(row["lead_minutes"]) for row in frozen if row["bet_type"] == "trifecta"]
    coverage = {
        "early2030_complete_market_races": len(labels),
        "early2030_structural_overlap_races": len(unique_races),
        "early2030_frozen_bet_rows": len(frozen),
        "early2030_days": len(days),
        "lead_minutes": base.quantiles(leads),
    }
    print("CANDIDATE_MARKET_EARLY2030_COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)

    payouts, k_errors = base.fetch_payouts(days)
    print("CANDIDATE_MARKET_EARLY2030_K_ERRORS=" + json.dumps(k_errors, ensure_ascii=False, sort_keys=True), flush=True)

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
        "contract": "candidate_discovery_market_early2030_roi_control_v1",
        "period": {"start": base.START_DATE, "end": base.END_DATE},
        "window_provenance": "pre-existing Bao early window 20-30 minutes, negative control",
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
        print(f"CANDIDATE_MARKET_EARLY2030={key} " + json.dumps(reports[key], sort_keys=True), flush=True)
    print(f"CANDIDATE_MARKET_EARLY2030_MISSING_PAYOUT_ROWS={missing}", flush=True)
    print("CANDIDATE_MARKET_EARLY2030_PROMOTION=BLOCK_NEGATIVE_CONTROL_ONLY", flush=True)
    print("CANDIDATE_MARKET_EARLY2030_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
