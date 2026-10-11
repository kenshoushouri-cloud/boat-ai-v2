# -*- coding: utf-8 -*-
"""Read-only historical readiness audit for V5.1 Exhibition Time.

Purpose
-------
Measure result-blind coverage and historical provenance of official BOAT RACE
beforeinfo exhibition-time rows for 2025-07-01..2026-09-30.

Historical timing rule
----------------------
Official archived target-race beforeinfo is accepted as
PREDEADLINE_BY_NATURE for historical research under
docs/HISTORICAL_SOURCE_POLICY_20260930.md. Retrieval/snapshot timestamps may be
synthetic or later than the race; they are NOT prospective timing evidence.

No outcomes, payouts, odds, or database writes are read/performed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

CONTRACT = "V51_EXHIBITION_TIME_HISTORICAL_READINESS_V1"
EXPLICIT_SOURCE_CONTRACT = "BOATRACE_OFFICIAL_ARCHIVED_BEFOREINFO_PREDEADLINE_ASSUMED_V1"
ACCEPTED_SOURCES = {
    "official_archived_beforeinfo_historical_reconstruction",
    "official_beforeinfo_historical",
    "official_beforeinfo_historical_v3_pilot",
}
START_DEFAULT = date(2025, 7, 1)
END_DEFAULT = date(2026, 9, 30)
LANES = {1, 2, 3, 4, 5, 6}

SPLITS = (
    ("TRAIN_REFERENCE", date(2025, 7, 1), date(2025, 12, 31)),
    ("VALIDATION", date(2026, 1, 1), date(2026, 6, 30)),
    ("OOS", date(2026, 7, 1), date(2026, 9, 30)),
)


def split_name(d: date) -> str:
    for name, start, end in SPLITS:
        if start <= d <= end:
            return name
    return "OUTSIDE"


def _finite_time(v: Any) -> bool:
    try:
        x = float(v)
    except Exception:
        return False
    # Exhibition times are around 6 seconds; broad bounds are intentionally
    # conservative and only reject obviously corrupt values.
    return math.isfinite(x) and 1.0 <= x <= 20.0


def load_rows(
    conn: psycopg.Connection[Any],
    start_date: date,
    end_date: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.race_id,r.race_date,
                   count(e.*)::int as entry_rows,
                   count(distinct e.lane)::int as entry_lanes,
                   count(*) filter(
                       where e.lane between 1 and 6
                         and e.motor_place2_rate between 0 and 100
                   )::int as motor2_valid_entries
              from v2_races r
              left join v2_race_entries e on e.race_id=r.race_id
             where r.race_date between %s and %s
             group by r.race_id,r.race_date
             order by r.race_date,r.race_id
            """,
            (start_date, end_date),
        )
        races = [dict(x) for x in cur.fetchall()]

        cur.execute(
            """
            select x.race_id,x.race_date,x.lane,x.snapshot_label,x.snapshot_at,
                   x.source,x.exhibition_time,x.exhibition_time_rank,
                   x.exhibition_time_diff,x.raw
              from v2_realtime_exhibition_snapshots x
             where x.race_date between %s and %s
               and x.snapshot_label='historical'
             order by x.race_date,x.race_id,x.lane
            """,
            (start_date, end_date),
        )
        ex = [dict(x) for x in cur.fetchall()]
    return races, ex


def explicit_contract(row: dict[str, Any]) -> bool:
    raw = row.get("raw")
    return (
        isinstance(raw, dict)
        and raw.get("source_contract") == EXPLICIT_SOURCE_CONTRACT
        and raw.get("historical_reconstruction") is True
        and raw.get("prospective_evidence") is False
        and raw.get("timing_policy")
        == "archived_target_race_beforeinfo_treated_as_predeadline"
    )


def provenance_class(row: dict[str, Any]) -> str:
    source = str(row.get("source") or "")
    if explicit_contract(row):
        return "explicit_official_predeadline_by_nature"
    if source in ACCEPTED_SOURCES:
        return "legacy_official_predeadline_by_nature"
    return "unaccepted_or_unknown"


def summarize(
    races: list[dict[str, Any]],
    ex_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ex_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_rows: Counter[str] = Counter()
    provenance_rows: Counter[str] = Counter()
    for row in ex_rows:
        rid = str(row["race_id"])
        ex_by_race[rid].append(row)
        source_rows[str(row.get("source") or "<NULL>")] += 1
        provenance_rows[provenance_class(row)] += 1

    counters: Counter[str] = Counter()
    split_counts: dict[str, Counter[str]] = {
        name: Counter() for name, _, _ in SPLITS
    }
    source_races: dict[str, set[str]] = defaultdict(set)

    for race in races:
        rid = str(race["race_id"])
        rd = race["race_date"]
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        split = split_name(rd)
        sc = split_counts[split]

        exact6 = (
            int(race["entry_rows"]) == 6
            and int(race["entry_lanes"]) == 6
        )
        motor6 = exact6 and int(race["motor2_valid_entries"]) == 6

        rows = ex_by_race.get(rid, [])
        accepted = [
            row for row in rows
            if provenance_class(row)
            in {
                "explicit_official_predeadline_by_nature",
                "legacy_official_predeadline_by_nature",
            }
        ]
        accepted_by_lane: dict[int, dict[str, Any]] = {}
        duplicate_lane = False
        for row in accepted:
            lane = int(row.get("lane") or 0)
            if lane not in LANES:
                continue
            if lane in accepted_by_lane:
                duplicate_lane = True
            accepted_by_lane[lane] = row

        valid_time_lanes = {
            lane for lane, row in accepted_by_lane.items()
            if _finite_time(row.get("exhibition_time"))
        }
        time6 = valid_time_lanes == LANES
        rank6 = time6 and all(
            row.get("exhibition_time_rank") is not None
            for row in accepted_by_lane.values()
        )
        diff6 = time6 and all(
            row.get("exhibition_time_diff") is not None
            for row in accepted_by_lane.values()
        )
        shared_time6 = motor6 and time6

        counters["races"] += 1
        counters["exact6_races"] += int(exact6)
        counters["motor2_complete_races"] += int(motor6)
        counters["historical_snapshot_races"] += int(bool(rows))
        counters["accepted_provenance_races"] += int(bool(accepted))
        counters["exhibition_time6_races"] += int(time6)
        counters["shared_motor2_exhibition_time6_races"] += int(shared_time6)
        counters["rank6_races"] += int(rank6)
        counters["diff6_races"] += int(diff6)
        counters["duplicate_lane_races"] += int(duplicate_lane)
        counters["accepted_rows"] += len(accepted)
        counters["valid_time_rows"] += len(valid_time_lanes)

        sc["races"] += 1
        sc["exact6_races"] += int(exact6)
        sc["motor2_complete_races"] += int(motor6)
        sc["exhibition_time6_races"] += int(time6)
        sc["shared_motor2_exhibition_time6_races"] += int(shared_time6)

        for row in rows:
            source_races[str(row.get("source") or "<NULL>")].add(rid)

    exact6 = counters["exact6_races"]
    motor6 = counters["motor2_complete_races"]
    counters_out: dict[str, Any] = dict(sorted(counters.items()))
    counters_out["exhibition_time6_pct_of_exact6"] = (
        round(100.0 * counters["exhibition_time6_races"] / exact6, 4)
        if exact6 else None
    )
    counters_out["shared_exhibition_time6_pct_of_motor2_complete"] = (
        round(
            100.0
            * counters["shared_motor2_exhibition_time6_races"]
            / motor6,
            4,
        )
        if motor6 else None
    )

    splits: dict[str, dict[str, Any]] = {}
    for name, _, _ in SPLITS:
        c = split_counts[name]
        split_out: dict[str, Any] = dict(sorted(c.items()))
        e6 = c["exact6_races"]
        m6 = c["motor2_complete_races"]
        split_out["exhibition_time6_pct_of_exact6"] = (
            round(100.0 * c["exhibition_time6_races"] / e6, 4)
            if e6 else None
        )
        split_out["shared_exhibition_time6_pct_of_motor2_complete"] = (
            round(
                100.0 * c["shared_motor2_exhibition_time6_races"] / m6,
                4,
            )
            if m6 else None
        )
        splits[name] = split_out

    source_breakdown = {
        source: {
            "rows": count,
            "distinct_races": len(source_races[source]),
            "accepted_by_policy": source in ACCEPTED_SOURCES,
        }
        for source, count in sorted(source_rows.items())
    }

    return {
        "overall": counters_out,
        "by_split": splits,
        "source_breakdown": source_breakdown,
        "provenance_row_breakdown": dict(sorted(provenance_rows.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=START_DEFAULT.isoformat())
    ap.add_argument("--end-date", default=END_DEFAULT.isoformat())
    ap.add_argument(
        "--output",
        default="v51-exhibition-time-historical-readiness.json",
    )
    args = ap.parse_args()

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    if start != START_DEFAULT or end != END_DEFAULT:
        raise RuntimeError("audit period is frozen to 2025-07-01..2026-09-30")

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V51_EX_TIME_READINESS_CONTRACT={CONTRACT}", flush=True)
    print(
        "V51_EX_TIME_READINESS_HISTORICAL_TIMING="
        "PREDEADLINE_BY_NATURE_NOT_PROSPECTIVE_TIMESTAMP",
        flush=True,
    )
    print("V51_EX_TIME_READINESS_RESULT_READ=0", flush=True)
    print("V51_EX_TIME_READINESS_ODDS_READ=0", flush=True)
    print("V51_EX_TIME_READINESS_PAYOUT_READ=0", flush=True)
    print("V51_EX_TIME_READINESS_DB_WRITE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        races, ex_rows = load_rows(conn, start, end)
        conn.rollback()

    report = summarize(races, ex_rows)
    payload = {
        "contract": CONTRACT,
        "candidate": "V51_EXHIBITION_TIME",
        "period": [start.isoformat(), end.isoformat()],
        "historical_source_policy": "PREDEADLINE_BY_NATURE",
        "exact_original_fetch_timestamp_required": False,
        "prospective_evidence": False,
        "accepted_sources": sorted(ACCEPTED_SOURCES),
        "explicit_source_contract": EXPLICIT_SOURCE_CONTRACT,
        **report,
        "result_read": False,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
    }

    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "V51_EX_TIME_READINESS_OVERALL="
        + json.dumps(payload["overall"], sort_keys=True),
        flush=True,
    )
    for name, row in payload["by_split"].items():
        print(
            "V51_EX_TIME_READINESS_SPLIT="
            + json.dumps({"split": name, **row}, sort_keys=True),
            flush=True,
        )
    print(
        "V51_EX_TIME_READINESS_SOURCES="
        + json.dumps(payload["source_breakdown"], sort_keys=True),
        flush=True,
    )
    print(
        "V51_EX_TIME_READINESS_PROVENANCE_ROWS="
        + json.dumps(payload["provenance_row_breakdown"], sort_keys=True),
        flush=True,
    )

    unknown = payload["provenance_row_breakdown"].get(
        "unaccepted_or_unknown", 0
    )
    print(f"V51_EX_TIME_READINESS_UNKNOWN_ROWS={unknown}", flush=True)
    print("V51_EX_TIME_READINESS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
