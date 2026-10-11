# -*- coding: utf-8 -*-
"""Read-only timing-safe market-residual audit for Course + Opponent.

This audit reuses the frozen research contract from PR #326:
- Racer Course coefficient = 0.50 fixed.
- Opponent Pressure coefficient = 1.0 fixed.
- Opponent delta changes only the first-place marginal while preserving
  P(second, third | first).

It joins only coherent 120-ticket realtime odds labels whose final ticket row was
captured before the race deadline. Market probability is de-vigged inverse odds.
A small market/model residual blend alpha is selected on strictly earlier dates
and frozen on each future test window.

Research-only: no DB writes, no Production decision changes, no LINE, no BUY.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research_value_candidate_shadow import Row
from research_value_market_residual import ALPHAS, TICKETS, residual_gate

JST = timezone(timedelta(hours=9))
START_DATE = date.fromisoformat(os.getenv("VALUE_RESIDUAL_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_RESIDUAL_END", "2026-09-12"))
COURSE_COEF = 0.50
OPP_COEF = 1.0
SOURCE_CUTOFF = time(8, 15)
EPS = 1e-15
MAX_LABEL_SPREAD_SECONDS = float(os.getenv("VALUE_RESIDUAL_MAX_LABEL_SPREAD_SECONDS", "60"))
OUTPUT = Path(os.getenv("VALUE_RESIDUAL_OUTPUT", "value-course-opponent-market-residual.json"))
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}
HEAD_INDEX = [int(t[0]) - 1 for t in TICKETS]

# Expanding-train, non-overlapping future tests. These dates are fixed in code and
# are not selected from ROI or metric outcomes.
FOLDS = (
    ("F1", date(2026, 8, 28), date(2026, 9, 1), date(2026, 9, 3)),
    ("F2", date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 6)),
    ("F3", date(2026, 9, 6), date(2026, 9, 7), date(2026, 9, 9)),
    ("F4", date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 12)),
)


def aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def valid_probs(xs: Any, n: int) -> bool:
    if not isinstance(xs, list) or len(xs) != n:
        return False
    try:
        vals = [float(x) for x in xs]
    except Exception:
        return False
    return all(math.isfinite(x) and x >= 0.0 for x in vals) and abs(sum(vals) - 1.0) <= 5e-5


def normalize(xs: list[float]) -> list[float]:
    vals = [max(EPS, float(x)) for x in xs]
    total = sum(vals)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("invalid normalization total")
    return [x / total for x in vals]


def first_marginal(ticket_probs: list[float]) -> list[float]:
    out = [0.0] * 6
    for i, p in enumerate(ticket_probs):
        out[HEAD_INDEX[i]] += float(p)
    return out


def apply_first_place_delta(ticket_probs: list[float], pressure_delta: list[float]) -> list[float]:
    if len(ticket_probs) != 120 or len(pressure_delta) != 6:
        raise ValueError("bad probability dimensions")
    base_first = first_marginal(ticket_probs)
    if any(x <= 0.0 or not math.isfinite(x) for x in base_first):
        raise ValueError("invalid first-place marginal")
    target_first = normalize([
        max(EPS, min(0.999, base_first[i] + OPP_COEF * float(pressure_delta[i])))
        for i in range(6)
    ])
    factors = [target_first[i] / base_first[i] for i in range(6)]
    return normalize([float(p) * factors[HEAD_INDEX[i]] for i, p in enumerate(ticket_probs)])


def course_integrity(row: dict[str, Any]) -> bool:
    race_date = row.get("race_date")
    deadline = aware_jst(row.get("deadline_at"))
    snapshot = aware_jst(row.get("course_snapshot_at"))
    source_times = row.get("course_snapshot_ats")
    rates = row.get("course_top3_rates")
    return bool(
        int(row.get("course_model_version") or 0) == 1
        and abs(float(row.get("course_coef") or 0.0) - COURSE_COEF) < 1e-9
        and str(row.get("source_cutoff_jst") or "") == "08:15"
        and str(row.get("ticket_order_version") or "") == "lexicographic_lane_loop_120_fixed_v1"
        and isinstance(rates, list) and len(rates) == 6
        and all(math.isfinite(float(x)) and 0.0 <= float(x) <= 100.0 for x in rates)
        and valid_probs(row.get("base_probs"), 120)
        and valid_probs(row.get("course_probs"), 120)
        and isinstance(source_times, list) and len(source_times) == 6
        and race_date is not None and deadline is not None and snapshot is not None
        and snapshot < deadline and float(row.get("minutes_before") or 0.0) >= 3.0
        and all(
            (dt := aware_jst(raw)) is not None
            and dt.date() == race_date
            and dt.time().replace(tzinfo=None) <= SOURCE_CUTOFF
            and dt < deadline
            for raw in source_times
        )
    )


def opponent_integrity(row: dict[str, Any]) -> bool:
    race_date = row.get("race_date")
    deadline = aware_jst(row.get("deadline_at"))
    created = aware_jst(row.get("opp_created_at"))
    matched = row.get("matched_opponents")
    base_win = row.get("base_win")
    adj_win = row.get("adj_win")
    try:
        arrays_ok = (
            isinstance(matched, list) and len(matched) == 6 and all(int(x) >= 4 for x in matched)
            and isinstance(base_win, list) and len(base_win) == 6
            and isinstance(adj_win, list) and len(adj_win) == 6
            and all(math.isfinite(float(x)) and 0.0 < float(x) < 1.0 for x in base_win + adj_win)
        )
    except Exception:
        arrays_ok = False
    return bool(
        int(row.get("opp_model_version") or 0) == 2
        and race_date is not None and row.get("train_end") is not None and row.get("train_end") < race_date
        and deadline is not None and created is not None and created.date() == race_date and created < deadline
        and arrays_ok
    )


def market_integrity(row: dict[str, Any]) -> bool:
    deadline = aware_jst(row.get("deadline_at"))
    first_at = aware_jst(row.get("market_first_snapshot_at"))
    last_at = aware_jst(row.get("market_last_snapshot_at"))
    odds = row.get("odds_map")
    if deadline is None or first_at is None or last_at is None or last_at > deadline:
        return False
    if (last_at - first_at).total_seconds() > MAX_LABEL_SPREAD_SECONDS:
        return False
    if not isinstance(odds, dict) or set(str(k) for k in odds) != set(TICKETS):
        return False
    try:
        vals = [float(odds[t]) for t in TICKETS]
    except Exception:
        return False
    return all(math.isfinite(x) and x > 1.0 for x in vals)


def load_rows(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("set local statement_timeout='120s'")
        cur.execute("set local lock_timeout='5s'")
        cur.execute("set local idle_in_transaction_session_timeout='30s'")
        cur.execute("set local max_parallel_workers_per_gather=0")
        cur.execute("set local work_mem='8MB'")
        cur.execute(
            """
            with course as (
              select distinct on (race_id)
                     race_id,race_date,venue_id,race_no,
                     model_version as course_model_version,formula_version,
                     ticket_order_version,course_coef,source_cutoff_jst,
                     deadline_at,snapshot_at as course_snapshot_at,minutes_before,
                     course_top3_rates,course_snapshot_ats,base_probs,course_probs
                from v2_racer_course_top3_forward_shadow
               where race_date between %s and %s
               order by race_id,snapshot_at desc
            ), odds_group as (
              select c.race_id,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from course c
                join v2_realtime_odds_snapshots o on o.race_id=c.race_id
               where o.snapshot_label is not null
               group by c.race_id,o.snapshot_label,c.deadline_at
              having count(*)=120
                 and count(distinct o.ticket)=120
                 and count(*) filter (where o.odds is not null and o.odds > 1.0)=120
                 and max(o.snapshot_at) <= c.deadline_at
                 and extract(epoch from (max(o.snapshot_at)-min(o.snapshot_at))) <= %s
            ), chosen as (
              select distinct on (race_id)
                     race_id,snapshot_label,first_snapshot_at,last_snapshot_at
                from odds_group
               order by race_id,last_snapshot_at desc,snapshot_label
            ), market as (
              select ch.race_id,ch.snapshot_label,
                     ch.first_snapshot_at as market_first_snapshot_at,
                     ch.last_snapshot_at as market_last_snapshot_at,
                     jsonb_object_agg(o.ticket,o.odds) as odds_map
                from chosen ch
                join v2_realtime_odds_snapshots o
                  on o.race_id=ch.race_id and o.snapshot_label=ch.snapshot_label
               group by ch.race_id,ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at
            )
            select c.*,
                   p.model_version as opp_model_version,p.train_end,p.matched_opponents,
                   p.base_win,p.adj_win,p.created_at as opp_created_at,
                   m.snapshot_label as market_snapshot_label,m.market_first_snapshot_at,
                   m.market_last_snapshot_at,m.odds_map,
                   r.result_status,r.race_status,r.trifecta_ticket
              from course c
              join v2_opponent_pressure_shadow_v2 p on p.race_id=c.race_id
              join market m on m.race_id=c.race_id
              left join v2_results r on r.race_id=c.race_id
             order by c.race_date,c.venue_id,c.race_no,c.race_id
            """,
            (START_DATE, END_DATE, MAX_LABEL_SPREAD_SECONDS),
        )
        return [dict(x) for x in cur.fetchall()]


def weighted_metric(folds: list[dict[str, Any]], section: str, metric: str) -> float | None:
    total_n = sum(int(f[section]["n"] or 0) for f in folds)
    if not total_n:
        return None
    return sum(float(f[section][metric]) * int(f[section]["n"]) for f in folds) / total_n


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if END_DATE < START_DATE:
        raise RuntimeError("end before start")

    print("VALUE_COURSE_OPP_MARKET_MODE=read_only_timing_safe_walk_forward", flush=True)
    print(f"VALUE_COURSE_OPP_MARKET_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_COURSE_OPP_MARKET_FIXED=course:0.50 opponent:1.0", flush=True)
    print(f"VALUE_COURSE_OPP_MARKET_MAX_LABEL_SPREAD_SECONDS={MAX_LABEL_SPREAD_SECONDS:g}", flush=True)
    print("VALUE_COURSE_OPP_MARKET_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        joined = load_rows(conn)
        conn.rollback()

    research_rows: list[Row] = []
    coverage = {
        "joined_market_course_opponent": len(joined),
        "evaluated_races": 0,
        "invalid_course": 0,
        "invalid_opponent": 0,
        "invalid_market": 0,
        "pending_result": 0,
        "invalid_result": 0,
    }
    market_labels: dict[str, int] = {}

    for row in joined:
        if not course_integrity(row):
            coverage["invalid_course"] += 1
            continue
        if not opponent_integrity(row):
            coverage["invalid_opponent"] += 1
            continue
        if not market_integrity(row):
            coverage["invalid_market"] += 1
            continue
        if str(row.get("result_status") or "").lower() != "official" or str(row.get("race_status") or "").lower() != "official":
            coverage["pending_result"] += 1
            continue
        actual = str(row.get("trifecta_ticket") or "").strip()
        if actual not in TICKET_INDEX:
            coverage["invalid_result"] += 1
            continue

        course = [float(x) for x in row["course_probs"]]
        pressure_delta = [float(row["adj_win"][i]) - float(row["base_win"][i]) for i in range(6)]
        combined = apply_first_place_delta(course, pressure_delta)
        odds_map = row["odds_map"]
        race_date_s = str(row["race_date"])
        race_id = str(row["race_id"])
        venue_id = str(row.get("venue_id") or "").zfill(2)
        race_no = int(row.get("race_no") or 0)
        for i, ticket in enumerate(TICKETS):
            research_rows.append(
                Row(
                    race_date=race_date_s,
                    race_id=race_id,
                    venue_id=venue_id,
                    race_no=race_no,
                    ticket=ticket,
                    odds=float(odds_map[ticket]),
                    prob=float(combined[i]),
                    hit=int(ticket == actual),
                )
            )
        coverage["evaluated_races"] += 1
        label = str(row.get("market_snapshot_label") or "<none>")
        market_labels[label] = market_labels.get(label, 0) + 1

    fold_results: list[dict[str, Any]] = []
    for name, train_end, test_start, test_end in FOLDS:
        out = residual_gate(research_rows, train_end, test_start, test_end, ALPHAS)
        fold = {
            "name": name,
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(),
            **out,
        }
        fold_results.append(fold)
        delta = out.get("selected_minus_market") or {}
        print(
            f"VALUE_COURSE_OPP_MARKET_FOLD={name} train:{out['period']['train_races']} test:{out['period']['test_races']} "
            f"alpha:{out['selected_alpha']} status:{out['status']} "
            f"dll:{delta.get('logloss')} dbrier:{delta.get('brier')} drank:{delta.get('mean_rank')}",
            flush=True,
        )

    aggregate: dict[str, Any] = {"test_races": sum(int(f["market"]["n"] or 0) for f in fold_results)}
    for section in ("market", "selected", "model"):
        aggregate[section] = {
            "logloss": weighted_metric(fold_results, section, "logloss"),
            "brier": weighted_metric(fold_results, section, "brier"),
            "mean_rank": weighted_metric(fold_results, section, "mean_rank"),
        }
    aggregate["selected_minus_market"] = {
        key: (aggregate["selected"][key] - aggregate["market"][key])
        for key in ("logloss", "brier", "mean_rank")
        if aggregate["selected"][key] is not None and aggregate["market"][key] is not None
    }
    aggregate["model_minus_market"] = {
        key: (aggregate["model"][key] - aggregate["market"][key])
        for key in ("logloss", "brier", "mean_rank")
        if aggregate["model"][key] is not None and aggregate["market"][key] is not None
    }
    positive_alpha_folds = sum(1 for f in fold_results if isinstance(f.get("selected_alpha"), (int, float)) and float(f["selected_alpha"]) > 0.0)
    improving_ll_folds = sum(
        1 for f in fold_results
        if isinstance(f.get("selected_minus_market"), dict) and float(f["selected_minus_market"]["logloss"]) < 0.0
    )
    improving_brier_folds = sum(
        1 for f in fold_results
        if isinstance(f.get("selected_minus_market"), dict) and float(f["selected_minus_market"]["brier"]) < 0.0
    )
    aggregate["positive_alpha_folds"] = positive_alpha_folds
    aggregate["improving_logloss_folds"] = improving_ll_folds
    aggregate["improving_brier_folds"] = improving_brier_folds

    residual_support = bool(
        aggregate["test_races"] > 0
        and aggregate["selected_minus_market"].get("logloss", 0.0) < 0.0
        and aggregate["selected_minus_market"].get("brier", 0.0) <= 0.0
        and positive_alpha_folds >= 3
        and improving_ll_folds >= 3
    )
    status = "SUPPORTS_MARKET_RESIDUAL_RESEARCH" if residual_support else "MARKET_RESIDUAL_NOT_ESTABLISHED"

    summary = {
        "contract": "value_course_opponent_market_residual_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "fixed_coefficients": {"course": COURSE_COEF, "opponent": OPP_COEF},
        "market_contract": {
            "complete_tickets": 120,
            "all_rows_predeadline": True,
            "max_label_spread_seconds": MAX_LABEL_SPREAD_SECONDS,
            "market_probability": "devig_inverse_odds",
        },
        "coverage": coverage,
        "market_labels": dict(sorted(market_labels.items())),
        "folds": fold_results,
        "aggregate_future_tests": aggregate,
        "status": status,
        "oos_residual_support": residual_support,
        "formal_profitability_established": False,
        "promotion_allowed": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"VALUE_COURSE_OPP_MARKET_COVERAGE={json.dumps(coverage, sort_keys=True)}", flush=True)
    print(f"VALUE_COURSE_OPP_MARKET_LABELS={json.dumps(dict(sorted(market_labels.items())), sort_keys=True)}", flush=True)
    print(f"VALUE_COURSE_OPP_MARKET_AGGREGATE={json.dumps(aggregate, sort_keys=True)}", flush=True)
    print(f"VALUE_COURSE_OPP_MARKET_STATUS={status}", flush=True)
    print("VALUE_COURSE_OPP_MARKET_PROFITABILITY=NOT_ESTABLISHED_BY_THIS_AUDIT", flush=True)
    print("VALUE_COURSE_OPP_MARKET_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"VALUE_COURSE_OPP_MARKET_ERROR={type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:700]}",
            flush=True,
        )
        raise
