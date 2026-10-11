# -*- coding: utf-8 -*-
"""Read-only LINE candidate volume / near-miss diagnostic.

Purpose:
- measure why the current Production pre-candidate path rarely reaches LINE;
- quantify candidate-race volume against the operational observation target
  (roughly 1-3 quality races/day) without changing any selector threshold;
- separate data-readiness loss from selector/strategy loss.

Safety:
- diagnostic only;
- PostgreSQL is forced into default_transaction_read_only=on;
- no LINE send;
- no DB write;
- no selector/model/threshold mutation;
- no purchase action.

The implementation reuses the current Production v24 ranking/strategy helpers so
this diagnostic cannot silently invent a second selector contract.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Set


def _force_read_only_pgoptions() -> None:
    current = os.environ.get("PGOPTIONS", "").strip()
    guard = "-c default_transaction_read_only=on"
    if guard not in current:
        os.environ["PGOPTIONS"] = f"{current} {guard}".strip()


def classify_low_core_near_miss(rows: Iterable[Dict[str, Any]]) -> Set[str]:
    """Return non-exclusive race-level near-miss flags for the frozen low core.

    Production low core:
      prob_rank 11..20
      market_rank == 1
      3.0 <= odds < 5.0

    A flag ending in _only means exactly that dimension misses while the other
    two dimensions satisfy the frozen core. multi_miss is used only when no
    exact or one-dimension near miss exists.
    """

    flags: Set[str] = set()
    saw_any = False
    for row in rows:
        saw_any = True
        pr = int(row.get("prob_rank", 999) or 999)
        mr = int(row.get("market_rank", 999) or 999)
        odds = float(row.get("odds", 0.0) or 0.0)

        prob_ok = 11 <= pr <= 20
        market_ok = mr == 1
        odds_ok = 3.0 <= odds < 5.0

        if prob_ok and market_ok and odds_ok:
            flags.add("core_match")
            continue
        if (not prob_ok) and market_ok and odds_ok:
            flags.add("prob_rank_only")
            continue
        if prob_ok and (not market_ok) and odds_ok:
            flags.add("market_rank_only")
            continue
        if prob_ok and market_ok and (not odds_ok):
            flags.add("odds_low_only" if odds < 3.0 else "odds_high_only")

    if saw_any and not flags:
        flags.add("multi_miss")
    return flags


def _date_range(start_date: str, end_date: str) -> List[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("END_DATE must be >= START_DATE")
    out: List[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _actual_candidate_tickets(
    prod: Any,
    ranked_rows: List[Dict[str, Any]],
    venue_id: str,
    race_no: int,
    event_day_no: int,
    combo_stage: str,
    meta_venue_style: str,
    meta_event_category: str,
    meta_gender: str,
    meta_grade: str,
    meta_session: str,
    selector_mode: str,
) -> Set[str]:
    strategies_by_name = {s.name: s for s in prod.V17_STRATEGIES}
    strategy_names = [
        n for n in prod._selector_strategy_names(selector_mode)
        if n in strategies_by_name
    ]
    tickets: Set[str] = set()
    for strategy_name in strategy_names:
        st = strategies_by_name[strategy_name]
        if not prod._match_extra_filter(
            st.extra_filter,
            meta_venue_style,
            meta_event_category,
            meta_gender,
            meta_grade,
            meta_session,
            event_day_no,
            race_no,
        ):
            continue
        for bet in prod._select_bets(
            ranked_rows,
            st,
            venue_id,
            race_no,
            event_day_no,
            combo_stage,
        ):
            ticket = str(bet.get("ticket", "")).strip()
            if ticket:
                tickets.add(ticket)
    return tickets


def evaluate_date_session(
    target_date: str,
    session: str,
    selector_mode: str = "ab",
) -> Dict[str, Any]:
    if session not in {"day", "night", "all"}:
        raise ValueError("session must be day, night, or all")

    _force_read_only_pgoptions()
    import v24_pre_candidate_notifier_pg as prod  # lazy: guard env first

    original_pre_session = prod.PRE_SESSION
    try:
        prod.PRE_SESSION = session
        event_day_by_venue = prod._compute_event_day_by_venue(target_date)
        races, entries_by_race, odds_by_race = prod._fetch_live_day_rows(target_date)

        counts: Counter[str] = Counter()
        near_miss: Counter[str] = Counter()
        candidate_race_ids: Set[str] = set()
        candidate_ticket_count = 0

        for race in races:
            counts["races"] += 1
            race_id = str(race.get("race_id") or "")
            venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            race_no = int(race.get("race_no") or 0)
            entries = entries_by_race.get(race_id, [])
            odds = odds_by_race.get(race_id, {})

            by_lane = prod._entry_by_lane(entries)
            if len(by_lane) != 6:
                counts["skipped_entries"] += 1
                continue

            odds_ready, _detail = prod._validate_odds_snapshot(odds)
            if not odds_ready:
                counts["skipped_odds"] += 1
                continue

            counts["ready_races"] += 1

            meta_text = prod._metadata_text(race)
            meta_grade = prod._infer_grade(meta_text)
            meta_gender = prod._infer_gender_category(meta_text)
            meta_event_category = prod._infer_event_category(meta_text)
            meta_session = prod._infer_session_type(race)

            if not prod._session_match(meta_session, venue_id, meta_text):
                counts["skipped_session"] += 1
                continue

            counts["session_pass_races"] += 1
            meta_venue_style = prod._infer_venue_style(venue_id)
            race_name = prod._best_race_name(race)
            event_day_no = event_day_by_venue.get(venue_id, 1)
            title_stage = prod._race_title_stage(race_name)
            combo_stage = prod._stage_combo(title_stage, event_day_no, race_no)
            ranked_rows = prod._rank_candidates(entries, venue_id, odds)

            flags = classify_low_core_near_miss(ranked_rows)
            for flag in flags:
                near_miss[flag] += 1

            candidate_tickets = _actual_candidate_tickets(
                prod,
                ranked_rows,
                venue_id,
                race_no,
                event_day_no,
                combo_stage,
                meta_venue_style,
                meta_event_category,
                meta_gender,
                meta_grade,
                meta_session,
                selector_mode,
            )
            if candidate_tickets:
                candidate_race_ids.add(race_id)
                candidate_ticket_count += len(candidate_tickets)
            elif "core_match" in flags:
                counts["core_but_strategy_blocked"] += 1

        counts["candidate_races"] = len(candidate_race_ids)
        counts["candidate_tickets"] = candidate_ticket_count

        return {
            "target_date": target_date,
            "session": session,
            "selector_mode": selector_mode,
            "diagnostic_only": True,
            "purchase_action": False,
            "line_send": False,
            "db_write": False,
            "counts": dict(sorted(counts.items())),
            "near_miss_races_nonexclusive": dict(sorted(near_miss.items())),
        }
    finally:
        prod.PRE_SESSION = original_pre_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=os.environ.get("START_DATE"))
    parser.add_argument("--end-date", default=os.environ.get("END_DATE"))
    parser.add_argument("--selector-mode", default=os.environ.get("SELECTOR_MODE", "ab"))
    parser.add_argument(
        "--sessions",
        default=os.environ.get("SESSIONS", "day,night"),
        help="comma-separated: day,night,all",
    )
    args = parser.parse_args()

    if not args.start_date or not args.end_date:
        raise SystemExit("START_DATE and END_DATE (or --start-date/--end-date) are required")

    sessions = [x.strip() for x in args.sessions.split(",") if x.strip()]
    rows: List[Dict[str, Any]] = []
    for target_date in _date_range(args.start_date, args.end_date):
        for session in sessions:
            rows.append(evaluate_date_session(target_date, session, args.selector_mode))

    by_date: Dict[str, Dict[str, int]] = {}
    for row in rows:
        d = row["target_date"]
        agg = by_date.setdefault(d, {"candidate_races": 0, "candidate_tickets": 0})
        agg["candidate_races"] += int(row["counts"].get("candidate_races", 0))
        agg["candidate_tickets"] += int(row["counts"].get("candidate_tickets", 0))

    output = {
        "contract": "LINE_CANDIDATE_VOLUME_NEARMISS_DIAGNOSTIC_V1",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "selector_mode": args.selector_mode,
        "sessions": sessions,
        "operational_observation_target_races_per_day": {"min": 1, "max": 3},
        "target_is_not_a_selector_gate": True,
        "no_threshold_relaxation": True,
        "diagnostic_only": True,
        "purchase_action": False,
        "line_send": False,
        "db_write": False,
        "rows": rows,
        "daily_candidate_volume": by_date,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
