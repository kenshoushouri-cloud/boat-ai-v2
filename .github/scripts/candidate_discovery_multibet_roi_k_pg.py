# -*- coding: utf-8 -*-
"""Read-only multi-bet ROI smoke audit using official K payouts.

This is a bounded parser/economics validation, not a promotion study.

Frozen before outcome evaluation:
- Candidate Discovery V2 structural race ranking, MOTOR2_FACTOR variant
- top 6 races/day; A=rank1-2, B=3-4, C=5-6
- trifecta / exacta / trio probabilities derived from the same 120-ticket model
- fixed TOP1/TOP2/TOP3/TOP5 and coverage 20/35/50 (max 12 tickets)
- 100 JPY per ticket

Race selection and ticket selection are completed before official K payout files
are downloaded. Payouts are then used only for realized evaluation.

No odds/EV eligibility, DB writes, LINE, BUY, schema changes, or Production logic
changes.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

V2_PATH = HERE / "candidate_discovery_v2_formation_pg.py"
spec_v2 = importlib.util.spec_from_file_location("candidate_discovery_v2_formation_pg", V2_PATH)
v2 = importlib.util.module_from_spec(spec_v2)
assert spec_v2 and spec_v2.loader
spec_v2.loader.exec_module(v2)

BET_PATH = REPO_ROOT / "research" / "candidate_discovery_bettype_contract.py"
spec_bet = importlib.util.spec_from_file_location("candidate_discovery_bettype_contract", BET_PATH)
bet = importlib.util.module_from_spec(spec_bet)
assert spec_bet and spec_bet.loader
spec_bet.loader.exec_module(bet)

K_PATH = HERE / "candidate_discovery_k_multibet_probe.py"
spec_k = importlib.util.spec_from_file_location("candidate_discovery_k_multibet_probe", K_PATH)
kmod = importlib.util.module_from_spec(spec_k)
assert spec_k and spec_k.loader
spec_k.loader.exec_module(kmod)

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_MULTIBET_ROI_START", "2026-08-14").strip()
END_DATE = os.getenv("CANDIDATE_MULTIBET_ROI_END", "2026-09-12").strip()
OUTPUT = Path(os.getenv("CANDIDATE_MULTIBET_ROI_OUTPUT", "candidate-discovery-multibet-roi-k.json"))
UNIT_YEN = 100
RACE_CAP = 6
ALL_LANES = {1, 2, 3, 4, 5, 6}


def tier_for_rank(rank: int) -> str:
    if 1 <= rank <= 2:
        return "A"
    if 3 <= rank <= 4:
        return "B"
    if 5 <= rank <= 6:
        return "C"
    return "OUT"


def date_range(start: str, end: str) -> list[str]:
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    if b < a:
        raise ValueError("end before start")
    out = []
    cur = a
    while cur <= b:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def load_races_entries(conn: psycopg.Connection[Any]):
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (START_DATE, END_DATE),
        )
        races = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            select e.race_id,e.lane,e.racer_class,e.national_win_rate,
                   e.national_place2_rate,e.local_place2_rate,e.avg_st,
                   e.motor_place2_rate
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date between %s and %s
             order by e.race_id,e.lane
            """,
            (START_DATE, END_DATE),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))
    return races, entries_by


def freeze_selections(races: list[dict[str, Any]], entries_by: dict[str, list[dict[str, Any]]]):
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = 0
    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v2.v1.si(x.get("lane"), 0) for x in entries} != ALL_LANES:
            skipped += 1
            continue
        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        base_probs = v2.v1.ticket_probabilities(entries, venue, 0.0)
        probs = v2.motor_adjust(base_probs, entries)
        ds = str(race.get("race_date") or "")[:10]
        by_day[ds].append(v2.probability_metrics(race, probs, "MOTOR2_FACTOR"))

    frozen = []
    for ds, rows in sorted(by_day.items()):
        for row in v2.rank_day(rows)[:RACE_CAP]:
            tri_probs = {
                ticket: float(prob)
                for ticket, prob in zip(row["ranked_tickets"], row["ranked_probs"])
            }
            frozen.append({
                "race_id": str(row["race_id"]),
                "race_date": ds,
                "venue_id": str(row["venue_id"]).zfill(2),
                "race_no": int(row["race_no"]),
                "daily_race_rank": int(row["daily_race_rank"]),
                "tier": tier_for_rank(int(row["daily_race_rank"])),
                "grid": bet.build_comparison_grid(tri_probs),
            })
    return frozen, skipped


def fetch_official_payouts(days: list[str]):
    by_day: dict[str, dict[tuple[str, int, str], dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    stats: dict[str, dict[str, int]] = {}
    for ds in days:
        try:
            parsed = kmod.parse_multibet_payouts(kmod.get_k_text(ds))
            by_day[ds] = parsed["by_key"]
            stats[ds] = {
                "markers": len(parsed["markers"]),
                "mapped": len(parsed["mapped"]),
                "trifecta": int(parsed["mapped_counts"].get("trifecta", 0)),
                "exacta": int(parsed["mapped_counts"].get("exacta", 0)),
                "trio": int(parsed["mapped_counts"].get("trio", 0)),
            }
        except Exception as exc:
            errors[ds] = f"{type(exc).__name__}:{str(exc)[:300]}"
    return by_day, errors, stats


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda x: (x["race_date"], x["venue_id"], x["race_no"]))
    n = len(ordered)
    hits = sum(1 for x in ordered if x["hit"])
    investment = sum(int(x["investment_yen"]) for x in ordered)
    returns = sum(int(x["return_yen"]) for x in ordered)
    losing = max_losing = 0
    running = peak = 0
    max_drawdown = 0
    hit_returns = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for x in ordered:
        if x["hit"]:
            losing = 0
            hit_returns.append(int(x["return_yen"]))
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        running += int(x["return_yen"]) - int(x["investment_yen"])
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)
        by_day[x["race_date"]].append(x)
        by_month[x["race_date"][:7]].append(x)

    positive_days = 0
    daily = {}
    for ds, xs in sorted(by_day.items()):
        inv = sum(int(x["investment_yen"]) for x in xs)
        ret = sum(int(x["return_yen"]) for x in xs)
        profit = ret - inv
        positive_days += 1 if profit > 0 else 0
        daily[ds] = {"races": len(xs), "investment_yen": inv, "return_yen": ret, "profit_yen": profit}

    monthly = {}
    for month, xs in sorted(by_month.items()):
        inv = sum(int(x["investment_yen"]) for x in xs)
        ret = sum(int(x["return_yen"]) for x in xs)
        monthly[month] = {
            "races": len(xs),
            "investment_yen": inv,
            "return_yen": ret,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 3) if inv else None,
        }

    max_hit = max(hit_returns) if hit_returns else 0
    return {
        "evaluated_races": n,
        "hits": hits,
        "race_hit_rate_pct": round(hits / n * 100.0, 3) if n else None,
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": round(returns / investment * 100.0, 3) if investment else None,
        "max_losing_race_streak": max_losing,
        "max_drawdown_yen": max_drawdown,
        "positive_days": positive_days,
        "evaluated_days": len(by_day),
        "positive_day_rate_pct": round(positive_days / len(by_day) * 100.0, 3) if by_day else None,
        "max_single_hit_return_yen": max_hit,
        "max_single_hit_share_of_returns_pct": round(max_hit / returns * 100.0, 3) if returns else None,
        "monthly": monthly,
        "daily": daily,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("CANDIDATE_MULTIBET_ROI_MODE=read_only_official_k_smoke", flush=True)
    print(f"CANDIDATE_MULTIBET_ROI_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CANDIDATE_MULTIBET_ROI_CONTRACT=top6_motor2_fixed_grid_100yen_per_ticket", flush=True)
    print("CANDIDATE_MULTIBET_ROI_ODDS_READ=0 EV_FILTER=0", flush=True)
    print("CANDIDATE_MULTIBET_ROI_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    # Phase 1: freeze all race and ticket selections using only pre-result features.
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='30s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")
        races, entries_by = load_races_entries(conn)
        conn.rollback()
    frozen, skipped = freeze_selections(races, entries_by)
    selected_days = sorted({x["race_date"] for x in frozen})
    print(f"CANDIDATE_MULTIBET_ROI_FROZEN=races:{len(frozen)} days:{len(selected_days)} skipped:{skipped}", flush=True)

    # Phase 2: only after freeze, obtain official realized payout files.
    payouts_by_day, k_errors, k_stats = fetch_official_payouts(selected_days)
    print(f"CANDIDATE_MULTIBET_ROI_K_ERRORS={json.dumps(k_errors, ensure_ascii=False, sort_keys=True)}", flush=True)

    overall: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    tiers: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    missing_payout_rows = 0
    evaluated_frozen_races = 0

    for race in frozen:
        day_map = payouts_by_day.get(race["race_date"])
        if day_map is None:
            continue
        race_has_any = False
        for view in race["grid"]:
            bet_type = str(view["bet_type"])
            strategy = str(view["strategy"])
            official = day_map.get((race["venue_id"], race["race_no"], bet_type))
            if official is None:
                missing_payout_rows += 1
                continue
            race_has_any = True
            selected = tuple(str(x) for x in view["tickets"])
            winning_ticket = str(official["ticket"])
            hit = winning_ticket in selected
            inv = len(selected) * UNIT_YEN
            ret = int(official["payout_yen"]) if hit else 0
            row = {
                "race_id": race["race_id"],
                "race_date": race["race_date"],
                "venue_id": race["venue_id"],
                "race_no": race["race_no"],
                "tier": race["tier"],
                "bet_type": bet_type,
                "strategy": strategy,
                "ticket_count": len(selected),
                "winning_ticket": winning_ticket,
                "selected_tickets": selected,
                "payout_yen": int(official["payout_yen"]),
                "hit": hit,
                "investment_yen": inv,
                "return_yen": ret,
            }
            overall[(bet_type, strategy)].append(row)
            tiers[(race["tier"], bet_type, strategy)].append(row)
        evaluated_frozen_races += 1 if race_has_any else 0

    reports = {f"{b}|{s}": aggregate(rows) for (b, s), rows in sorted(overall.items())}
    tier_reports = {f"{t}|{b}|{s}": aggregate(rows) for (t, b, s), rows in sorted(tiers.items())}

    out = {
        "contract": "candidate_discovery_multibet_roi_k_smoke_v1",
        "period": {"start": START_DATE, "end": END_DATE},
        "selection_variant": "MOTOR2_FACTOR",
        "daily_race_cap": RACE_CAP,
        "unit_yen_per_ticket": UNIT_YEN,
        "frozen_races": len(frozen),
        "selected_days": selected_days,
        "k_archive_errors": k_errors,
        "k_archive_stats": k_stats,
        "evaluated_frozen_races": evaluated_frozen_races,
        "missing_payout_rows": missing_payout_rows,
        "reports": reports,
        "tier_reports": tier_reports,
        "smoke_only": True,
        "promotion_allowed": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for key in (
        "trifecta|top1", "trifecta|top2", "trifecta|top3", "trifecta|top5",
        "exacta|top1", "exacta|top2", "exacta|top3", "exacta|top5",
        "trio|top1", "trio|top2", "trio|top3", "trio|top5",
    ):
        if key in reports:
            m = reports[key]
            compact = {k: m[k] for k in (
                "evaluated_races", "hits", "race_hit_rate_pct", "investment_yen",
                "return_yen", "profit_yen", "roi_pct", "max_losing_race_streak",
                "max_drawdown_yen", "positive_day_rate_pct", "max_single_hit_share_of_returns_pct"
            )}
            print(f"CANDIDATE_MULTIBET_ROI={key} {json.dumps(compact, sort_keys=True)}", flush=True)

    print(f"CANDIDATE_MULTIBET_ROI_MISSING_PAYOUT_ROWS={missing_payout_rows}", flush=True)
    print("CANDIDATE_MULTIBET_ROI_PROMOTION=BLOCK_SMOKE_ONLY", flush=True)
    print("CANDIDATE_MULTIBET_ROI_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"CANDIDATE_MULTIBET_ROI_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
