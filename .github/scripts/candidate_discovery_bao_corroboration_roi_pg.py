# -*- coding: utf-8 -*-
"""Read-only ROI proxy audit for structural tickets corroborated by late Bao.

Purpose
-------
Test whether an independent timing-safe late Bao signal improves the economics of
an already-frozen broad structural prediction feed. This is a research proxy,
not a V4 Production backtest and not a purchase rule.

Frozen before outcome evaluation:
- structural proxy: Candidate Discovery V2 MOTOR2_FACTOR, top 6 races/day;
- bet types: trifecta / exacta / trio;
- structural ticket: TOP1 only;
- Bao views: BASELINE_BAO_READY, BAO_TOP2_SUPPORT, BAO_TOP1_AGREE;
- late Bao: complete 120-ticket late market snapshot after dedicated exhibition
  snapshot and before race deadline, with frozen Motor2/exhibition betas 0.06;
- flat stake: 100 JPY per selected ticket;
- no EV or absolute-odds eligibility gate.

Selections/signals are frozen in memory before official K payout archives are
read. No result table is queried. No DB writes, LINE, BUY, schema or Production
behavior changes.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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
bao = load_module("candidate_discovery_late_bao_contract", REPO_ROOT / "research" / "candidate_discovery_late_bao_contract.py")
kmod = load_module("candidate_discovery_k_multibet_probe", HERE / "candidate_discovery_k_multibet_probe.py")

OUTPUT = Path(os.getenv("CANDIDATE_BAO_CORROBORATION_OUTPUT", "candidate-discovery-bao-corroboration-roi.json"))
UNIT_YEN = 100
RACE_CAP = 6
FETCH_WORKERS = max(1, min(4, int(os.getenv("CANDIDATE_BAO_K_FETCH_WORKERS", "4"))))
ALL_LANES = {1, 2, 3, 4, 5, 6}
BET_TYPES = ("trifecta", "exacta", "trio")
VIEWS = ("baseline_bao_ready", "bao_top2_support", "bao_top1_agree")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _late_odds_mapping(values: Any) -> dict[str, float] | None:
    if values is None:
        return None
    xs = list(values)
    if len(xs) != 120:
        return None
    out: dict[str, float] = {}
    for ticket, value in zip(bao.TICKETS, xs):
        v = _safe_float(value)
        if v is None or v <= 1.0:
            return None
        out[ticket] = v
    return out


def load_bao_rows(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with late as (
                select distinct on (race_id)
                       race_id,race_date,venue_id,race_no,captured_at,minutes_before,odds
                  from v2_bao_market_shadow_snapshots
                 where phase='late'
                 order by race_id,captured_at desc
            )
            select l.race_id,l.race_date,l.venue_id,l.race_no,
                   l.captured_at as late_at,l.minutes_before as late_mb,l.odds as late_odds,
                   x.captured_at as exhibition_at,x.minutes_before as exhibition_mb,
                   x.exhibition_time_ranks,
                   r.deadline_at
              from late l
              join v2_bao_exhibition_shadow_snapshots x on x.race_id=l.race_id
              join v2_races r on r.race_id=l.race_id
             order by l.race_date,l.venue_id,l.race_no,l.race_id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def timing_safe(row: dict[str, Any]) -> bool:
    ex_at = row.get("exhibition_at")
    late_at = row.get("late_at")
    deadline = row.get("deadline_at")
    return bool(ex_at and late_at and deadline and ex_at < late_at < deadline)


def load_race_cards(conn: psycopg.Connection[Any], start_date: str, end_date: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (start_date, end_date),
        )
        races = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select e.race_id,e.lane,e.racer_class,e.national_win_rate,
                   e.national_place2_rate,e.local_place2_rate,e.avg_st,e.motor_place2_rate
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date between %s and %s
             order by e.race_id,e.lane
            """,
            (start_date, end_date),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))
    return races, entries_by


def rank_structural_days(races: list[dict[str, Any]], entries_by: dict[str, list[dict[str, Any]]]):
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    probs_by_race: dict[str, dict[str, float]] = {}
    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v2.v1.si(x.get("lane"), 0) for x in entries} != ALL_LANES:
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base_probs = v2.v1.ticket_probabilities(entries, venue, 0.0)
        m2_probs = v2.motor_adjust(base_probs, entries)
        probs_by_race[rid] = m2_probs
        ds = str(race.get("race_date") or "")[:10]
        by_day[ds].append(v2.probability_metrics(race, m2_probs, "MOTOR2_FACTOR"))
    top6: dict[str, dict[str, Any]] = {}
    for ds, rows in sorted(by_day.items()):
        for row in v2.rank_day(rows)[:RACE_CAP]:
            top6[str(row["race_id"])] = row
    return top6, probs_by_race


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float] | None:
    by = {v2.v1.si(row.get("lane"), 0): row for row in entries}
    if set(by) != ALL_LANES:
        return None
    out: dict[int, float] = {}
    for lane in range(1, 7):
        value = v2.v1.valid_motor2(by[lane].get("motor_place2_rate"))
        if value is None:
            return None
        out[lane] = float(value)
    return out


def exhibition_rank_map(values: Any) -> dict[int, int] | None:
    if values is None:
        return None
    xs = [int(x) for x in list(values)]
    if len(xs) != 6 or set(xs) != ALL_LANES:
        return None
    return {lane: xs[lane - 1] for lane in range(1, 7)}


def freeze_signal_rows(
    bao_rows: list[dict[str, Any]],
    top6: dict[str, dict[str, Any]],
    probs_by_race: dict[str, dict[str, float]],
    entries_by: dict[str, list[dict[str, Any]]],
):
    frozen: list[dict[str, Any]] = []
    timing_valid = complete_valid = top6_valid = 0
    for row in bao_rows:
        if not timing_safe(row):
            continue
        timing_valid += 1
        rid = str(row["race_id"])
        odds = _late_odds_mapping(row.get("late_odds"))
        motors = motor_map(entries_by.get(rid, []))
        exr = exhibition_rank_map(row.get("exhibition_time_ranks"))
        if odds is None or motors is None or exr is None:
            continue
        try:
            bao_tri = bao.bao_distribution(odds=odds, motor_place2=motors, exhibition_time_rank=exr)
        except Exception:
            continue
        complete_valid += 1
        if rid not in top6 or rid not in probs_by_race:
            continue
        top6_valid += 1
        structural_tri = probs_by_race[rid]
        for bet_type in BET_TYPES:
            sdist = bet.distribution_for_bet_type(structural_tri, bet_type)
            bdist = bet.distribution_for_bet_type(bao_tri, bet_type)
            s_top1 = bet.select_fixed(sdist, 1)[0]
            b_top2 = bet.select_fixed(bdist, 2)
            b_top1 = b_top2[0]
            frozen.append({
                "race_id": rid,
                "race_date": str(row["race_date"])[:10],
                "venue_id": str(row.get("venue_id") or top6[rid].get("venue_id") or "").zfill(2),
                "race_no": int(row.get("race_no") or top6[rid].get("race_no") or 0),
                "daily_race_rank": int(top6[rid]["daily_race_rank"]),
                "bet_type": bet_type,
                "structural_top1": s_top1,
                "bao_top1": b_top1,
                "bao_top2": tuple(b_top2),
                "bao_top1_agree": s_top1 == b_top1,
                "bao_top2_support": s_top1 in set(b_top2),
                "late_at": str(row.get("late_at")),
                "exhibition_at": str(row.get("exhibition_at")),
            })
    coverage = {
        "bao_rows": len(bao_rows),
        "timing_safe_rows": timing_valid,
        "complete_bao_rows": complete_valid,
        "top6_bao_races": top6_valid,
        "frozen_bet_rows": len(frozen),
    }
    return frozen, coverage


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
    hits = 0
    inv = ret = 0
    losing = max_losing = 0
    running = peak = max_dd = 0
    hit_returns: list[int] = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
    positive_days = 0
    for xs in by_day.values():
        day_ret = sum(int(x["return_yen"]) for x in xs)
        if day_ret - UNIT_YEN * len(xs) > 0:
            positive_days += 1
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


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("CANDIDATE_BAO_ROI_MODE=read_only_structural_proxy_corroboration", flush=True)
    print("CANDIDATE_BAO_ROI_PROXY=V2_MOTOR2_FACTOR_TOP6_NOT_V4_PRODUCTION_BACKTEST", flush=True)
    print("CANDIDATE_BAO_ROI_VIEWS=baseline_bao_ready,bao_top2_support,bao_top1_agree", flush=True)
    print("CANDIDATE_BAO_ROI_BET_TYPES=trifecta,exacta,trio TOP1_ONLY=1 UNIT_YEN=100", flush=True)
    print("CANDIDATE_BAO_ROI_EV_FILTER=0 ODDS_ELIGIBILITY_FILTER=0", flush=True)
    print("CANDIDATE_BAO_ROI_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        bao_rows = load_bao_rows(conn)
        if not bao_rows:
            raise RuntimeError("no late Bao/exhibition pairs found")
        dates = [str(row["race_date"])[:10] for row in bao_rows]
        start_date, end_date = min(dates), max(dates)
        races, entries_by = load_race_cards(conn, start_date, end_date)
        conn.rollback()

    top6, probs_by_race = rank_structural_days(races, entries_by)
    frozen, coverage = freeze_signal_rows(bao_rows, top6, probs_by_race, entries_by)
    days = sorted({row["race_date"] for row in frozen})
    print(f"CANDIDATE_BAO_ROI_PERIOD={start_date}..{end_date}", flush=True)
    print("CANDIDATE_BAO_ROI_COVERAGE=" + json.dumps(coverage, sort_keys=True), flush=True)
    print(f"CANDIDATE_BAO_ROI_FROZEN_DAYS={len(days)}", flush=True)

    payouts, k_errors = fetch_payouts(days)
    print("CANDIDATE_BAO_ROI_K_ERRORS=" + json.dumps(k_errors, ensure_ascii=False, sort_keys=True), flush=True)

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    missing = 0
    for row in frozen:
        official = payouts.get(row["race_date"], {}).get((row["venue_id"], row["race_no"], row["bet_type"]))
        if official is None:
            missing += 1
            continue
        hit = str(official["ticket"]) == row["structural_top1"]
        evaluated = dict(row)
        evaluated["hit"] = hit
        evaluated["return_yen"] = int(official["payout_yen"]) if hit else 0
        buckets[(row["bet_type"], "baseline_bao_ready")].append(evaluated)
        if row["bao_top2_support"]:
            buckets[(row["bet_type"], "bao_top2_support")].append(evaluated)
        if row["bao_top1_agree"]:
            buckets[(row["bet_type"], "bao_top1_agree")].append(evaluated)

    reports = {
        f"{bet_type}|{view}": aggregate(buckets.get((bet_type, view), []))
        for bet_type in BET_TYPES for view in VIEWS
    }
    out = {
        "contract": "candidate_discovery_bao_corroboration_roi_proxy_v1",
        "period": {"start": start_date, "end": end_date},
        "proxy_only": True,
        "proxy_model": "V2_MOTOR2_FACTOR_TOP6",
        "late_bao_timing": "dedicated_exhibition_at < late_market_at < deadline_at",
        "unit_yen": UNIT_YEN,
        "coverage": coverage,
        "frozen_days": days,
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
        print(f"CANDIDATE_BAO_ROI={key} " + json.dumps(reports[key], sort_keys=True), flush=True)
    print(f"CANDIDATE_BAO_ROI_MISSING_PAYOUT_ROWS={missing}", flush=True)
    print("CANDIDATE_BAO_ROI_PROMOTION=BLOCK_PROXY_ONLY", flush=True)
    print("CANDIDATE_BAO_ROI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
