# -*- coding: utf-8 -*-
"""Read-only sensitivity probe for PRE impact of currently missing base odds.

For upcoming races whose v2_odds_trifecta snapshot is still incomplete, fetch the
official odds3t page with the existing parser and evaluate the existing v24 PRE
candidate rules in memory. No fetched odds or notification data are persisted.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import psycopg
from psycopg.rows import dict_row

import repair_month_all_pg as repair
import run_odds_window_pg as window_odds
import v24_pre_candidate_notifier_pg as core

JST = timezone(timedelta(hours=9))
DB = (os.getenv("DATABASE_URL") or "").strip()
TARGET_DATE = (os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")).strip()
MIN_BEFORE = float(os.getenv("WINDOW_REFRESH_MIN_MINUTES_BEFORE_DEADLINE", "10"))
MAX_BEFORE = float(os.getenv("WINDOW_REFRESH_MAX_MINUTES_BEFORE_DEADLINE", "60"))
LIMIT = max(1, min(20, int(os.getenv("PRE_ODDS_SENSITIVITY_LIMIT", "10"))))
SELECTOR_MODE = (os.getenv("SELECTOR_MODE") or "balanced").strip().lower()
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
    hhmm = str(row.get("deadline_time") or "")[:5]
    if not hhmm:
        return None
    try:
        return _clock_at(TARGET_DATE, hhmm)
    except Exception:
        return None


def _active_windows(now_jst: datetime) -> List[str]:
    active: List[str] = []
    prewarm = 15.0
    for name in VALID_WINDOWS:
        start, end = window_odds.WINDOW_PRESETS[name]
        lo = _clock_at(TARGET_DATE, start) - timedelta(minutes=prewarm)
        hi = _clock_at(TARGET_DATE, end) if end else _clock_at(TARGET_DATE, "23:59") + timedelta(minutes=1)
        if lo <= now_jst < hi:
            active.append(name)
    return active


def _in_window(row: Dict[str, Any], name: str) -> bool:
    hhmm = str(row.get("deadline_time") or "")[:5]
    if not hhmm:
        return False
    start, end = window_odds.WINDOW_PRESETS[name]
    return start <= hhmm < end if end else hhmm >= start


def _candidate_tickets(
    race: Dict[str, Any],
    entries: List[Dict[str, Any]],
    official_odds: Dict[str, float],
    event_day_no: int,
    pre_session: str,
) -> Set[str]:
    if len(core._entry_by_lane(entries)) != 6:
        return set()

    meta_text = core._metadata_text(race)
    venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
    race_no = core._safe_int(race.get("race_no"), 0)
    meta_session = core._infer_session_type(race)

    previous_session = core.PRE_SESSION
    core.PRE_SESSION = pre_session
    try:
        if not core._session_match(meta_session, venue_id, meta_text):
            return set()

        venue_style = core._infer_venue_style(venue_id)
        event_category = core._infer_event_category(meta_text)
        gender = core._infer_gender_category(meta_text)
        grade = core._infer_grade(meta_text)
        race_name = core._best_race_name(race)
        stage_combo = core._stage_combo(core._race_title_stage(race_name), event_day_no, race_no)
        ranked_rows = core._rank_candidates(entries, venue_id, official_odds)
        strategies = {s.name: s for s in core.V17_STRATEGIES}
        names = [n for n in core._selector_strategy_names(SELECTOR_MODE) if n in strategies]

        tickets: Set[str] = set()
        for name in names:
            st = strategies[name]
            if not core._match_extra_filter(
                st.extra_filter,
                venue_style,
                event_category,
                gender,
                grade,
                meta_session,
                event_day_no,
                race_no,
            ):
                continue
            for bet in core._select_bets(
                ranked_rows,
                st,
                venue_id,
                race_no,
                event_day_no,
                stage_combo,
            ):
                ticket = str(bet.get("ticket") or "").strip()
                if ticket:
                    tickets.add(ticket)
        return tickets
    finally:
        core.PRE_SESSION = previous_session


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    now_jst = datetime.now(JST)
    today = now_jst.strftime("%Y-%m-%d")
    active = _active_windows(now_jst)

    print("PRE_ODDS_SENSITIVITY_MODE=read_only_official_http_in_memory_v24", flush=True)
    print("PRE_ODDS_SENSITIVITY_POLICY=no_db_writes_no_line_no_shadow_no_final_no_promotion", flush=True)
    print(f"PRE_ODDS_SENSITIVITY_DATE={TARGET_DATE}", flush=True)
    print(f"PRE_ODDS_SENSITIVITY_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print(
        f"PRE_ODDS_SENSITIVITY_SCOPE=active_windows:{','.join(active) if active else 'none'} "
        f"min_before:{MIN_BEFORE:.1f} max_before:{MAX_BEFORE:.1f} limit:{LIMIT} selector:{SELECTOR_MODE}",
        flush=True,
    )

    if TARGET_DATE != today:
        print(f"PRE_ODDS_SENSITIVITY_RESULT=BLOCKED_NONLIVE_DATE today:{today}", flush=True)
        return
    if not active:
        print("PRE_ODDS_SENSITIVITY_SUMMARY=eligible:0 incomplete:0 probed:0 official_complete:0 candidate_races:0 candidate_tickets:0", flush=True)
        print("PRE_ODDS_SENSITIVITY_RESULT=PASS_READ_ONLY", flush=True)
        return

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select race_id,race_date,coalesce(venue_id,venue_code) venue_id,
                       venue_code,race_no,deadline_time,deadline_at,race_name,race_title,title,
                       event_title,event_name,series_title,series_name,tournament_title,
                       tournament_name,meeting_title,meet_title,grade,grade_type,category,
                       race_category,race_type,program_name,subtitle,session_type
                from v2_races
                where race_date=%s
                order by deadline_at,venue_id,race_no
                """,
                (TARGET_DATE,),
            )
            day_races = [dict(row) for row in cur.fetchall()]

        eligible: List[Dict[str, Any]] = []
        for row in day_races:
            deadline = _deadline_at(row)
            if deadline is None:
                continue
            mb = (deadline - now_jst).total_seconds() / 60.0
            if not (MIN_BEFORE <= mb <= MAX_BEFORE):
                continue
            windows = [name for name in active if _in_window(row, name)]
            if not windows:
                continue
            row["minutes_before"] = mb
            row["active_windows"] = windows
            eligible.append(row)

        ids = [str(row["race_id"]) for row in eligible]
        tickets_by: Dict[str, List[str]] = defaultdict(list)
        entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if ids:
            with conn.cursor() as cur:
                cur.execute(
                    "select race_id,ticket from v2_odds_trifecta where race_id=any(%s) order by race_id,ticket",
                    (ids,),
                )
                for row in cur.fetchall():
                    tickets_by[str(row["race_id"])].append(str(row.get("ticket") or ""))
                cur.execute(
                    """
                    select race_id,lane,racer_number,racer_class,racer_name,
                           national_win_rate,national_place2_rate,local_win_rate,local_place2_rate,
                           motor_no,boat_no,avg_st
                    from v2_race_entries
                    where race_id=any(%s)
                    order by race_id,lane
                    """,
                    (ids,),
                )
                for row in cur.fetchall():
                    entries_by[str(row["race_id"])].append(dict(row))

    incomplete = [
        row for row in eligible
        if not window_odds._evaluate_ticket_snapshot(tickets_by.get(str(row["race_id"]), [])).get("complete", False)
    ]
    targets = incomplete[:LIMIT]
    event_day_by_venue = core._compute_event_day_by_venue(TARGET_DATE)

    official_complete = 0
    candidate_races = 0
    candidate_tickets_total = 0

    print(
        f"PRE_ODDS_SENSITIVITY_COUNTS=eligible:{len(eligible)} incomplete:{len(incomplete)} probed:{len(targets)}",
        flush=True,
    )

    for row in targets:
        rid = str(row["race_id"])
        venue = str(row.get("venue_id") or "").zfill(2)
        rno = int(row.get("race_no") or 0)
        mb = float(row.get("minutes_before") or 0.0)
        html = repair._fetch(repair._official_url("odds3t", TARGET_DATE, venue, rno))
        parsed = repair.parse_odds3t(html or "", rid) if html else []
        status = window_odds._evaluate_ticket_snapshot([str(x.get("ticket") or "") for x in parsed])
        complete = bool(status.get("complete", False))
        candidate_union: Set[str] = set()

        if complete:
            official_complete += 1
            official_odds = {
                str(item.get("ticket") or ""): float(item.get("odds") or 0.0)
                for item in parsed
                if str(item.get("ticket") or "") and float(item.get("odds") or 0.0) > 0
            }
            event_day = int(event_day_by_venue.get(venue, 1))
            for window_name in row.get("active_windows") or []:
                pre_session = "night" if window_name == "night" else "day"
                candidate_union.update(
                    _candidate_tickets(row, entries_by.get(rid, []), official_odds, event_day, pre_session)
                )

        if candidate_union:
            candidate_races += 1
            candidate_tickets_total += len(candidate_union)
        sample = ",".join(sorted(candidate_union)[:8]) if candidate_union else "none"
        print(
            f"PRE_ODDS_SENSITIVITY_RACE=race:{rid} minutes_before:{mb:.2f} "
            f"windows:{','.join(row.get('active_windows') or [])} html:{'ok' if html else 'missing'} "
            f"parsed:{len(parsed)} official_complete:{str(complete).lower()} "
            f"candidate_tickets:{len(candidate_union)} sample:{sample}",
            flush=True,
        )

    print(
        f"PRE_ODDS_SENSITIVITY_SUMMARY=eligible:{len(eligible)} incomplete:{len(incomplete)} "
        f"probed:{len(targets)} official_complete:{official_complete} candidate_races:{candidate_races} "
        f"candidate_tickets:{candidate_tickets_total} unprobed:{max(0,len(incomplete)-len(targets))}",
        flush=True,
    )
    print("PRE_ODDS_SENSITIVITY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
