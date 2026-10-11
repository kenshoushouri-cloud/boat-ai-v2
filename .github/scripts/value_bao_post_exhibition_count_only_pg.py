# -*- coding: utf-8 -*-
"""Outcome-blind Bao post-exhibition Value density audit.

Uses the already-frozen Motor2=0.06 + exhibition=0.06 probability adjustment and
timing-safe post-exhibition market contract, but never reads results or payouts.
The purpose is only to measure how many races have top1 p_adjusted*odds at fixed
economically meaningful thresholds before choosing any future hypothesis.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent
for p in (ROOT, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import value_bao_post_exhibition_market_residual_pg as base

DB = (os.getenv("DATABASE_URL") or "").strip()
OUTPUT = Path(os.getenv("VALUE_BAO_COUNT_OUTPUT", "value-bao-post-exhibition-count-only.json"))
THRESHOLDS = (1.00, 1.01, 1.02, 1.05)
ODDS_BANDS = (
    (1.0, 3.0, "1-3"),
    (3.0, 6.0, "3-6"),
    (6.0, 10.0, "6-10"),
    (10.0, 20.0, "10-20"),
    (20.0, 30.0, "20-30"),
    (30.0, 50.0, "30-50"),
    (50.0, float("inf"), "50+"),
)


def odds_band(odd: float) -> str:
    for lo, hi, label in ODDS_BANDS:
        if lo <= odd < hi:
            return label
    return "other"


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return round(xs[lo], 6)
    w = pos - lo
    return round(xs[lo] * (1.0 - w) + xs[hi] * w, 6)


def load_market_rows_outcome_blind(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with ex as (
              select race_id,race_date,venue_id,race_no,captured_at,deadline_at,
                     minutes_before,exhibition_time_ranks
                from v2_bao_exhibition_shadow_snapshots
            ), grouped as (
              select ex.race_id,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from ex
                join v2_realtime_odds_snapshots o on o.race_id=ex.race_id
               where o.snapshot_label is not null
               group by ex.race_id,ex.captured_at,ex.deadline_at,o.snapshot_label
              having count(*)=120
                 and count(distinct o.ticket)=120
                 and count(*) filter (where o.odds is not null and o.odds > 1.0)=120
                 and min(o.snapshot_at) >= ex.captured_at
                 and max(o.snapshot_at) <= ex.deadline_at
                 and extract(epoch from (max(o.snapshot_at)-min(o.snapshot_at))) <= %s
            ), chosen as (
              select distinct on (race_id)
                     race_id,snapshot_label,first_snapshot_at,last_snapshot_at
                from grouped
               order by race_id,first_snapshot_at asc,snapshot_label
            ), market as (
              select ch.race_id,ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at,
                     jsonb_object_agg(o.ticket,o.odds) as odds_map
                from chosen ch
                join v2_realtime_odds_snapshots o
                  on o.race_id=ch.race_id and o.snapshot_label=ch.snapshot_label
               group by ch.race_id,ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at
            )
            select ex.*,m.snapshot_label,m.first_snapshot_at,m.last_snapshot_at,m.odds_map
              from ex
              left join market m on m.race_id=ex.race_id
             order by ex.race_date,ex.venue_id,ex.race_no,ex.race_id
            """,
            (base.MAX_LABEL_SPREAD_SECONDS,),
        )
        return [dict(x) for x in cur.fetchall()]


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("VALUE_BAO_COUNT_MODE=outcome_blind_count_only", flush=True)
    print(f"VALUE_BAO_COUNT_FIXED=motor2:{base.MOTOR_BETA:.2f} exhibition:{base.EXHIBITION_BETA:.2f}", flush=True)
    print("VALUE_BAO_COUNT_THRESHOLDS=" + ",".join(f"{x:.2f}" for x in THRESHOLDS), flush=True)
    print("VALUE_BAO_COUNT_RESULTS_READ=0 PAYOUTS_READ=0 ROI_CALCULATED=0 DB_WRITE=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        rows = load_market_rows_outcome_blind(conn)
        entries_by = base.load_entries(conn, [str(x["race_id"]) for x in rows])
        conn.rollback()

    coverage = Counter()
    top_rows: list[dict[str, Any]] = []
    coverage["exhibition_forward_rows"] = len(rows)
    for row in rows:
        if row.get("odds_map") is None:
            coverage["no_post_exhibition_complete_market"] += 1
            continue
        q = base.devig(row["odds_map"])
        if q is None:
            coverage["invalid_market"] += 1
            continue
        scores = base.feature_scores(row, entries_by.get(str(row["race_id"]), []))
        if scores is None:
            coverage["invalid_features"] += 1
            continue
        motor, exhibition = scores
        p = base.adjusted(q, motor, exhibition)
        ranked: list[tuple[float, float, float, str]] = []
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
        value, prob, odd, ticket = max(ranked, key=lambda x: (x[0], x[1], -x[2], x[3]))
        top_rows.append({
            "race_id": str(row["race_id"]),
            "race_date": str(row.get("race_date"))[:10],
            "venue_id": str(row.get("venue_id") or "").zfill(2),
            "race_no": int(row.get("race_no") or 0),
            "ticket": ticket,
            "value": value,
            "prob": prob,
            "odds": odd,
            "odds_band": odds_band(odd),
        })
        coverage["evaluable_top1"] += 1

    values = [float(x["value"]) for x in top_rows]
    distribution = {
        "min": round(min(values), 6) if values else None,
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": round(max(values), 6) if values else None,
    }

    gates: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        selected = [x for x in top_rows if float(x["value"]) >= threshold]
        by_date = Counter(x["race_date"] for x in selected)
        by_band = Counter(x["odds_band"] for x in selected)
        gates[f"{threshold:.2f}"] = {
            "races": len(selected),
            "dates": len(by_date),
            "by_date": dict(sorted(by_date.items())),
            "by_odds_band": dict(sorted(by_band.items())),
        }
        print(
            f"VALUE_BAO_COUNT_GATE={threshold:.2f} races:{len(selected)} dates:{len(by_date)} "
            f"odds_bands:{json.dumps(dict(sorted(by_band.items())), sort_keys=True)}",
            flush=True,
        )

    out = {
        "contract": "bao_post_exhibition_value_density_count_only_v1",
        "fixed_coefficients": {"motor2": base.MOTOR_BETA, "exhibition": base.EXHIBITION_BETA},
        "thresholds": list(THRESHOLDS),
        "coverage": dict(coverage),
        "top1_value_distribution": distribution,
        "gates": gates,
        "outcomes_read": False,
        "payouts_read": False,
        "roi_calculated": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("VALUE_BAO_COUNT_COVERAGE=" + json.dumps(dict(coverage), sort_keys=True), flush=True)
    print("VALUE_BAO_COUNT_DISTRIBUTION=" + json.dumps(distribution, sort_keys=True), flush=True)
    print("VALUE_BAO_COUNT_RESULTS_READ=0", flush=True)
    print("VALUE_BAO_COUNT_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_BAO_COUNT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
