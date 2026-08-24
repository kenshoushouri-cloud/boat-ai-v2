# -*- coding: utf-8 -*-
"""Read-only operational health snapshot for the current JST race day.

Checks production-data coverage only. No DB writes, no Production decision changes,
and no LINE operations.
"""
from __future__ import annotations

import itertools
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
DB = (os.getenv("DATABASE_URL") or "").strip()
TARGET_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
ALL_LANES = {1, 2, 3, 4, 5, 6}


def _ticket(raw: object) -> str:
    text = str(raw or "").strip()
    parts = text.split("-")
    if len(parts) != 3 or any(not p.isdigit() for p in parts):
        return ""
    lanes = [int(p) for p in parts]
    if any(x not in ALL_LANES for x in lanes) or len(set(lanes)) != 3:
        return ""
    return "-".join(str(x) for x in lanes)


def _odds_complete(tickets: list[str]) -> bool:
    actual = {_ticket(x) for x in tickets}
    actual.discard("")
    if not actual:
        return False
    active = {int(p) for t in actual for p in t.split("-")}
    if not 4 <= len(active) <= 6:
        return False
    expected = {
        f"{a}-{b}-{c}"
        for a, b, c in itertools.permutations(sorted(active), 3)
    }
    return actual == expected


def _in_window(deadline: str, name: str) -> bool:
    value = (deadline or "")[:5]
    if not value:
        return False
    if name == "morning":
        return "08:30" <= value < "10:15"
    if name == "day":
        return "09:45" <= value < "15:00"
    if name == "night":
        return value >= "14:45"
    return False


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    print(f"TODAY_HEALTH_DATE={TARGET_DATE}", flush=True)
    print("TODAY_HEALTH_POLICY=read_only_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select race_id, coalesce(venue_id, venue_code) venue_id, race_no,
                       deadline_time, deadline_at
                from v2_races
                where race_date=%s
                order by deadline_time nulls last, venue_id, race_no
                """,
                (TARGET_DATE,),
            )
            races = [dict(x) for x in cur.fetchall()]

        race_ids = [str(x["race_id"]) for x in races]
        entries_by: dict[str, set[int]] = defaultdict(set)
        odds_by: dict[str, list[str]] = defaultdict(list)
        results: set[str] = set()

        if race_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """select race_id,lane from v2_race_entries
                       where race_id=any(%s) order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    lane = row.get("lane")
                    if lane is not None:
                        entries_by[str(row["race_id"])].add(int(lane))

                cur.execute(
                    """select race_id,ticket from v2_odds_trifecta
                       where race_id=any(%s) order by race_id,ticket""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    odds_by[str(row["race_id"])].append(str(row.get("ticket") or ""))

                cur.execute(
                    "select race_id from v2_results where race_id=any(%s)",
                    (race_ids,),
                )
                results = {str(x["race_id"]) for x in cur.fetchall()}

        deadline_ready = sum(1 for r in races if r.get("deadline_time") or r.get("deadline_at"))
        entries_full = sum(1 for rid in race_ids if entries_by.get(rid) == ALL_LANES)
        odds_races = sum(1 for rid in race_ids if odds_by.get(rid))
        odds_complete = sum(1 for rid in race_ids if _odds_complete(odds_by.get(rid, [])))
        entry_rows = sum(len(v) for v in entries_by.values())
        odds_rows = sum(len(v) for v in odds_by.values())

        print(
            f"TODAY_HEALTH_RACES=total:{len(races)} deadline_ready:{deadline_ready}",
            flush=True,
        )
        print(
            f"TODAY_HEALTH_ENTRIES=rows:{entry_rows} races:{len(entries_by)} full6:{entries_full}",
            flush=True,
        )
        print(
            f"TODAY_HEALTH_ODDS=rows:{odds_rows} races:{odds_races} exact_dynamic_complete:{odds_complete}",
            flush=True,
        )
        print(f"TODAY_HEALTH_RESULTS=races:{len(results)}", flush=True)

        for name in ("morning", "day", "night"):
            selected = [
                r for r in races
                if _in_window(str(r.get("deadline_time") or ""), name)
            ]
            ids = [str(r["race_id"]) for r in selected]
            full6 = sum(1 for rid in ids if entries_by.get(rid) == ALL_LANES)
            complete = sum(1 for rid in ids if _odds_complete(odds_by.get(rid, [])))
            print(
                f"TODAY_HEALTH_WINDOW=name:{name} races:{len(ids)} entries_full6:{full6} odds_complete:{complete}",
                flush=True,
            )

    print("TODAY_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
