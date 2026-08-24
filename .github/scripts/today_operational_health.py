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


def _deadline_jst(race: dict) -> datetime | None:
    value = race.get("deadline_at")
    if isinstance(value, datetime):
        return value.replace(tzinfo=JST) if value.tzinfo is None else value.astimezone(JST)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed.astimezone(JST)
        except Exception:
            pass
    deadline_time = str(race.get("deadline_time") or "")[:5]
    if not deadline_time:
        return None
    try:
        return datetime.strptime(
            f"{TARGET_DATE} {deadline_time}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=JST)
    except Exception:
        return None


def _sample(values: list[str], limit: int = 20) -> tuple[str, int]:
    shown = values[:limit]
    return (",".join(shown) if shown else "none", max(0, len(values) - len(shown)))


def _label(race: dict) -> str:
    return f"{race['race_id']}@{str(race.get('deadline_time') or '')[:5]}"


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    now_jst = datetime.now(JST)
    print(f"TODAY_HEALTH_DATE={TARGET_DATE}", flush=True)
    print(f"TODAY_HEALTH_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
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

        elapsed = [r for r in races if (_deadline_jst(r) is not None and _deadline_jst(r) <= now_jst)]
        upcoming = [r for r in races if (_deadline_jst(r) is not None and _deadline_jst(r) > now_jst)]
        elapsed_odds_complete = sum(
            1 for r in elapsed if _odds_complete(odds_by.get(str(r["race_id"]), []))
        )
        upcoming_odds_complete = sum(
            1 for r in upcoming if _odds_complete(odds_by.get(str(r["race_id"]), []))
        )

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
        print(
            f"TODAY_HEALTH_TIMING=elapsed:{len(elapsed)} elapsed_odds_complete:{elapsed_odds_complete} "
            f"upcoming:{len(upcoming)} upcoming_odds_complete:{upcoming_odds_complete}",
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
            selected_elapsed = [
                r for r in selected
                if _deadline_jst(r) is not None and _deadline_jst(r) <= now_jst
            ]
            selected_upcoming = [
                r for r in selected
                if _deadline_jst(r) is not None and _deadline_jst(r) > now_jst
            ]
            elapsed_complete = sum(
                1 for r in selected_elapsed
                if _odds_complete(odds_by.get(str(r["race_id"]), []))
            )
            upcoming_complete = sum(
                1 for r in selected_upcoming
                if _odds_complete(odds_by.get(str(r["race_id"]), []))
            )
            print(
                f"TODAY_HEALTH_WINDOW=name:{name} races:{len(ids)} entries_full6:{full6} odds_complete:{complete} "
                f"elapsed:{len(selected_elapsed)} elapsed_odds_complete:{elapsed_complete} "
                f"upcoming:{len(selected_upcoming)} upcoming_odds_complete:{upcoming_complete}",
                flush=True,
            )

            entry_missing = [
                _label(r)
                for r in selected
                if entries_by.get(str(r["race_id"])) != ALL_LANES
            ]
            odds_missing = [
                _label(r)
                for r in selected
                if not _odds_complete(odds_by.get(str(r["race_id"]), []))
            ]
            odds_missing_elapsed = [
                _label(r)
                for r in selected_elapsed
                if not _odds_complete(odds_by.get(str(r["race_id"]), []))
            ]
            odds_missing_upcoming = [
                _label(r)
                for r in selected_upcoming
                if not _odds_complete(odds_by.get(str(r["race_id"]), []))
            ]
            entry_sample, entry_more = _sample(entry_missing)
            odds_sample, odds_more = _sample(odds_missing)
            elapsed_sample, elapsed_more = _sample(odds_missing_elapsed)
            upcoming_sample, upcoming_more = _sample(odds_missing_upcoming)
            print(
                f"TODAY_HEALTH_WINDOW_INCOMPLETE=name:{name} "
                f"entries_missing:{len(entry_missing)} entry_races:{entry_sample} entry_more:{entry_more} "
                f"odds_missing:{len(odds_missing)} odds_races:{odds_sample} odds_more:{odds_more}",
                flush=True,
            )
            print(
                f"TODAY_HEALTH_WINDOW_TIMED_GAPS=name:{name} "
                f"elapsed_odds_missing:{len(odds_missing_elapsed)} elapsed_races:{elapsed_sample} elapsed_more:{elapsed_more} "
                f"upcoming_odds_missing:{len(odds_missing_upcoming)} upcoming_races:{upcoming_sample} upcoming_more:{upcoming_more}",
                flush=True,
            )

    print("TODAY_HEALTH_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
