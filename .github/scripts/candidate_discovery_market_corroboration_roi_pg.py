# -*- coding: utf-8 -*-
"""Read-only timing-safe market corroboration ROI proxy audit.

This tests a simple independent signal without outcome-driven thresholds:
structural TOP1 vs the de-vigged market TOP1/TOP2 from the latest coherent,
complete 120-ticket snapshot before deadline.

Frozen contract:
- structural proxy: Candidate Discovery V2 MOTOR2_FACTOR, top 6 races/day;
- odds snapshot: exactly 120 rows/tickets, all odds >1, one snapshot label,
  within-label spread <=60 seconds, latest complete label before deadline;
- bet types: trifecta / exacta / trio;
- structural TOP1 only;
- views: baseline market-ready / market TOP2 support / market TOP1 agree;
- stake: 100 JPY per selected ticket;
- no EV or absolute-odds eligibility threshold.

All selections and market agreement flags are frozen before official K payouts are
retrieved. No result table is queried. No DB writes, LINE, BUY, schema or
Production behavior changes.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


v2 = load_module("candidate_discovery_v2_formation_pg", HERE / "candidate_discovery_v2_formation_pg.py")
bet = load_module("candidate_discovery_bettype_contract", REPO_ROOT / "research" / "candidate_discovery_bettype_contract.py")
kmod = load_module("candidate_discovery_k_multibet_probe", HERE / "candidate_discovery_k_multibet_probe.py")

START_DATE = os.getenv("CANDIDATE_MARKET_START", "2026-08-14").strip()
END_DATE = os.getenv("CANDIDATE_MARKET_END", "2026-09-12").strip()
OUTPUT = Path(os.getenv("CANDIDATE_MARKET_OUTPUT", "candidate-discovery-market-corroboration-roi.json"))
MAX_LABEL_SPREAD_SECONDS = 60.0
UNIT_YEN = 100
RACE_CAP = 6
FETCH_WORKERS = max(1, min(4, int(os.getenv("CANDIDATE_MARKET_K_FETCH_WORKERS", "4"))))
ALL_LANES = {1, 2, 3, 4, 5, 6}
BET_TYPES = ("trifecta", "exacta", "trio")
VIEWS = ("baseline_market_ready", "market_top2_support", "market_top1_agree")


def latest_complete_labels(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
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
            )
            select distinct on (race_id)
                   race_id,race_date,venue_id,venue_code,race_no,deadline_at,snapshot_label,
                   first_snapshot_at,last_snapshot_at,spread_seconds,lead_minutes
              from valid
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (START_DATE, END_DATE, MAX_LABEL_SPREAD_SECONDS),
        )
        return [dict(row) for row in cur.fetchall()]


def load_cards_and_odds(conn: psycopg.Connection[Any], labels: list[dict[str, Any]]):
    with conn.cursor() as cur:
        cur.execute(
            """select race_id,race_date,venue_id,venue_code,race_no
                 from v2_races
                where race_date between %s and %s
                order by race_date,venue_id,race_no,race_id""",
            (START_DATE, END_DATE),
        )
        races = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """select e.race_id,e.lane,e.racer_class,e.national_win_rate,
                      e.national_place2_rate,e.local_place2_rate,e.avg_st,e.motor_place2_rate
                 from v2_race_entries e
                 join v2_races r on r.race_id=e.race_id
                where r.race_date between %s and %s
                order by e.race_id,e.lane""",
            (START_DATE, END_DATE),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))

        label_by = {str(row["race_id"]): str(row["snapshot_label"]) for row in labels}
        race_ids = list(label_by)
        odds_by: dict[str, dict[str, float]] = defaultdict(dict)
        if race_ids:
            cur.execute(
                """select race_id,ticket,odds,snapshot_label
                     from v2_realtime_odds_snapshots
                    where race_id=any(%s) and odds is not null and odds>1.0
                    order by race_id,snapshot_label,ticket""",
                (race_ids,),
            )
            for row in cur.fetchall():
                rid = str(row["race_id"])
                if str(row.get("snapshot_label") or "") != label_by.get(rid):
                    continue
                ticket = v2.v1.norm_ticket(row.get("ticket"))
                if ticket:
                    odds_by[rid][ticket] = float(row["odds"])
    return races, entries_by, dict(odds_by)


def structural_top6(races: list[dict[str, Any]], entries_by: dict[str, list[dict[str, Any]]]):
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    probs_by: dict[str, dict[str, float]] = {}
    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v2.v1.si(x.get("lane"), 0) for x in entries} != ALL_LANES:
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base = v2.v1.ticket_probabilities(entries, venue, 0.0)
        probs = v2.motor_adjust(base, entries)
        probs_by[rid] = probs
        ds = str(race.get("race_date") or "")[:10]
        by_day[ds].append(v2.probability_metrics(race, probs, "MOTOR2_FACTOR"))
    selected = {}
    for ds, rows in sorted(by_day.items()):
        for row in v2.rank_day(rows)[:RACE_CAP]:
            selected[str(row["race_id"])] = row
    return selected, probs_by


def market_distribution(odds: dict[str, float]) -> dict[str, float] | None:
    if len(odds) != 120:
        return None
    inv = {}
    for ticket, odd in odds.items():
        if not math.isfinite(odd) or odd <= 1.0:
            return None
        inv[ticket] = 1.0 / odd
    total = sum(inv.values())
    if total <= 0:
        return None
    return {ticket: value / total for ticket, value in inv.items()}


def freeze_rows(labels, selected, structural_probs, odds_by):
    frozen = []
    label_by = {str(row["race_id"]): row for row in labels}
    for rid, row in selected.items():
        label = label_by.get(rid)
        market_tri = market_distribution(odds_by.get(rid, {}))
        if label is None or market_tri is None or rid not in structural_probs:
            continue
        for bet_type in BET_TYPES:
            sdist = bet.distribution_for_bet_type(structural_probs[rid], bet_type)
            mdist = bet.distribution_for_bet_type(market_tri, bet_type)
            stop1 = bet.select_fixed(sdist, 1)[0]
            mtop2 = bet.select_fixed(mdist, 2)
            frozen.append({
                "race_id": rid,
                "race_date": str(label["race_date"])[:10],
                "venue_id": str(label.get("venue_id") or label.get("venue_code") or row.get("venue_id") or "").zfill(2),
                "race_no": int(label.get("race_no") or row.get("race_no") or 0),
                "daily_race_rank": int(row["daily_race_rank"]),
                "bet_type": bet_type,
                "structural_top1": stop1,
                "market_top1": mtop2[0],
                "market_top2": tuple(mtop2),
                "market_top1_agree": stop1 == mtop2[0],
                "market_top2_support": stop1 in set(mtop2),
                "snapshot_label": str(label["snapshot_label"]),
                "last_snapshot_at": str(label["last_snapshot_at"]),
                "lead_minutes": float(label["lead_minutes"]),
                "spread_seconds": float(label["spread_seconds"]),
            })
    return frozen


def fetch_k_day(ds: str):
    try:
        parsed = kmod.parse_multibet_payouts(kmod.get_k_text(ds))
        return ds, parsed["by_key"], None
    except Exception as exc:
        return ds, None, f"{type(exc).__name__}:{str(exc)[:200]}"


def fetch_payouts(days: list[str]):
    by_day = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for ds, mapping, err in pool.map(fetch_k_day, days):
            if err:
                errors[ds] = err
            else:
                by_day[ds] = mapping
    return by_day, errors


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda x: (x["race_date"], x["venue_id"], x["race_no"]))
    n = len(ordered)
    hits = inv = ret = 0
    losing = max_losing = 0
    running = peak = max_dd = 0
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hit_returns = []
    for row in ordered:
        inv += UNIT_YEN
        value = int(row["return_yen"])
        ret += value
        if row["hit"]:
            hits += 1
            losing = 0
            hit_returns.append(value)
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        running += value - UNIT_YEN
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)
        by_day[row["race_date"]].append(row)
    positive_days = sum(
        1 for xs in by_day.values()
        if sum(int(x["return_yen"]) for x in xs) > UNIT_YEN * len(xs)
    )
    max_hit = max(hit_returns) if hit_returns else 0
    return {
        "evaluated_races": n,
        "hits": hits,
        "race_hit_rate_pct": round(hits / n * 100.0, 3) if n else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 3) if inv else None,
        "max_losing_race_streak": max_losing,
        "max_drawdown_yen": max_dd,
        "positive_days": positive_days,
        "evaluated_days": len(by_day),
        "positive_day_rate_pct": round(positive_days / len(by_day) * 100.0, 3) if by_day else None,
        "max_single_hit_return_yen": max_hit,
        "max_single_hit_share_of_returns_pct": round(max_hit / ret * 100.0, 3) if ret else None,
    }


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "p50": None, "max": None}
    xs = sorted(values)
    return {"min": round(xs[0], 3), "p50": round(float(median(xs)), 3), "max": round(xs[-1], 3)}


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("CANDIDATE_MARKET_ROI_MODE=read_only_timing_safe_market_corroboration", flush=True)
    print(f"CANDIDATE_MARKET_ROI_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CANDIDATE_MARKET_ROI_PROXY=V2_MOTOR2_FACTOR_TOP6_NOT_V4_PRODUCTION_BACKTEST", flush=True)
    print("CANDIDATE_MARKET_ROI_SNAPSHOT=120_tickets_positive_spread_le60_latest_predeadline", flush=True)
    print("CANDIDATE_MARKET_ROI_VIEWS=baseline_market_ready,market_top2_support,market_top1_agree", flush=True)
    print("CANDIDATE_MARKET_ROI_EV_FILTER=0 ODDS_ELIGIBILITY_FILTER=0 UNIT_YEN=100", flush=True)
    print("CANDIDATE_MARKET_ROI_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        labels = latest_complete_labels(conn)
        races, entries_by, odds_by = load_cards_and_odds(conn, labels)
        conn.rollback()

    selected, structural_probs = structural_top6(races, entries_by)
    frozen = freeze_rows(labels, selected, structural_probs, odds_by)
    unique_races = {row["race_id"] for row in frozen}
    days = sorted({row["race_date"] for row in frozen})
    leads = [row["lead_minutes"] for row in frozen if row["bet_type"] == "trifecta"]
    spreads = [row["spread_seconds"] for row in frozen if row["bet_type"] == "trifecta"]
    coverage = {
        "complete_timing_safe_market_races": len(labels),
        "structural_top6_market_overlap_races": len(unique_races),
        "frozen_bet_rows": len(frozen),
        "frozen_days": len(days),
        "lead_minutes": quantiles(leads),
        "spread_seconds": quantiles(spreads),
    }
    print("CANDIDATE_MARKET_ROI_COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)

    payouts, k_errors = fetch_payouts(days)
    print("CANDIDATE_MARKET_ROI_K_ERRORS=" + json.dumps(k_errors, ensure_ascii=False, sort_keys=True), flush=True)

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
        f"{bt}|{view}": aggregate(buckets.get((bt, view), []))
        for bt in BET_TYPES for view in VIEWS
    }
    out = {
        "contract": "candidate_discovery_market_corroboration_roi_proxy_v1",
        "period": {"start": START_DATE, "end": END_DATE},
        "proxy_only": True,
        "proxy_model": "V2_MOTOR2_FACTOR_TOP6",
        "snapshot_contract": "120 positive tickets, one label, spread<=60s, latest complete predeadline",
        "unit_yen": UNIT_YEN,
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
        print(f"CANDIDATE_MARKET_ROI={key} " + json.dumps(reports[key], sort_keys=True), flush=True)
    print(f"CANDIDATE_MARKET_ROI_MISSING_PAYOUT_ROWS={missing}", flush=True)
    print("CANDIDATE_MARKET_ROI_PROMOTION=BLOCK_PROXY_ONLY", flush=True)
    print("CANDIDATE_MARKET_ROI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
