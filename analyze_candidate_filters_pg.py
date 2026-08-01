# -*- coding: utf-8 -*-
"""
analyze_candidate_filters_pg.py

v24_pre_candidate_notifier_pg.py と同じ確率計算を使い、
過去データで候補条件を比較する読み取り専用スクリプトです。

本番判定、LINE通知、DB更新は行いません。

Start Command:
    python -u analyze_candidate_filters_pg.py

Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}

任意:
    ANALYZE_START_DATE=2026-07-01
    ANALYZE_END_DATE=2026-08-01
    ANALYZE_VENUES=01,02,...,24
    ANALYZE_MAX_RACE_NO=9
    ANALYZE_REQUIRE_COMPLETE_ODDS=1
    ANALYZE_SHOW_DAILY=1
    ANALYZE_SHOW_VENUE=1
    ANALYZE_SHOW_RACE_GROUP=1
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).date()
DEFAULT_END = TODAY.strftime("%Y-%m-%d")
DEFAULT_START = (TODAY - timedelta(days=30)).strftime("%Y-%m-%d")

START_DATE = os.getenv("ANALYZE_START_DATE", DEFAULT_START)
END_DATE = os.getenv("ANALYZE_END_DATE", DEFAULT_END)
MAX_RACE_NO = max(1, min(12, int(os.getenv("ANALYZE_MAX_RACE_NO", "9"))))
REQUIRE_COMPLETE_ODDS = os.getenv("ANALYZE_REQUIRE_COMPLETE_ODDS", "1").strip().lower() in {"1", "true", "yes", "on"}
SHOW_DAILY = os.getenv("ANALYZE_SHOW_DAILY", "1").strip().lower() in {"1", "true", "yes", "on"}
SHOW_VENUE = os.getenv("ANALYZE_SHOW_VENUE", "1").strip().lower() in {"1", "true", "yes", "on"}
SHOW_RACE_GROUP = os.getenv("ANALYZE_SHOW_RACE_GROUP", "1").strip().lower() in {"1", "true", "yes", "on"}

raw_venues = os.getenv("ANALYZE_VENUES", "")
VENUES = {value.strip().zfill(2) for value in raw_venues.split(",") if value.strip()} or {f"{i:02d}" for i in range(1, 25)}

# name, prob_rank_min, prob_rank_max, market_rank_min, market_rank_max, odds_min, odds_max
FILTERS: List[Tuple[str, int, int, int, int, float, float]] = [
    ("current", 11, 20, 1, 1, 3.0, 5.0),
    ("A_prob6_20_mr1_odds3_6", 6, 20, 1, 1, 3.0, 6.0),
    ("B_prob11_25_mr1_3_odds3_8", 11, 25, 1, 3, 3.0, 8.0),
    ("C_prob1_10_mr1_5_odds3_8", 1, 10, 1, 5, 3.0, 8.0),
]


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _race_group(race_no: int) -> str:
    if race_no <= 3:
        return "R01_03"
    if race_no <= 6:
        return "R04_06"
    if race_no <= 9:
        return "R07_09"
    return "R10_12"


def _fetch_rows():
    next_end = (datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    start_prefix = START_DATE.replace("-", "")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s and race_date <= %s
        order by race_date, venue_id, race_no;
        """,
        (START_DATE, END_DATE),
    )
    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id, lane;
        """,
        (start_prefix, next_end),
    )
    odds = fetch_all(
        """
        select race_id, ticket, odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id, ticket;
        """,
        (start_prefix, next_end),
    )
    results = fetch_all(
        """
        select race_id, trifecta_ticket, trifecta_payout_yen, result_status
        from v2_results
        where race_id >= %s and race_id < %s;
        """,
        (start_prefix, next_end),
    )
    return races, entries, odds, results


def _candidate_match(row: Dict[str, Any], definition: Tuple[str, int, int, int, int, float, float]) -> bool:
    _, pr_min, pr_max, mr_min, mr_max, odds_min, odds_max = definition
    pr = _safe_int(row.get("prob_rank"), 999)
    mr = _safe_int(row.get("market_rank"), 999)
    odd = _safe_float(row.get("odds"), 0.0)
    return pr_min <= pr <= pr_max and mr_min <= mr <= mr_max and odds_min <= odd < odds_max


def _new_stat() -> Dict[str, int]:
    return {"candidates": 0, "hits": 0, "investment": 0, "return": 0}


def _add_result(stat: Dict[str, int], hit: bool, payout: int) -> None:
    stat["candidates"] += 1
    stat["investment"] += 100
    if hit:
        stat["hits"] += 1
        stat["return"] += payout


def _print_stat(label: str, stat: Dict[str, int]) -> None:
    candidates = stat["candidates"]
    hits = stat["hits"]
    investment = stat["investment"]
    ret = stat["return"]
    hit_rate = hits / candidates * 100.0 if candidates else 0.0
    roi = ret / investment * 100.0 if investment else 0.0
    profit = ret - investment
    print(f"{label}: candidates={candidates} hits={hits} hit_rate={hit_rate:.2f}% investment={investment} return={ret} profit={profit} ROI={roi:.2f}%", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ analyze_candidate_filters_pg.py VERSION 2026-08-01 filter-comparison-v1", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} MAX_RACE_NO={MAX_RACE_NO} REQUIRE_COMPLETE_ODDS={REQUIRE_COMPLETE_ODDS}", flush=True)
    print("読み取り専用です。本番判定・LINE通知・DB更新は行いません。", flush=True)

    races, entries_rows, odds_rows, result_rows = _fetch_rows()

    entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in entries_rows:
        entries_by[str(row.get("race_id"))].append(row)

    odds_by: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in odds_rows:
        rid = str(row.get("race_id") or "")
        ticket = v24._norm_ticket(row.get("ticket"))
        odd = _safe_float(row.get("odds"), 0.0)
        if rid and ticket and odd > 0:
            odds_by[rid][ticket] = odd

    results_by = {
        str(row.get("race_id")): {
            "ticket": v24._norm_ticket(row.get("trifecta_ticket")),
            "payout": _safe_int(row.get("trifecta_payout_yen"), 0),
        }
        for row in result_rows
    }

    overall = {name: _new_stat() for name, *_ in FILTERS}
    daily = {name: defaultdict(_new_stat) for name, *_ in FILTERS}
    venue = {name: defaultdict(_new_stat) for name, *_ in FILTERS}
    race_group = {name: defaultdict(_new_stat) for name, *_ in FILTERS}

    total_races = ready_races = skipped_venue = skipped_race_no = 0
    skipped_entries = skipped_odds = skipped_result = 0

    for race in races:
        rid = str(race.get("race_id") or "")
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)
        race_date = str(race.get("race_date"))[:10]
        total_races += 1

        if venue_id not in VENUES:
            skipped_venue += 1
            continue
        if race_no <= 0 or race_no > MAX_RACE_NO:
            skipped_race_no += 1
            continue

        entries = entries_by.get(rid, [])
        if len(v24._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue

        odds = odds_by.get(rid, {})
        if REQUIRE_COMPLETE_ODDS:
            odds_ready, _ = v24._validate_odds_snapshot(odds)
            if not odds_ready:
                skipped_odds += 1
                continue
        elif not odds:
            skipped_odds += 1
            continue

        result = results_by.get(rid)
        if not result or not result.get("ticket") or result.get("payout", 0) <= 0:
            skipped_result += 1
            continue

        ready_races += 1
        ranked = v24._rank_candidates(entries, venue_id, odds)

        for definition in FILTERS:
            name = definition[0]
            matches = [row for row in ranked if _candidate_match(row, definition)]
            if not matches:
                continue
            matches.sort(key=lambda row: (_safe_float(row.get("prob"), 0.0), _safe_float(row.get("raw_ev"), 0.0)), reverse=True)
            selected = matches[0]
            ticket = str(selected.get("ticket") or "")
            hit = ticket == result["ticket"]
            payout = int(result["payout"]) if hit else 0

            _add_result(overall[name], hit, payout)
            _add_result(daily[name][race_date], hit, payout)
            _add_result(venue[name][venue_id], hit, payout)
            _add_result(race_group[name][_race_group(race_no)], hit, payout)

    print("\n=== data coverage ===", flush=True)
    print(f"total_races={total_races}", flush=True)
    print(f"ready_races={ready_races}", flush=True)
    print(f"skipped_venue={skipped_venue}", flush=True)
    print(f"skipped_race_no={skipped_race_no}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print(f"skipped_result={skipped_result}", flush=True)

    print("\n=== overall filter comparison ===", flush=True)
    for name, *_ in FILTERS:
        _print_stat(name, overall[name])

    if SHOW_DAILY:
        print("\n=== daily breakdown ===", flush=True)
        all_dates = sorted({date for name in daily for date in daily[name].keys()})
        for date in all_dates:
            print(f"-- {date} --", flush=True)
            for name, *_ in FILTERS:
                stat = daily[name].get(date)
                if stat and stat["candidates"]:
                    _print_stat(name, stat)

    if SHOW_VENUE:
        print("\n=== venue breakdown (candidate count desc) ===", flush=True)
        for name, *_ in FILTERS:
            print(f"-- {name} --", flush=True)
            rows = sorted(venue[name].items(), key=lambda item: (item[1]["candidates"], item[1]["return"] - item[1]["investment"]), reverse=True)
            for venue_id, stat in rows[:24]:
                _print_stat(f"venue={venue_id}", stat)

    if SHOW_RACE_GROUP:
        print("\n=== race-group breakdown ===", flush=True)
        for name, *_ in FILTERS:
            print(f"-- {name} --", flush=True)
            for group in ("R01_03", "R04_06", "R07_09", "R10_12"):
                stat = race_group[name].get(group)
                if stat and stat["candidates"]:
                    _print_stat(group, stat)

    print("\n=== analysis finished ===", flush=True)


if __name__ == "__main__":
    main()