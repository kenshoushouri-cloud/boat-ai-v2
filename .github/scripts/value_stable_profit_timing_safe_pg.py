# -*- coding: utf-8 -*-
"""Read-only timing-integrity audit for frozen Phase-4 A_STABLE/B_PROFIT.

The candidate thresholds and 15-minute decision cutoff are frozen before this
script's realized ROI is inspected. This is not a reconstruction of the current
PRE notifier timestamp. It is a separate deadline-minus-15m research contract.

No DB writes / LINE / BUY / Production behavior changes.
"""
from __future__ import annotations

import hashlib
import json
import math
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

START_DATE = date.fromisoformat(os.getenv("VALUE_STABLE_TIMING_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_STABLE_TIMING_END", "2026-09-12"))
CUTOFF_MINUTES = 15
MAX_LABEL_SPREAD_SECONDS = 60.0
UNIT_YEN = 100
OUTPUT = Path(os.getenv("VALUE_STABLE_TIMING_OUTPUT", "value-stable-profit-timing-safe.json"))

RULES = (
    {
        "id": "A_STABLE",
        "prob_rank": (11, 25),
        "market_rank": (2, 5),
        "odds": (3.0, 6.0),
        "race_nos": tuple(range(7, 13)),
        "select_mode": "ev",
    },
    {
        "id": "B_PROFIT",
        "prob_rank": (11, 20),
        "market_rank": (2, 5),
        "odds": (3.0, 6.0),
        "race_nos": tuple(range(7, 11)),
        "select_mode": "ev",
    },
)

FROZEN_CONFIG = {
    "contract": "phase4_ab_timing_safe_deadline_minus_15m_v1",
    "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
    "timing": {
        "cutoff_minutes_before_deadline": CUTOFF_MINUTES,
        "max_label_spread_seconds": MAX_LABEL_SPREAD_SECONDS,
        "ticket_rows": 120,
        "distinct_tickets": 120,
        "all_odds_gt": 1.0,
        "selection": "latest coherent label fully observable by cutoff",
    },
    "rules": [
        {
            **{k: v for k, v in rule.items() if k != "race_nos"},
            "race_nos": list(rule["race_nos"]),
        }
        for rule in RULES
    ],
    "unit_yen": UNIT_YEN,
}
FROZEN_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(FROZEN_CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


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


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return round(xs[0], 4)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return round(xs[lo], 4)
    weight = pos - lo
    return round(xs[lo] * (1.0 - weight) + xs[hi] * weight, 4)


def max_losing_streak(rows: list[dict[str, Any]]) -> int:
    best = 0
    current = 0
    for row in rows:
        if bool(row.get("hit")):
            current = 0
        else:
            current += 1
            best = max(best, current)
    return best


def max_drawdown_yen(rows: list[dict[str, Any]]) -> int:
    equity = 0
    peak = 0
    worst = 0
    for row in rows:
        equity += si(row.get("profit_yen"), 0)
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def summarize(rows: list[dict[str, Any]], calendar_days: int) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: (str(r.get("race_date")), str(r.get("race_id"))))
    evaluated = [r for r in ordered if r.get("evaluated")]
    pending = len(ordered) - len(evaluated)
    hits = sum(1 for r in evaluated if bool(r.get("hit")))
    invested = len(evaluated) * UNIT_YEN
    returned = sum(si(r.get("return_yen"), 0) for r in evaluated)
    hit_returns = sorted((si(r.get("return_yen"), 0) for r in evaluated if bool(r.get("hit"))), reverse=True)

    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated:
        by_month[str(row.get("race_date"))[:7]].append(row)
    monthly: dict[str, dict[str, Any]] = {}
    for month, rr in sorted(by_month.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(si(r.get("return_yen"), 0) for r in rr)
        monthly[month] = {
            "evaluated": len(rr),
            "hits": sum(1 for r in rr if bool(r.get("hit"))),
            "investment_yen": inv,
            "return_yen": ret,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        }

    return {
        "candidate_rows": len(ordered),
        "candidates_per_30_calendar_days": round(len(ordered) / calendar_days * 30.0, 4) if calendar_days else None,
        "evaluated": len(evaluated),
        "pending": pending,
        "hits": hits,
        "hit_rate_pct": round(hits / len(evaluated) * 100.0, 4) if evaluated else None,
        "investment_yen": invested,
        "return_yen": returned,
        "profit_yen": returned - invested,
        "roi_pct": round(returned / invested * 100.0, 4) if invested else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / returned * 100.0, 4) if hit_returns and returned else 0.0,
        "max_losing_streak": max_losing_streak(evaluated),
        "max_drawdown_yen": max_drawdown_yen(evaluated),
        "by_month": monthly,
    }


def select_candidate(ranked: list[dict[str, Any]], rule: dict[str, Any], race_no: int) -> dict[str, Any] | None:
    if race_no not in rule["race_nos"]:
        return None
    matches = []
    for row in ranked:
        pr = si(row.get("prob_rank"), 999)
        mr = si(row.get("market_rank"), 999)
        odd = sf(row.get("odds"), 0.0)
        if (
            rule["prob_rank"][0] <= pr <= rule["prob_rank"][1]
            and rule["market_rank"][0] <= mr <= rule["market_rank"][1]
            and rule["odds"][0] <= odd < rule["odds"][1]
        ):
            matches.append(row)
    if not matches:
        return None
    return max(matches, key=lambda r: (sf(r.get("raw_ev")), sf(r.get("prob"))))


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if END_DATE < START_DATE:
        raise RuntimeError("END_DATE must be >= START_DATE")

    print("VALUE_STABLE_TIMING_MODE=read_only_frozen_contract", flush=True)
    print(f"VALUE_STABLE_TIMING_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(f"VALUE_STABLE_TIMING_CUTOFF_MINUTES={CUTOFF_MINUTES}", flush=True)
    print(f"VALUE_STABLE_TIMING_CONFIG_SHA256={FROZEN_CONFIG_SHA256}", flush=True)
    print("VALUE_STABLE_TIMING_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local idle_in_transaction_session_timeout='60s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='16MB'")

            cur.execute(
                """
                with c as (
                  select race_id,race_date,
                         coalesce(nullif(venue_id,''), nullif(venue_code,'')) as venue_id,
                         race_no,deadline_at
                    from v2_races
                   where race_date between %s and %s
                     and deadline_at is not null
                ), grouped as (
                  select c.race_id,c.deadline_at,o.snapshot_label,
                         count(*)::bigint as row_count,
                         count(distinct o.ticket)::bigint as ticket_count,
                         count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                         min(o.snapshot_at) as first_snapshot_at,
                         max(o.snapshot_at) as last_snapshot_at
                    from c
                    join v2_realtime_odds_snapshots o on o.race_id=c.race_id
                   where o.snapshot_label is not null
                   group by c.race_id,c.deadline_at,o.snapshot_label
                ), valid as (
                  select *, extract(epoch from (last_snapshot_at-first_snapshot_at)) as spread_seconds
                    from grouped
                   where row_count=120
                     and ticket_count=120
                     and positive_odds_count=120
                     and last_snapshot_at <= deadline_at - (%s * interval '1 minute')
                     and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
                ), chosen as (
                  select distinct on (race_id)
                         race_id,snapshot_label,first_snapshot_at,last_snapshot_at,spread_seconds
                    from valid
                   order by race_id,last_snapshot_at desc,snapshot_label desc
                )
                select c.race_id,c.race_date,c.venue_id,c.race_no,c.deadline_at,
                       ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at,ch.spread_seconds,
                       o.ticket,o.odds,
                       (select count(*)::bigint from c) as total_races,
                       (select count(*)::bigint from valid) as valid_labels
                  from chosen ch
                  join c on c.race_id=ch.race_id
                  join v2_realtime_odds_snapshots o
                    on o.race_id=ch.race_id and o.snapshot_label=ch.snapshot_label
                 order by c.race_date,c.race_id,o.ticket
                """,
                (START_DATE, END_DATE, CUTOFF_MINUTES, MAX_LABEL_SPREAD_SECONDS),
            )
            odds_rows = [dict(r) for r in cur.fetchall()]

            chosen_meta: dict[str, dict[str, Any]] = {}
            odds_by: dict[str, dict[str, float]] = defaultdict(dict)
            total_races = 0
            valid_labels = 0
            for row in odds_rows:
                rid = str(row.get("race_id") or "")
                if not rid:
                    continue
                total_races = max(total_races, si(row.get("total_races"), 0))
                valid_labels = max(valid_labels, si(row.get("valid_labels"), 0))
                chosen_meta.setdefault(rid, {
                    "race_id": rid,
                    "race_date": row.get("race_date"),
                    "venue_id": str(row.get("venue_id") or "").zfill(2),
                    "race_no": si(row.get("race_no"), 0),
                    "deadline_at": row.get("deadline_at"),
                    "snapshot_label": row.get("snapshot_label"),
                    "first_snapshot_at": row.get("first_snapshot_at"),
                    "last_snapshot_at": row.get("last_snapshot_at"),
                    "spread_seconds": sf(row.get("spread_seconds"), 0.0),
                })
                ticket = v24._norm_ticket(row.get("ticket"))
                odd = sf(row.get("odds"), 0.0)
                if ticket and odd > 1.0:
                    odds_by[rid][ticket] = odd

            race_ids = sorted(chosen_meta)
            entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
            results_by: dict[str, tuple[str, int]] = {}
            if race_ids:
                cur.execute(
                    """select race_id,lane,racer_number,racer_class,racer_name,
                              national_win_rate,national_place2_rate,
                              local_win_rate,local_place2_rate,
                              motor_no,boat_no,avg_st
                         from v2_race_entries
                        where race_id = any(%s)
                        order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries_by[str(row["race_id"])].append(dict(row))

                cur.execute(
                    """select race_id,trifecta_ticket,trifecta_payout_yen
                         from v2_results
                        where race_id = any(%s)""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    rid = str(row.get("race_id") or "")
                    ticket = v24._norm_ticket(row.get("trifecta_ticket"))
                    payout = si(row.get("trifecta_payout_yen"), 0)
                    if rid and ticket and payout > 0:
                        results_by[rid] = (ticket, payout)
        conn.rollback()

    label_gaps: list[float] = []
    entry_ready = 0
    result_ready = 0
    odds_ready = 0
    candidate_rows: dict[str, list[dict[str, Any]]] = {str(rule["id"]): [] for rule in RULES}

    for rid, meta in sorted(chosen_meta.items(), key=lambda item: (str(item[1]["race_date"]), item[0])):
        deadline = meta.get("deadline_at")
        last_snapshot = meta.get("last_snapshot_at")
        if deadline is not None and last_snapshot is not None:
            label_gaps.append((deadline - last_snapshot).total_seconds() / 60.0)

        odds = odds_by.get(rid, {})
        if len(odds) != 120:
            continue
        odds_ready += 1
        entries = entries_by.get(rid, [])
        if len(v24._entry_by_lane(entries)) != 6:
            continue
        entry_ready += 1
        result = results_by.get(rid)
        if result:
            result_ready += 1

        ranked = v24._rank_candidates(entries, str(meta.get("venue_id") or "").zfill(2), odds)
        for rule in RULES:
            selected = select_candidate(ranked, rule, si(meta.get("race_no"), 0))
            if not selected:
                continue
            result_ticket, payout = result if result else ("", 0)
            selected_ticket = v24._norm_ticket(selected.get("ticket"))
            evaluated = bool(result)
            hit = bool(evaluated and selected_ticket == result_ticket)
            return_yen = payout if hit else (0 if evaluated else None)
            profit_yen = (si(return_yen, 0) - UNIT_YEN) if evaluated else None
            candidate_rows[str(rule["id"])].append({
                "race_id": rid,
                "race_date": str(meta.get("race_date"))[:10],
                "race_no": si(meta.get("race_no"), 0),
                "ticket": selected_ticket,
                "odds": sf(selected.get("odds")),
                "prob": sf(selected.get("prob")),
                "prob_rank": si(selected.get("prob_rank"), 999),
                "market_rank": si(selected.get("market_rank"), 999),
                "raw_ev": sf(selected.get("raw_ev")),
                "snapshot_label": str(meta.get("snapshot_label") or ""),
                "minutes_before_deadline": round((deadline - last_snapshot).total_seconds() / 60.0, 4) if deadline and last_snapshot else None,
                "evaluated": evaluated,
                "hit": hit if evaluated else None,
                "return_yen": return_yen,
                "profit_yen": profit_yen,
            })

    calendar_days = (END_DATE - START_DATE).days + 1
    summaries = {rule_id: summarize(rows, calendar_days) for rule_id, rows in candidate_rows.items()}
    timing = {
        "selected_races": len(chosen_meta),
        "minutes_before_deadline": {
            "min": round(min(label_gaps), 4) if label_gaps else None,
            "p05": percentile(label_gaps, 0.05),
            "p50": percentile(label_gaps, 0.50),
            "p95": percentile(label_gaps, 0.95),
            "max": round(max(label_gaps), 4) if label_gaps else None,
        },
    }
    audit = {
        "total_races_with_deadline": total_races,
        "valid_coherent_labels": valid_labels,
        "races_with_chosen_timing_safe_label": len(chosen_meta),
        "odds_ready_120": odds_ready,
        "entry_ready_6lanes": entry_ready,
        "result_ready": result_ready,
    }

    out = {
        "frozen_config": FROZEN_CONFIG,
        "frozen_config_sha256": FROZEN_CONFIG_SHA256,
        "audit": audit,
        "timing": timing,
        "variants": summaries,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("VALUE_STABLE_TIMING_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    print("VALUE_STABLE_TIMING_GAP=" + json.dumps(timing["minutes_before_deadline"], sort_keys=True), flush=True)
    for rule in RULES:
        rid = str(rule["id"])
        s = summaries[rid]
        print(
            f"VALUE_STABLE_TIMING_VARIANT={rid} candidates:{s['candidate_rows']} per30d:{s['candidates_per_30_calendar_days']} "
            f"evaluated:{s['evaluated']} pending:{s['pending']} hits:{s['hits']} roi:{s['roi_pct']} "
            f"profit:{s['profit_yen']} single_hit_share:{s['single_hit_share_pct']} "
            f"lose_streak:{s['max_losing_streak']} max_dd:{s['max_drawdown_yen']}",
            flush=True,
        )
        print("VALUE_STABLE_TIMING_MONTHLY=" + rid + ":" + json.dumps(s["by_month"], sort_keys=True), flush=True)
    print("VALUE_STABLE_TIMING_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_STABLE_TIMING_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
