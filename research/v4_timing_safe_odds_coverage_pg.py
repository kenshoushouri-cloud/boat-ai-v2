# -*- coding: utf-8 -*-
"""Read-only odds coverage ladder for current V4 selected races.

No outcomes or payouts are read. The purpose is only to diagnose where timing-
safe odds coverage disappears: any row, complete 120, predeadline, or fixed
predeadline margins.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4
from research import v4_long_history_walkforward_pg as hist

START_DATE = date.fromisoformat(os.getenv("V4_ODDS_COVERAGE_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("V4_ODDS_COVERAGE_END", "2026-09-22"))
MAX_SPREAD_SECONDS = float(os.getenv("V4_ODDS_COVERAGE_MAX_SPREAD_SECONDS", "60"))
OUTPUT = Path(os.getenv("V4_ODDS_COVERAGE_OUTPUT", "v4-odds-coverage-ladder.json"))
MARGINS = (0, 5, 10, 15)


def selected_ids_for_day(cur: psycopg.Cursor[Any], day: date) -> list[str]:
    races, entries_by, course_by, opponent_by = hist.fetch_day_inputs(cur, day)
    cutoff = hist.cutoff_for(day)
    distributions: dict[str, dict[str, float]] = {}
    for race in races:
        rid = str(race.get("race_id") or "")
        entries = entries_by.get(rid, [])
        deadline = hist.aware_jst(race.get("deadline_at"))
        if len(entries) != 6 or deadline is None:
            continue
        venue = str(race.get("venue_id") or "").zfill(2)
        try:
            base = hist.base_raw(entries, venue)
        except Exception:
            continue
        course = hist.course_map(
            entries=entries,
            deadline=deadline,
            cutoff=cutoff,
            course_by=course_by,
        )
        opponent = hist.opponent_delta(
            row=opponent_by.get(rid),
            race_day=day,
            deadline=deadline,
            cutoff=cutoff,
        )
        motor = hist.motor_map(entries)
        distributions[rid] = v4.build_v4_distribution(
            base_raw=base,
            course_top3=course,
            motor_place2=motor,
            opponent_delta=opponent,
        )
    selected = v4.select_daily(
        distributions,
        race_cap=v4.CORE_RACES,
        ticket_count=v4.CORE_TICKETS,
    )
    return [str(row["race_id"]) for row in selected]


def coverage_for_ids(
    cur: psycopg.Cursor[Any],
    race_ids: list[str],
) -> dict[str, Any]:
    if not race_ids:
        return {}
    cur.execute(
        """
        with target as (
          select r.race_id,r.race_date,r.deadline_at
            from v2_races r
           where r.race_id=any(%s)
        ), grouped as (
          select t.race_id,t.race_date,t.deadline_at,o.snapshot_label,
                 count(*)::bigint as row_count,
                 count(distinct o.ticket)::bigint as ticket_count,
                 count(*) filter (
                   where o.odds is not null and o.odds > 1.0
                 )::bigint as positive_count,
                 min(o.snapshot_at) as first_at,
                 max(o.snapshot_at) as last_at
            from target t
            left join v2_realtime_odds_snapshots o
              on o.race_id=t.race_id
           group by t.race_id,t.race_date,t.deadline_at,o.snapshot_label
        )
        select race_id,race_date,deadline_at,snapshot_label,row_count,ticket_count,
               positive_count,first_at,last_at,
               case
                 when first_at is not null and last_at is not null
                 then extract(epoch from (last_at-first_at))
                 else null
               end as spread_seconds
          from grouped
         order by race_id,last_at nulls first,snapshot_label
        """,
        (race_ids,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    by_race: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_race.setdefault(str(row["race_id"]), []).append(row)

    labels: Counter[str] = Counter()
    result: dict[str, Any] = {}
    for rid in race_ids:
        groups = by_race.get(rid, [])
        any_rows = any(int(row.get("row_count") or 0) > 0 for row in groups)
        complete_any = False
        complete_coherent = False
        margin_ok = {margin: False for margin in MARGINS}
        best_last = None
        for row in groups:
            label = str(row.get("snapshot_label") or "<none>")
            if label != "<none>":
                labels[label] += 1
            row_count = int(row.get("row_count") or 0)
            ticket_count = int(row.get("ticket_count") or 0)
            positive = int(row.get("positive_count") or 0)
            spread = row.get("spread_seconds")
            deadline = hist.aware_jst(row.get("deadline_at"))
            last_at = hist.aware_jst(row.get("last_at"))
            complete = (
                row_count == 120
                and ticket_count == 120
                and positive == 120
            )
            if complete:
                complete_any = True
            coherent = (
                complete
                and spread is not None
                and float(spread) <= MAX_SPREAD_SECONDS
            )
            if coherent:
                complete_coherent = True
            if coherent and deadline is not None and last_at is not None:
                if best_last is None or last_at > best_last:
                    best_last = last_at
                for margin in MARGINS:
                    if last_at <= deadline - __import__("datetime").timedelta(minutes=margin):
                        margin_ok[margin] = True

        result[rid] = {
            "any_rows": any_rows,
            "complete_120_any_time": complete_any,
            "complete_120_coherent": complete_coherent,
            **{
                f"complete_by_deadline_minus_{margin}m": margin_ok[margin]
                for margin in MARGINS
            },
        }
    return {
        "races": result,
        "labels_seen": dict(sorted(labels.items())),
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V4_ODDS_COVERAGE_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print(
        "V4_ODDS_COVERAGE_MODE=READ_ONLY_NO_RESULTS_NO_PAYOUTS_NO_BUY",
        flush=True,
    )

    selected_by_date: dict[str, list[str]] = {}
    all_ids: list[str] = []
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='10min'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            for day in hist.daterange(START_DATE, END_DATE):
                ids = selected_ids_for_day(cur, day)
                selected_by_date[day.isoformat()] = ids
                all_ids.extend(ids)
            coverage = coverage_for_ids(cur, all_ids)
            conn.rollback()

    race_cov = coverage.get("races", {})
    keys = [
        "any_rows",
        "complete_120_any_time",
        "complete_120_coherent",
        "complete_by_deadline_minus_0m",
        "complete_by_deadline_minus_5m",
        "complete_by_deadline_minus_10m",
        "complete_by_deadline_minus_15m",
    ]
    counts = {
        key: sum(1 for row in race_cov.values() if bool(row.get(key)))
        for key in keys
    }
    by_date = {}
    for day, ids in selected_by_date.items():
        by_date[day] = {
            "selected": len(ids),
            **{
                key: sum(
                    1
                    for rid in ids
                    if bool(race_cov.get(rid, {}).get(key))
                )
                for key in keys
            },
        }

    selected_total = len(all_ids)
    out = {
        "contract": "v4_odds_coverage_ladder_v1",
        "period": {
            "start": START_DATE.isoformat(),
            "end": END_DATE.isoformat(),
        },
        "selected_races": selected_total,
        "counts": counts,
        "percent": {
            key: round(count / selected_total * 100.0, 3)
            if selected_total else 0.0
            for key, count in counts.items()
        },
        "labels_seen": coverage.get("labels_seen", {}),
        "by_date": by_date,
        "result_read": False,
        "payout_read": False,
        "mutation_performed": False,
        "purchase_action": False,
    }
    OUTPUT.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("V4_ODDS_COVERAGE_COUNTS=" + json.dumps(counts, sort_keys=True), flush=True)
    print("V4_ODDS_COVERAGE_PERCENT=" + json.dumps(out["percent"], sort_keys=True), flush=True)
    print("V4_ODDS_COVERAGE_LABELS=" + json.dumps(out["labels_seen"], sort_keys=True), flush=True)
    print("RESULT=PASS_READ_ONLY_ODDS_COVERAGE_LADDER", flush=True)


if __name__ == "__main__":
    main()
