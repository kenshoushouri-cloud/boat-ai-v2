# -*- coding: utf-8 -*-
"""Outcome-blind, read-only candidate geometry audit for timing-safe final_ab odds.

No results/payouts/hit/ROI are read. The audit maps only current candidate density.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import v24_pre_candidate_notifier_pg as v24

START_DATE = date.fromisoformat(os.getenv("VALUE_GEOMETRY_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("VALUE_GEOMETRY_END", "2026-09-12"))
MAX_SPREAD_SECONDS = 60.0
OUTPUT = Path(os.getenv("VALUE_GEOMETRY_OUTPUT", "value-final-ab-candidate-geometry.json"))

RANK_BANDS = ((1, 5, "01-05"), (6, 10, "06-10"), (11, 20, "11-20"), (21, 40, "21-40"), (41, 80, "41-80"), (81, 120, "81-120"))
ODDS_BANDS = ((0.0, 3.0, "<3"), (3.0, 6.0, "3-6"), (6.0, 10.0, "6-10"), (10.0, 20.0, "10-20"), (20.0, 30.0, "20-30"), (30.0, 50.0, "30-50"), (50.0, float("inf"), "50+"))
RACE_GROUPS = ((1, 3, "R01-03"), (4, 6, "R04-06"), (7, 9, "R07-09"), (10, 12, "R10-12"))


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


def band_rank(rank: int) -> str:
    for lo, hi, label in RANK_BANDS:
        if lo <= rank <= hi:
            return label
    return "other"


def band_odds(odds: float) -> str:
    for lo, hi, label in ODDS_BANDS:
        if lo <= odds < hi:
            return label
    return "other"


def race_group(rno: int) -> str:
    for lo, hi, label in RACE_GROUPS:
        if lo <= rno <= hi:
            return label
    return "other"


def disagreement(prob_rank: int, market_rank: int) -> str:
    gap = market_rank - prob_rank
    if gap >= 20:
        return "MODEL_AHEAD_20P"
    if gap >= 10:
        return "MODEL_AHEAD_10P"
    if gap >= 5:
        return "MODEL_AHEAD_5P"
    if gap <= -20:
        return "MARKET_AHEAD_20P"
    if gap <= -10:
        return "MARKET_AHEAD_10P"
    if gap <= -5:
        return "MARKET_AHEAD_5P"
    return "ALIGNED_4P"


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    p = (len(xs) - 1) * q
    lo = math.floor(p)
    hi = math.ceil(p)
    if lo == hi:
        return round(xs[lo], 4)
    w = p - lo
    return round(xs[lo] * (1.0 - w) + xs[hi] * w, 4)


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if END_DATE < START_DATE:
        raise RuntimeError("END_DATE must be >= START_DATE")

    print("VALUE_GEOMETRY_MODE=outcome_blind_count_only", flush=True)
    print(f"VALUE_GEOMETRY_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_GEOMETRY_SOURCE=complete_predeadline_final_ab_120", flush=True)
    print("VALUE_GEOMETRY_RESULTS_READ=0 ROI_CALCULATED=0 DB_WRITE=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute(
                """
                with races as (
                  select race_id,race_date,
                         coalesce(nullif(venue_id,''),nullif(venue_code,'')) as venue_id,
                         race_no,deadline_at
                    from v2_races
                   where race_date between %s and %s
                     and deadline_at is not null
                ), grouped as (
                  select r.race_id,r.race_date,r.venue_id,r.race_no,r.deadline_at,
                         count(*)::bigint row_count,
                         count(distinct o.ticket)::bigint ticket_count,
                         count(*) filter(where o.odds is not null and o.odds>1.0)::bigint positive_count,
                         min(o.snapshot_at) first_snapshot_at,
                         max(o.snapshot_at) last_snapshot_at
                    from races r
                    join v2_realtime_odds_snapshots o on o.race_id=r.race_id
                   where o.snapshot_label='final_ab'
                   group by r.race_id,r.race_date,r.venue_id,r.race_no,r.deadline_at
                ), valid as (
                  select *,extract(epoch from(last_snapshot_at-first_snapshot_at)) spread_seconds
                    from grouped
                   where row_count=120
                     and ticket_count=120
                     and positive_count=120
                     and last_snapshot_at<=deadline_at
                     and extract(epoch from(last_snapshot_at-first_snapshot_at))<=%s
                )
                select v.*,o.ticket,o.odds,
                       (select count(*)::bigint from races) total_races,
                       (select count(*)::bigint from grouped) final_ab_races
                  from valid v
                  join v2_realtime_odds_snapshots o
                    on o.race_id=v.race_id and o.snapshot_label='final_ab'
                 order by v.race_date,v.race_id,o.ticket
                """,
                (START_DATE, END_DATE, MAX_SPREAD_SECONDS),
            )
            rows = [dict(r) for r in cur.fetchall()]

            meta: dict[str, dict[str, Any]] = {}
            odds_by: dict[str, dict[str, float]] = defaultdict(dict)
            total_races = final_ab_races = 0
            for row in rows:
                rid = str(row.get("race_id") or "")
                if not rid:
                    continue
                total_races = max(total_races, si(row.get("total_races")))
                final_ab_races = max(final_ab_races, si(row.get("final_ab_races")))
                meta.setdefault(rid, {k: row.get(k) for k in ("race_id", "race_date", "venue_id", "race_no", "deadline_at", "last_snapshot_at")})
                ticket = v24._norm_ticket(row.get("ticket"))
                odd = sf(row.get("odds"))
                if ticket and odd > 1.0:
                    odds_by[rid][ticket] = odd

            race_ids = sorted(meta)
            entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if race_ids:
                cur.execute(
                    """select race_id,lane,racer_number,racer_class,racer_name,
                              national_win_rate,national_place2_rate,
                              local_win_rate,local_place2_rate,
                              motor_no,boat_no,avg_st
                         from v2_race_entries
                        where race_id=any(%s)
                        order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries_by[str(row["race_id"])].append(dict(row))
        conn.rollback()

    ticket_cells: Counter[str] = Counter()
    race_cells: dict[str, set[str]] = defaultdict(set)
    family_cells: dict[str, set[str]] = defaultdict(set)
    family_ticket_counts: Counter[str] = Counter()
    gaps: list[float] = []
    ready_races = 0

    for rid, m in sorted(meta.items(), key=lambda x: (str(x[1].get("race_date")), x[0])):
        odds = odds_by.get(rid, {})
        entries = entries_by.get(rid, [])
        if len(odds) != 120 or len(v24._entry_by_lane(entries)) != 6:
            continue
        ready_races += 1
        deadline = m.get("deadline_at")
        last = m.get("last_snapshot_at")
        if deadline is not None and last is not None:
            gaps.append((deadline - last).total_seconds() / 60.0)
        venue = str(m.get("venue_id") or "").zfill(2)
        rgroup = race_group(si(m.get("race_no")))
        ranked = v24._rank_candidates(entries, venue, odds)
        for item in ranked:
            pr = si(item.get("prob_rank"), 999)
            mr = si(item.get("market_rank"), 999)
            odd = sf(item.get("odds"))
            pb = band_rank(pr)
            mb = band_rank(mr)
            ob = band_odds(odd)
            cell = f"pr={pb}|mr={mb}|odds={ob}|race={rgroup}"
            ticket_cells[cell] += 1
            race_cells[cell].add(rid)
            fam = disagreement(pr, mr)
            fcell = f"family={fam}|odds={ob}|race={rgroup}"
            family_ticket_counts[fcell] += 1
            family_cells[fcell].add(rid)

    days = (END_DATE - START_DATE).days + 1
    cell_rows = [
        {
            "cell": cell,
            "ticket_count": ticket_cells[cell],
            "race_count": len(races),
            "race_count_per_30d": round(len(races) / days * 30.0, 4),
        }
        for cell, races in race_cells.items()
    ]
    cell_rows.sort(key=lambda x: (-x["race_count"], -x["ticket_count"], x["cell"]))

    family_rows = [
        {
            "cell": cell,
            "ticket_count": family_ticket_counts[cell],
            "race_count": len(races),
            "race_count_per_30d": round(len(races) / days * 30.0, 4),
        }
        for cell, races in family_cells.items()
    ]
    family_rows.sort(key=lambda x: (-x["race_count"], -x["ticket_count"], x["cell"]))

    audit = {
        "total_races_with_deadline": total_races,
        "races_with_final_ab_rows": final_ab_races,
        "complete_predeadline_final_ab_races": len(meta),
        "entry_and_odds_ready_races": ready_races,
        "calendar_days": days,
    }
    timing = {
        "n": len(gaps),
        "min": round(min(gaps), 4) if gaps else None,
        "p05": percentile(gaps, 0.05),
        "median": percentile(gaps, 0.50),
        "p95": percentile(gaps, 0.95),
        "max": round(max(gaps), 4) if gaps else None,
    }
    out = {
        "contract": "final_ab_candidate_geometry_count_only_v1",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "audit": audit,
        "minutes_to_deadline": timing,
        "rank_odds_race_cells": cell_rows,
        "disagreement_family_cells": family_rows,
        "outcomes_read": False,
        "roi_calculated": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("VALUE_GEOMETRY_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    print("VALUE_GEOMETRY_TIMING=" + json.dumps(timing, sort_keys=True), flush=True)
    for row in family_rows[:30]:
        print(f"VALUE_GEOMETRY_FAMILY={row['cell']} races:{row['race_count']} per30d:{row['race_count_per_30d']} tickets:{row['ticket_count']}", flush=True)
    for row in cell_rows[:30]:
        print(f"VALUE_GEOMETRY_CELL={row['cell']} races:{row['race_count']} per30d:{row['race_count_per_30d']} tickets:{row['ticket_count']}", flush=True)
    print("VALUE_GEOMETRY_OUTCOMES_READ=0", flush=True)
    print("VALUE_GEOMETRY_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_GEOMETRY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
