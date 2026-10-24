# -*- coding: utf-8 -*-
"""Read-only timing-safe S02 boundary expansion audit.

Purpose:
- Reconstruct S02 on the current Forward timing-safe race universe.
- Compare the frozen S02 rule with pre-declared one-dimension expansions only.
- Measure candidate volume and official-payout ROI without changing Production.

This is hypothesis evaluation, not a Production threshold recommendation.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v24_pre_candidate_notifier_pg as v24

START_DATE = date.fromisoformat(os.getenv("VALUE_S02_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_S02_END", "2026-09-12"))
MAX_LABEL_SPREAD_SECONDS = float(os.getenv("VALUE_S02_MAX_LABEL_SPREAD_SECONDS", "60"))
OUTPUT = Path(os.getenv("VALUE_S02_OUTPUT", "value-s02-timing-safe-expansion.json"))
UNIT_YEN = 100

BASE = {
    "pr_min": 16, "pr_max": 30,
    "mr_min": 6, "mr_max": 10,
    "odds_min": 20.0, "odds_max": 30.0,
    "race_nos": {7, 8, 9},
}

# Pre-declared, one-dimension-only expansions. No combinations and no post-hoc search.
VARIANTS: dict[str, dict[str, Any]] = {
    "BASE": dict(BASE),
    "PR_LOWER_11": {**BASE, "pr_min": 11},
    "PR_UPPER_35": {**BASE, "pr_max": 35},
    "MR_LOWER_5": {**BASE, "mr_min": 5},
    "MR_UPPER_12": {**BASE, "mr_max": 12},
    "ODDS_LOWER_18": {**BASE, "odds_min": 18.0},
    "ODDS_UPPER_35": {**BASE, "odds_max": 35.0},
    "RACE_LOWER_R06": {**BASE, "race_nos": {6, 7, 8, 9}},
    "RACE_UPPER_R10": {**BASE, "race_nos": {7, 8, 9, 10}},
}


def si(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except Exception:
        return default


def sf(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except Exception:
        return default


def canonical_ticket(value: Any) -> str:
    return v24._norm_ticket(value) or ""


def latest_complete_labels(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with c as (
              select race_id,min(race_date) as race_date,min(deadline_at) as deadline_at
                from v2_racer_course_top3_forward_shadow
               where race_date between %s and %s
                 and deadline_at is not null
               group by race_id
            ), grouped as (
              select c.race_id,c.race_date,c.deadline_at,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from c
                join v2_realtime_odds_snapshots o on o.race_id=c.race_id
               where o.snapshot_label is not null
               group by c.race_id,c.race_date,c.deadline_at,o.snapshot_label
            ), valid as (
              select *,extract(epoch from (last_snapshot_at-first_snapshot_at)) as spread_seconds
                from grouped
               where row_count=120
                 and ticket_count=120
                 and positive_odds_count=120
                 and last_snapshot_at <= deadline_at
                 and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
            )
            select distinct on (race_id)
                   race_id,race_date,deadline_at,snapshot_label,first_snapshot_at,last_snapshot_at,spread_seconds
              from valid
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (START_DATE, END_DATE, MAX_LABEL_SPREAD_SECONDS),
        )
        return [dict(r) for r in cur.fetchall()]


def fetch_inputs(conn: psycopg.Connection[Any], labels: list[dict[str, Any]]) -> tuple[dict, dict, dict, dict]:
    if not labels:
        return {}, {}, {}, {}
    race_ids = [str(r["race_id"]) for r in labels]
    label_by = {str(r["race_id"]): str(r["snapshot_label"]) for r in labels}

    with conn.cursor() as cur:
        cur.execute("select * from v2_races where race_id = any(%s)", (race_ids,))
        races = {str(r["race_id"]): dict(r) for r in cur.fetchall()}

        cur.execute(
            """select race_id,lane,racer_number,racer_class,racer_name,
                      national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,
                      motor_no,boat_no,avg_st
                 from v2_race_entries
                where race_id = any(%s)
                order by race_id,lane""",
            (race_ids,),
        )
        entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries[str(row["race_id"])].append(dict(row))

        cur.execute(
            """select race_id,ticket,odds,snapshot_label,snapshot_at
                 from v2_realtime_odds_snapshots
                where race_id = any(%s)
                  and odds is not null and odds > 1.0
                order by race_id,snapshot_label,ticket""",
            (race_ids,),
        )
        odds: dict[str, dict[str, float]] = defaultdict(dict)
        for row in cur.fetchall():
            rid = str(row["race_id"])
            if str(row.get("snapshot_label") or "") != label_by.get(rid):
                continue
            ticket = canonical_ticket(row.get("ticket"))
            odd = sf(row.get("odds"), 0.0)
            if ticket and odd > 1.0:
                odds[rid][ticket] = odd

        cur.execute(
            """select race_id,trifecta_ticket,trifecta_payout_yen,result_status,race_status
                 from v2_results
                where race_id = any(%s)
                  and trifecta_ticket is not null
                  and trifecta_payout_yen is not null
                  and trifecta_payout_yen > 0""",
            (race_ids,),
        )
        results = {str(r["race_id"]): dict(r) for r in cur.fetchall()}

    return races, dict(entries), dict(odds), results


def match(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    return (
        rule["pr_min"] <= si(row.get("prob_rank"), 999) <= rule["pr_max"]
        and rule["mr_min"] <= si(row.get("market_rank"), 999) <= rule["mr_max"]
        and rule["odds_min"] <= sf(row.get("odds"), 0.0) < rule["odds_max"]
    )


def new_stat() -> dict[str, Any]:
    return {"bets": 0, "hits": 0, "return_yen": 0, "hit_returns": [], "dates": defaultdict(lambda: {"bets": 0, "hits": 0, "return_yen": 0})}


def add(stat: dict[str, Any], race_date: str, hit: bool, payout: int) -> None:
    stat["bets"] += 1
    stat["hits"] += int(hit)
    if hit:
        stat["return_yen"] += payout
        stat["hit_returns"].append(payout)
    d = stat["dates"][race_date]
    d["bets"] += 1
    d["hits"] += int(hit)
    if hit:
        d["return_yen"] += payout


def summarize(stat: dict[str, Any]) -> dict[str, Any]:
    bets = int(stat["bets"])
    hits = int(stat["hits"])
    ret = int(stat["return_yen"])
    inv = bets * UNIT_YEN
    payouts = sorted((int(x) for x in stat["hit_returns"]), reverse=True)
    by_date = {}
    for d, rec in sorted(stat["dates"].items()):
        dinv = rec["bets"] * UNIT_YEN
        by_date[d] = {
            "bets": rec["bets"], "hits": rec["hits"], "return_yen": rec["return_yen"],
            "roi_pct": round(rec["return_yen"] / dinv * 100.0, 4) if dinv else None,
        }
    return {
        "bets": bets,
        "hits": hits,
        "hit_rate_pct": round(hits / bets * 100.0, 4) if bets else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        "max_hit_yen": payouts[0] if payouts else 0,
        "single_hit_share_pct": round((payouts[0] / ret * 100.0), 4) if payouts and ret else 0.0,
        "by_date": by_date,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_S02_EXPANSION_MODE=read_only_predeclared_one_dimension", flush=True)
    print(f"VALUE_S02_EXPANSION_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_S02_EXPANSION_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    print("VALUE_S02_EXPANSION_VARIANTS=" + ",".join(VARIANTS), flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")
        labels = latest_complete_labels(conn)
        races, entries_by, odds_by, results = fetch_inputs(conn, labels)
        conn.rollback()

    label_date = {str(r["race_id"]): str(r["race_date"]) for r in labels}
    stats = {name: new_stat() for name in VARIANTS}
    audit = {
        "complete_timing_safe_races": len(labels),
        "ready_s02_style_races": 0,
        "skipped_entries": 0,
        "skipped_odds": 0,
        "skipped_result": 0,
    }

    for rec in labels:
        rid = str(rec["race_id"])
        race = races.get(rid)
        entries = entries_by.get(rid, [])
        odds = odds_by.get(rid, {})
        result = results.get(rid)
        if not race or len(v24._entry_by_lane(entries)) != 6:
            audit["skipped_entries"] += 1
            continue
        ready, _ = v24._validate_odds_snapshot(odds)
        if len(odds) != 120 or not ready:
            audit["skipped_odds"] += 1
            continue
        if not result or str(result.get("result_status") or "official") != "official" or str(result.get("race_status") or "official") != "official":
            audit["skipped_result"] += 1
            continue

        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = si(race.get("race_no"), 0)
        if v24._infer_venue_style(venue_id) != "in_strong":
            continue
        audit["ready_s02_style_races"] += 1
        ranked = v24._rank_candidates(entries, venue_id, odds)
        result_ticket = canonical_ticket(result.get("trifecta_ticket"))
        payout = si(result.get("trifecta_payout_yen"), 0)
        race_date = label_date.get(rid, "")

        for name, rule in VARIANTS.items():
            if race_no not in rule["race_nos"]:
                continue
            matches = [row for row in ranked if match(row, rule)]
            if not matches:
                continue
            selected = max(matches, key=lambda row: (sf(row.get("prob")), sf(row.get("raw_ev"))))
            ticket = canonical_ticket(selected.get("ticket"))
            if not ticket:
                continue
            add(stats[name], race_date, ticket == result_ticket, payout)

    summaries = {name: summarize(stat) for name, stat in stats.items()}
    base_bets = int(summaries["BASE"]["bets"] or 0)
    for name, summary in summaries.items():
        summary["volume_delta_vs_base"] = int(summary["bets"] or 0) - base_bets
        summary["volume_ratio_vs_base"] = round((summary["bets"] / base_bets), 4) if base_bets else None

    out = {
        "contract": "value_s02_timing_safe_expansion_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "selection": "one_ticket_per_race_max_probability_within_rule",
        "rule_scope": "S02 in_strong; one dimension expanded at a time; no combinations",
        "audit": audit,
        "variants": {name: {**{k: (sorted(v) if isinstance(v, set) else v) for k, v in rule.items()}, **summaries[name]} for name, rule in VARIANTS.items()},
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("VALUE_S02_EXPANSION_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    for name in VARIANTS:
        s = summaries[name]
        print(
            f"VALUE_S02_VARIANT={name} bets:{s['bets']} delta:{s['volume_delta_vs_base']} hits:{s['hits']} "
            f"roi:{s['roi_pct']} profit:{s['profit_yen']} single_hit_share:{s['single_hit_share_pct']}",
            flush=True,
        )
    print("VALUE_S02_EXPANSION_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S02_EXPANSION_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
