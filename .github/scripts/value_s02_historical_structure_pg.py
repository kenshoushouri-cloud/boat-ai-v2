# -*- coding: utf-8 -*-
"""Read-only historical structural screen for pre-declared S02 expansions.

Important limitations:
- Uses v2_odds_trifecta, which may contain final/repaired historical odds.
- Therefore this is NOT PRE-timing ROI evidence and NOT an OOS promotion test.
- Its only purpose is to eliminate structurally weak expansion ideas before
  future natural PRE Forward observation.
- Variants were declared before this historical screen and differ from S02 in
  one dimension only. No combination search is performed.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import v24_pre_candidate_notifier_pg as v24

START_DATE = date.fromisoformat(os.getenv("VALUE_S02_HIST_START", "2025-07-01"))
END_DATE = date.fromisoformat(os.getenv("VALUE_S02_HIST_END", "2026-08-13"))
SPLIT_DATE = date.fromisoformat(os.getenv("VALUE_S02_HIST_SPLIT", "2026-03-01"))
OUTPUT = Path(os.getenv("VALUE_S02_HIST_OUTPUT", "value-s02-historical-structure.json"))
UNIT_YEN = 100

BASE = {
    "pr_min": 16, "pr_max": 30,
    "mr_min": 6, "mr_max": 10,
    "odds_min": 20.0, "odds_max": 30.0,
    "race_nos": {7, 8, 9},
}
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


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except Exception:
        return default


def month_ranges(start: date, end: date):
    cur = start.replace(day=1)
    while cur <= end:
        if cur.month == 12:
            nxt = cur.replace(year=cur.year + 1, month=1)
        else:
            nxt = cur.replace(month=cur.month + 1)
        lo = max(start, cur)
        hi = min(end + timedelta(days=1), nxt)
        if lo < hi:
            yield lo, hi
        cur = nxt


def new_stat() -> dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "return_yen": 0,
        "hit_returns": [],
        "records": [],
    }


def add(stat: dict[str, Any], d: str, rid: str, ticket: str, hit: bool, payout: int) -> None:
    stat["bets"] += 1
    stat["hits"] += int(hit)
    if hit:
        stat["return_yen"] += payout
        stat["hit_returns"].append(payout)
    stat["records"].append((d, rid, ticket, bool(hit), payout if hit else 0))


def summarize_records(records: list[tuple]) -> dict[str, Any]:
    bets = len(records)
    hits = sum(1 for r in records if r[3])
    ret = sum(int(r[4]) for r in records)
    inv = bets * UNIT_YEN
    hit_returns = sorted((int(r[4]) for r in records if r[3] and int(r[4]) > 0), reverse=True)
    month_rows: dict[str, list[tuple]] = defaultdict(list)
    for rec in records:
        month_rows[str(rec[0])[:7]].append(rec)
    by_month = {}
    positive_months = 0
    for month, rows in sorted(month_rows.items()):
        mbets = len(rows)
        mhits = sum(1 for r in rows if r[3])
        mret = sum(int(r[4]) for r in rows)
        minv = mbets * UNIT_YEN
        profit = mret - minv
        positive_months += int(profit > 0)
        by_month[month] = {
            "bets": mbets,
            "hits": mhits,
            "return_yen": mret,
            "profit_yen": profit,
            "roi_pct": round(mret / minv * 100.0, 4) if minv else None,
        }
    return {
        "bets": bets,
        "hits": hits,
        "hit_rate_pct": round(hits / bets * 100.0, 4) if bets else None,
        "investment_yen": inv,
        "return_yen": ret,
        "profit_yen": ret - inv,
        "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / ret * 100.0, 4) if hit_returns and ret else 0.0,
        "months": len(by_month),
        "positive_months": positive_months,
        "positive_month_ratio_pct": round(positive_months / len(by_month) * 100.0, 4) if by_month else None,
        "by_month": by_month,
    }


def summarize(stat: dict[str, Any]) -> dict[str, Any]:
    records = list(stat["records"])
    early = [r for r in records if date.fromisoformat(str(r[0])) < SPLIT_DATE]
    late = [r for r in records if date.fromisoformat(str(r[0])) >= SPLIT_DATE]
    return {
        "overall": summarize_records(records),
        "early": summarize_records(early),
        "late": summarize_records(late),
    }


def match(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    return (
        rule["pr_min"] <= si(row.get("prob_rank"), 999) <= rule["pr_max"]
        and rule["mr_min"] <= si(row.get("market_rank"), 999) <= rule["mr_max"]
        and rule["odds_min"] <= sf(row.get("odds"), 0.0) < rule["odds_max"]
    )


def fetch_month(conn: psycopg.Connection[Any], lo: date, hi: date):
    with conn.cursor() as cur:
        cur.execute(
            "select * from v2_races where race_date >= %s and race_date < %s order by race_date,venue_id,race_no",
            (lo, hi),
        )
        races = []
        for row in cur.fetchall():
            r = dict(row)
            venue_id = str(r.get("venue_id") or r.get("venue_code") or "").zfill(2)
            race_no = si(r.get("race_no"), 0)
            if 6 <= race_no <= 10 and v24._infer_venue_style(venue_id) == "in_strong":
                races.append(r)

        race_ids = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
        if not race_ids:
            return [], {}, {}, {}, {}

        cur.execute(
            """select race_id,trifecta_ticket,trifecta_payout_yen,result_status,race_status,
                      finish_order,winning_method
                 from v2_results
                where race_id = any(%s)
                  and trifecta_ticket is not null
                  and trifecta_payout_yen is not null
                  and trifecta_payout_yen > 0
                  and finish_order is not null
                  and winning_method is not null
                  and coalesce(result_status,'')='official'
                  and coalesce(race_status,'')='official'""",
            (race_ids,),
        )
        results = {str(r["race_id"]): dict(r) for r in cur.fetchall()}
        valid_ids = sorted(results)
        if not valid_ids:
            return [], {}, {}, {}, {}

        cur.execute(
            """select race_id,lane,racer_number,racer_class,racer_name,
                      national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,
                      motor_no,boat_no,avg_st
                 from v2_race_entries
                where race_id = any(%s)
                order by race_id,lane""",
            (valid_ids,),
        )
        entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries[str(row["race_id"])].append(dict(row))

        cur.execute(
            """select race_id,ticket,odds
                 from v2_odds_trifecta
                where race_id = any(%s)
                order by race_id,ticket""",
            (valid_ids,),
        )
        odds: dict[str, dict[str, float]] = defaultdict(dict)
        for row in cur.fetchall():
            rid = str(row["race_id"])
            ticket = v24._norm_ticket(row.get("ticket"))
            odd = sf(row.get("odds"), 0.0)
            if ticket and odd > 0:
                odds[rid][ticket] = odd

        cur.execute(
            """select race_id,count(*)::int as n
                 from v2_result_entries
                where race_id = any(%s)
                group by race_id""",
            (valid_ids,),
        )
        result_entry_counts = {str(r["race_id"]): si(r.get("n"), 0) for r in cur.fetchall()}

    race_by = {str(r.get("race_id")): r for r in races if str(r.get("race_id")) in results}
    return list(race_by.values()), dict(entries), dict(odds), results, result_entry_counts


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_S02_HIST_MODE=read_only_structural_screen", flush=True)
    print(f"VALUE_S02_HIST_PERIOD={START_DATE}..{END_DATE} split={SPLIT_DATE}", flush=True)
    print("VALUE_S02_HIST_ODDS_WARNING=v2_odds_trifecta_may_be_final_or_repaired_not_PRE_timing", flush=True)
    print("VALUE_S02_HIST_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)
    print("VALUE_S02_HIST_VARIANTS=" + ",".join(VARIANTS), flush=True)

    stats = {name: new_stat() for name in VARIANTS}
    audit = {
        "months_processed": 0,
        "scope_races": 0,
        "ready_races": 0,
        "skipped_entries": 0,
        "skipped_result_entries": 0,
        "skipped_odds": 0,
    }

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='32MB'")

        for lo, hi in month_ranges(START_DATE, END_DATE):
            races, entries_by, odds_by, results, result_entry_counts = fetch_month(conn, lo, hi)
            audit["months_processed"] += 1
            audit["scope_races"] += len(races)
            month_ready = 0
            for race in races:
                rid = str(race.get("race_id") or "")
                entries = entries_by.get(rid, [])
                if len(v24._entry_by_lane(entries)) != 6:
                    audit["skipped_entries"] += 1
                    continue
                if result_entry_counts.get(rid, 0) != 6:
                    audit["skipped_result_entries"] += 1
                    continue
                odds = odds_by.get(rid, {})
                ready, _ = v24._validate_odds_snapshot(odds)
                if len(odds) != 120 or not ready:
                    audit["skipped_odds"] += 1
                    continue
                result = results.get(rid)
                if not result:
                    continue
                audit["ready_races"] += 1
                month_ready += 1

                venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
                race_no = si(race.get("race_no"), 0)
                ranked = v24._rank_candidates(entries, venue_id, odds)
                result_ticket = v24._norm_ticket(result.get("trifecta_ticket")) or ""
                payout = si(result.get("trifecta_payout_yen"), 0)
                race_date = str(race.get("race_date"))

                for name, rule in VARIANTS.items():
                    if race_no not in rule["race_nos"]:
                        continue
                    matches = [row for row in ranked if match(row, rule)]
                    if not matches:
                        continue
                    selected = max(matches, key=lambda row: (sf(row.get("prob")), sf(row.get("raw_ev"))))
                    ticket = v24._norm_ticket(selected.get("ticket")) or ""
                    if not ticket:
                        continue
                    add(stats[name], race_date, rid, ticket, ticket == result_ticket, payout)

            print(f"VALUE_S02_HIST_MONTH={lo:%Y-%m} scope:{len(races)} ready:{month_ready}", flush=True)
        conn.rollback()

    summaries = {name: summarize(stat) for name, stat in stats.items()}
    base_bets = int(summaries["BASE"]["overall"]["bets"] or 0)
    for name, summary in summaries.items():
        overall = summary["overall"]
        overall["volume_delta_vs_base"] = int(overall["bets"] or 0) - base_bets
        overall["volume_ratio_vs_base"] = round(overall["bets"] / base_bets, 4) if base_bets else None

    out = {
        "contract": "value_s02_historical_structure_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat(), "split": SPLIT_DATE.isoformat()},
        "warning": "historical v2_odds_trifecta can be final/repaired; use only as structural screen, never PRE timing evidence",
        "audit": audit,
        "variants": {
            name: {
                "rule": {k: (sorted(v) if isinstance(v, set) else v) for k, v in VARIANTS[name].items()},
                **summaries[name],
            }
            for name in VARIANTS
        },
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("VALUE_S02_HIST_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    for name in VARIANTS:
        o = summaries[name]["overall"]
        e = summaries[name]["early"]
        l = summaries[name]["late"]
        print(
            f"VALUE_S02_HIST_VARIANT={name} bets:{o['bets']} delta:{o['volume_delta_vs_base']} "
            f"roi:{o['roi_pct']} hits:{o['hits']} pos_months:{o['positive_months']}/{o['months']} "
            f"single_hit_share:{o['single_hit_share_pct']} early_roi:{e['roi_pct']} late_roi:{l['roi_pct']}",
            flush=True,
        )
    print("VALUE_S02_HIST_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S02_HIST_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
