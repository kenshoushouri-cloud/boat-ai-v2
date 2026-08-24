# -*- coding: utf-8 -*-
"""Read-only planner for the opt-in repeated base-odds refresh runner."""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

import run_odds_window_pg as odds

JST = timezone(timedelta(hours=9))
DB = (os.getenv("DATABASE_URL") or "").strip()
TARGET_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
VALID_WINDOWS = ("morning", "day", "night")


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    return default if not raw else float(raw)


def _clock_at(date_str: str, hhmm: str) -> datetime:
    return datetime.strptime(f"{date_str} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def _deadline_at(row: Dict[str, Any]) -> Optional[datetime]:
    value = row.get("deadline_at")
    if isinstance(value, datetime):
        return value.replace(tzinfo=JST) if value.tzinfo is None else value.astimezone(JST)
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed.astimezone(JST)
        except Exception:
            pass
    clock = str(row.get("deadline_time") or "")[:5]
    if not clock:
        return None
    try:
        return _clock_at(TARGET_DATE, clock)
    except Exception:
        return None


def _active_windows(now_jst: datetime) -> List[str]:
    prewarm = max(0.0, _env_float("WINDOW_REFRESH_PREWARM_MIN", 15.0))
    active: List[str] = []
    for name in VALID_WINDOWS:
        start, end = odds.WINDOW_PRESETS[name]
        active_start = _clock_at(TARGET_DATE, start) - timedelta(minutes=prewarm)
        active_end = (
            _clock_at(TARGET_DATE, end)
            if end
            else _clock_at(TARGET_DATE, "23:59") + timedelta(minutes=1)
        )
        if active_start <= now_jst < active_end:
            active.append(name)
    return active


def _in_window(row: Dict[str, Any], name: str) -> bool:
    clock = str(row.get("deadline_time") or "")[:5]
    if not clock:
        return False
    start, end = odds.WINDOW_PRESETS[name]
    if end:
        return start <= clock < end
    return clock >= start


def _sample(values: List[str], limit: int = 20) -> tuple[str, int]:
    shown = values[:limit]
    return (",".join(shown) if shown else "none", max(0, len(values) - len(shown)))


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    now_jst = datetime.now(JST)
    today = now_jst.strftime("%Y-%m-%d")
    min_before = max(0.0, _env_float("WINDOW_REFRESH_MIN_MINUTES_BEFORE_DEADLINE", 10.0))
    max_before = max(min_before, _env_float("WINDOW_REFRESH_MAX_MINUTES_BEFORE_DEADLINE", 90.0))
    active = _active_windows(now_jst)

    print("WINDOW_REFRESH_PLAN_MODE=read_only", flush=True)
    print("WINDOW_REFRESH_PLAN_POLICY=no_writes_no_pre_no_line_no_final_no_promotion", flush=True)
    print(f"WINDOW_REFRESH_PLAN_DATE={TARGET_DATE}", flush=True)
    print(f"WINDOW_REFRESH_PLAN_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print(
        "WINDOW_REFRESH_PLAN_SCOPE="
        f"active_windows:{','.join(active) if active else 'none'} "
        f"min_before:{min_before:.1f} max_before:{max_before:.1f}",
        flush=True,
    )

    if TARGET_DATE != today:
        print(f"WINDOW_REFRESH_PLAN_RESULT=BLOCKED_NONLIVE_DATE today:{today}", flush=True)
        return
    if not active:
        print("WINDOW_REFRESH_PLAN_COUNTS=eligible:0 complete:0 incomplete:0", flush=True)
        print("WINDOW_REFRESH_PLAN_RESULT=PASS_READ_ONLY", flush=True)
        return

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select race_id, coalesce(venue_id,venue_code) venue_id, race_no,
                       deadline_time, deadline_at
                from v2_races
                where race_date=%s
                order by deadline_time, venue_id, race_no
                """,
                (TARGET_DATE,),
            )
            races = [dict(row) for row in cur.fetchall()]

        eligible: List[Dict[str, Any]] = []
        memberships: Dict[str, List[str]] = {}
        for row in races:
            deadline = _deadline_at(row)
            if deadline is None:
                continue
            minutes_before = (deadline - now_jst).total_seconds() / 60.0
            if not (min_before <= minutes_before <= max_before):
                continue
            names = [name for name in active if _in_window(row, name)]
            if not names:
                continue
            rid = str(row.get("race_id") or "")
            if not rid:
                continue
            row["minutes_before"] = minutes_before
            eligible.append(row)
            memberships[rid] = names

        race_ids = [str(row["race_id"]) for row in eligible]
        tickets_by: Dict[str, List[str]] = defaultdict(list)
        if race_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select race_id,ticket
                    from v2_odds_trifecta
                    where race_id=any(%s)
                    order by race_id,ticket
                    """,
                    (race_ids,),
                )
                for row in cur.fetchall():
                    tickets_by[str(row["race_id"])].append(str(row.get("ticket") or ""))

    complete: List[str] = []
    incomplete: List[str] = []
    incomplete_by_window: Dict[str, List[str]] = {name: [] for name in active}
    eligible_by_window: Dict[str, int] = {name: 0 for name in active}

    for row in eligible:
        rid = str(row["race_id"])
        status = odds._evaluate_ticket_snapshot(tickets_by.get(rid, []))
        label = f"{rid}@{str(row.get('deadline_time') or '')[:5]}"
        for name in memberships.get(rid, []):
            eligible_by_window[name] += 1
        if status.get("complete"):
            complete.append(label)
            continue
        incomplete.append(label)
        for name in memberships.get(rid, []):
            incomplete_by_window[name].append(label)

    print(
        f"WINDOW_REFRESH_PLAN_COUNTS=eligible:{len(eligible)} "
        f"complete:{len(complete)} incomplete:{len(incomplete)}",
        flush=True,
    )
    for name in active:
        sample, more = _sample(incomplete_by_window[name])
        print(
            f"WINDOW_REFRESH_PLAN_WINDOW=name:{name} eligible:{eligible_by_window[name]} "
            f"incomplete:{len(incomplete_by_window[name])} races:{sample} more:{more}",
            flush=True,
        )
    sample, more = _sample(incomplete)
    print(
        f"WINDOW_REFRESH_PLAN_INCOMPLETE=count:{len(incomplete)} races:{sample} more:{more}",
        flush=True,
    )
    print(
        "WINDOW_REFRESH_PLAN_FETCH_BUDGET="
        f"initial_race_fetches:{len(incomplete)} "
        f"max_with_default_one_retry:{len(incomplete) * 2}",
        flush=True,
    )
    print("WINDOW_REFRESH_PLAN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
