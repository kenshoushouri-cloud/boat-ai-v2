# -*- coding: utf-8 -*-
"""Read-only live probe for currently incomplete base trifecta odds.

The probe selects upcoming races in the same default 10-60 minute refresh scope,
reads current v2_odds_trifecta completeness, then HTTP-GETs the official BOAT
RACE odds3t page and parses it with the exact parser used by the base collector.
It never calls any DB write helper.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

import repair_month_all_pg as repair
import run_odds_window_pg as odds

JST = timezone(timedelta(hours=9))
DB = (os.getenv("DATABASE_URL") or "").strip()
TARGET_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
MIN_BEFORE = float(os.getenv("WINDOW_REFRESH_MIN_MINUTES_BEFORE_DEADLINE", "10"))
MAX_BEFORE = float(os.getenv("WINDOW_REFRESH_MAX_MINUTES_BEFORE_DEADLINE", "60"))
LIMIT = max(1, min(20, int(os.getenv("WINDOW_REFRESH_PROBE_LIMIT", "10"))))
VALID_WINDOWS = ("morning", "day", "night")


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
    active: List[str] = []
    prewarm = 15.0
    for name in VALID_WINDOWS:
        start, end = odds.WINDOW_PRESETS[name]
        lo = _clock_at(TARGET_DATE, start) - timedelta(minutes=prewarm)
        hi = _clock_at(TARGET_DATE, end) if end else _clock_at(TARGET_DATE, "23:59") + timedelta(minutes=1)
        if lo <= now_jst < hi:
            active.append(name)
    return active


def _in_window(row: Dict[str, Any], name: str) -> bool:
    clock = str(row.get("deadline_time") or "")[:5]
    if not clock:
        return False
    start, end = odds.WINDOW_PRESETS[name]
    return start <= clock < end if end else clock >= start


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    now_jst = datetime.now(JST)
    today = now_jst.strftime("%Y-%m-%d")
    active = _active_windows(now_jst)

    print("WINDOW_REFRESH_PROBE_MODE=read_only_http_get", flush=True)
    print("WINDOW_REFRESH_PROBE_POLICY=no_db_writes_no_pre_no_line_no_final_no_promotion", flush=True)
    print(f"WINDOW_REFRESH_PROBE_DATE={TARGET_DATE}", flush=True)
    print(f"WINDOW_REFRESH_PROBE_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print(
        f"WINDOW_REFRESH_PROBE_SCOPE=active_windows:{','.join(active) if active else 'none'} "
        f"min_before:{MIN_BEFORE:.1f} max_before:{MAX_BEFORE:.1f} limit:{LIMIT}",
        flush=True,
    )

    if TARGET_DATE != today:
        print(f"WINDOW_REFRESH_PROBE_RESULT=BLOCKED_NONLIVE_DATE today:{today}", flush=True)
        return
    if not active:
        print("WINDOW_REFRESH_PROBE_COUNTS=eligible:0 incomplete:0 probed:0 would_complete:0", flush=True)
        print("WINDOW_REFRESH_PROBE_RESULT=PASS_READ_ONLY", flush=True)
        return

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select race_id, race_date, coalesce(venue_id,venue_code) venue_id,
                       race_no, deadline_time, deadline_at
                from v2_races
                where race_date=%s
                order by deadline_at, venue_id, race_no
                """,
                (TARGET_DATE,),
            )
            races = [dict(row) for row in cur.fetchall()]

        eligible: List[Dict[str, Any]] = []
        for row in races:
            deadline = _deadline_at(row)
            if deadline is None:
                continue
            mb = (deadline - now_jst).total_seconds() / 60.0
            if not (MIN_BEFORE <= mb <= MAX_BEFORE):
                continue
            if not any(_in_window(row, name) for name in active):
                continue
            row["minutes_before"] = mb
            eligible.append(row)

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

    incomplete: List[Dict[str, Any]] = []
    for row in eligible:
        rid = str(row["race_id"])
        if not odds._evaluate_ticket_snapshot(tickets_by.get(rid, [])).get("complete", False):
            incomplete.append(row)

    targets = incomplete[:LIMIT]
    would_complete = 0
    html_ok = 0
    exact120 = 0
    dynamic_complete = 0

    print(
        f"WINDOW_REFRESH_PROBE_COUNTS=eligible:{len(eligible)} incomplete:{len(incomplete)} "
        f"probed:{len(targets)}",
        flush=True,
    )

    for row in targets:
        rid = str(row["race_id"])
        venue = str(row.get("venue_id") or "").zfill(2)
        rno = int(row["race_no"])
        mb = float(row.get("minutes_before") or 0.0)
        url = repair._official_url("odds3t", TARGET_DATE, venue, rno)
        html = repair._fetch(url)
        if html:
            html_ok += 1
        parsed = repair.parse_odds3t(html or "", rid) if html else []
        status = odds._evaluate_ticket_snapshot([str(x.get("ticket") or "") for x in parsed])
        complete = bool(status.get("complete", False))
        if complete:
            would_complete += 1
            dynamic_complete += 1
        if len(parsed) == 120 and complete:
            exact120 += 1
        print(
            f"WINDOW_REFRESH_PROBE_RACE=race:{rid} minutes_before:{mb:.2f} "
            f"html:{'ok' if html else 'missing'} parsed:{len(parsed)} "
            f"expected:{status.get('expected_count',0)} active_lanes:{status.get('active_lanes',[])} "
            f"complete:{str(complete).lower()}",
            flush=True,
        )

    print(
        f"WINDOW_REFRESH_PROBE_SUMMARY=probed:{len(targets)} html_ok:{html_ok} "
        f"would_complete:{would_complete} exact120:{exact120} dynamic_complete:{dynamic_complete} "
        f"still_incomplete:{len(targets)-would_complete}",
        flush=True,
    )
    print("WINDOW_REFRESH_PROBE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
