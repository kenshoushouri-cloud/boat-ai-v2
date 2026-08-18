# -*- coding: utf-8 -*-
"""
backtest_n02_time_split_pg.py

N02ルールを変更せず、期間前半・後半に分けて再現性を確認する
読み取り専用バックテスト。

DB更新なし / LINE通知なし。

Start Command:
    python -u backtest_n02_time_split_pg.py

Variables:
    DATABASE_URL

任意:
    BACKTEST_START_DATE=2025-07-01
    BACKTEST_END_DATE=2026-08-16
    BACKTEST_SPLIT_DATE=2026-02-01
    BACKTEST_UNIT_YEN=100
    BACKTEST_PROGRESS_EVERY_DAYS=10
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION = "2026-08-18 n02-time-split-v1"

START_DATE = os.getenv("BACKTEST_START_DATE", "2025-07-01")
END_DATE = os.getenv("BACKTEST_END_DATE", "2026-08-16")
SPLIT_DATE = os.getenv("BACKTEST_SPLIT_DATE", "2026-02-01")
UNIT_YEN = max(1, int(os.getenv("BACKTEST_UNIT_YEN", "100")))
PROGRESS_EVERY_DAYS = max(
    1,
    int(os.getenv("BACKTEST_PROGRESS_EVERY_DAYS", "10")),
)

RULES_BY_ID = {
    str(rule["rule_id"]).upper(): rule
    for rule in shadow.RULES
}
N02 = RULES_BY_ID["N02"]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _dates(start_date: str, end_date: str) -> Iterable[str]:
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


def _stat() -> Dict[str, Any]:
    return {
        "bets": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
    }


def _add(stat: Dict[str, Any], hit: bool, payout: int) -> None:
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN

    if hit:
        stat["hits"] += 1
        stat["return"] += payout
        if payout > 0:
            stat["hit_returns"].append(payout)


def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    bets = int(stat["bets"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    profit = returned - investment

    hit_rate = hits / bets * 100.0 if bets else 0.0
    roi = returned / investment * 100.0 if investment else 0.0
    max_hit = max(stat["hit_returns"]) if stat["hit_returns"] else 0
    single_hit_share = (
        max_hit / returned * 100.0
        if returned > 0
        else 0.0
    )

    print(
        f"{label}: "
        f"bets={bets} "
        f"hits={hits} "
        f"hit_rate={hit_rate:.3f}% "
        f"investment={investment} "
        f"return={returned} "
        f"profit={profit} "
        f"ROI={roi:.2f}% "
        f"max_hit={max_hit} "
        f"single_hit_share={single_hit_share:.2f}%",
        flush=True,
    )


def _split_name(day: str) -> str:
    return "FIRST" if day < SPLIT_DATE else "SECOND"


def _fetch_day(day: str):
    prefix = day.replace("-", "")
    next_prefix = (
        datetime.strptime(day, "%Y-%m-%d")
        + timedelta(days=1)
    ).strftime("%Y%m%d")

    results = fetch_all(
        """
        select
            race_id,
            trifecta_ticket,
            trifecta_payout_yen
        from v2_results
        where race_date=%s
          and trifecta_ticket is not null
          and trifecta_payout_yen is not null
          and trifecta_payout_yen > 0
          and finish_order is not null
          and winning_method is not null
          and coalesce(result_status,'')='official'
          and coalesce(race_status,'')='official'
        order by race_id;
        """,
        (day,),
    )

    result_by = {
        str(row.get("race_id")): row
        for row in results
        if row.get("race_id")
    }
    valid_ids = set(result_by)

    if not valid_ids:
        return [], {}, {}, {}, {}

    races = [
        row
        for row in fetch_all(
            """
            select *
            from v2_races
            where race_date=%s
            order by venue_id, race_no;
            """,
            (day,),
        )
        if str(row.get("race_id") or "") in valid_ids
    ]

    entries_by: Dict[str, list] = defaultdict(list)
    entries = fetch_all(
        """
        select
            race_id,
            lane,
            racer_number,
            racer_class,
            racer_name,
            national_win_rate,
            national_place2_rate,
            local_win_rate,
            local_place2_rate,
            motor_no,
            boat_no,
            avg_st
        from v2_race_entries
        where race_id >= %s
          and race_id < %s
        order by race_id, lane;
        """,
        (prefix, next_prefix),
    )

    for row in entries:
        race_id = str(row.get("race_id") or "")
        if race_id in valid_ids:
            entries_by[race_id].append(row)

    odds_by: Dict[str, Dict[str, float]] = defaultdict(dict)
    odds_rows = fetch_all(
        """
        select
            race_id,
            ticket,
            odds
        from v2_odds_trifecta
        where race_id >= %s
          and race_id < %s
        order by race_id, ticket;
        """,
        (prefix, next_prefix),
    )

    for row in odds_rows:
        race_id = str(row.get("race_id") or "")
        if race_id not in valid_ids:
            continue

        ticket = v24._norm_ticket(row.get("ticket"))
        odd = _safe_float(row.get("odds"), 0.0)

        if ticket and odd > 0:
            odds_by[race_id][ticket] = odd

    k_counts: Dict[str, int] = {}
    k_rows = fetch_all(
        """
        select
            race_id,
            count(*)::int as n
        from v2_result_entries
        where race_id >= %s
          and race_id < %s
        group by race_id;
        """,
        (prefix, next_prefix),
    )

    for row in k_rows:
        k_counts[str(row.get("race_id"))] = _safe_int(
            row.get("n"),
            0,
        )

    return (
        races,
        entries_by,
        odds_by,
        result_by,
        k_counts,
    )


def main() -> None:
    print(
        f"✅ backtest_n02_time_split_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"SPLIT_DATE={SPLIT_DATE} "
        f"UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print(
        "N02条件は変更しません。DB書き込みなし。LINE通知なし。",
        flush=True,
    )
    print(
        "N02="
        f"pr{N02['pr_min']}-{N02['pr_max']} "
        f"mr{N02['mr_min']}-{N02['mr_max']} "
        f"odds{N02['odds_min']}-{N02['odds_max']} "
        f"R{min(N02['race_nos']):02d}-{max(N02['race_nos']):02d} "
        f"select={N02['select_mode']}",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    overall = _stat()
    split_overall = defaultdict(_stat)
    split_race_no = defaultdict(_stat)
    split_prob_rank = defaultdict(_stat)
    split_market_rank = defaultdict(_stat)
    split_odds = defaultdict(_stat)
    split_venue = defaultdict(_stat)

    ready_races = 0
    selections = 0

    days = list(_dates(START_DATE, END_DATE))

    for index, day in enumerate(days, start=1):
        (
            races,
            entries_by,
            odds_by,
            result_by,
            k_counts,
        ) = _fetch_day(day)

        split = _split_name(day)

        for race in races:
            race_id = str(race.get("race_id") or "")
            venue_id = str(
                race.get("venue_id")
                or race.get("venue_code")
                or ""
            ).zfill(2)
            race_no = _safe_int(race.get("race_no"), 0)

            entries = entries_by.get(race_id, [])
            if len(v24._entry_by_lane(entries)) != 6:
                continue

            if k_counts.get(race_id, 0) != 6:
                continue

            odds = odds_by.get(race_id, {})
            odds_ready, _ = v24._validate_odds_snapshot(odds)

            if len(odds) != 120 or not odds_ready:
                continue

            ready_races += 1

            meta_text = v24._metadata_text(race)
            venue_style = v24._infer_venue_style(venue_id)
            event_category = v24._infer_event_category(meta_text)

            if race_no not in N02["race_nos"]:
                continue
            if (
                N02["venue_style"] != "ALL"
                and venue_style != N02["venue_style"]
            ):
                continue
            if (
                N02["event_category"] != "ALL"
                and event_category != N02["event_category"]
            ):
                continue

            ranked = v24._rank_candidates(
                entries,
                venue_id,
                odds,
            )

            matches = [
                row
                for row in ranked
                if shadow._match_rule(row, N02)
            ]

            selected = shadow._select_one(
                matches,
                str(N02["select_mode"]),
            )

            if not selected:
                continue

            ticket = str(selected.get("ticket") or "")
            if not ticket:
                continue

            result = result_by[race_id]
            result_ticket = v24._norm_ticket(
                result.get("trifecta_ticket")
            )
            payout = _safe_int(
                result.get("trifecta_payout_yen"),
                0,
            )
            hit = ticket == result_ticket

            prob_rank = _safe_int(
                selected.get("prob_rank"),
                999,
            )
            market_rank = _safe_int(
                selected.get("market_rank"),
                999,
            )
            odd = _safe_float(
                selected.get("odds"),
                0.0,
            )

            if 3.0 <= odd < 4.0:
                odds_bucket = "3.0-3.9"
            elif 4.0 <= odd < 5.0:
                odds_bucket = "4.0-4.9"
            elif 5.0 <= odd < 6.0:
                odds_bucket = "5.0-5.9"
            else:
                odds_bucket = "other"

            selections += 1

            _add(overall, hit, payout)
            _add(
                split_overall[split],
                hit,
                payout,
            )
            _add(
                split_race_no[(split, race_no)],
                hit,
                payout,
            )
            _add(
                split_prob_rank[(split, prob_rank)],
                hit,
                payout,
            )
            _add(
                split_market_rank[(split, market_rank)],
                hit,
                payout,
            )
            _add(
                split_odds[(split, odds_bucket)],
                hit,
                payout,
            )
            _add(
                split_venue[(split, venue_id)],
                hit,
                payout,
            )

        if (
            index % PROGRESS_EVERY_DAYS == 0
            or index == len(days)
        ):
            print(
                f"PROGRESS {index}/{len(days)} "
                f"date={day} "
                f"ready_races={ready_races} "
                f"n02_selections={selections}",
                flush=True,
            )

    first_end = (
        datetime.strptime(SPLIT_DATE, "%Y-%m-%d")
        - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    print("\n=== N02 OVERALL ===", flush=True)
    _print_stat("N02 ALL", overall)

    print("\n=== N02 TIME SPLIT ===", flush=True)
    print(
        f"FIRST={START_DATE}..{first_end}",
        flush=True,
    )
    _print_stat(
        "N02 FIRST",
        split_overall["FIRST"],
    )

    print(
        f"SECOND={SPLIT_DATE}..{END_DATE}",
        flush=True,
    )
    _print_stat(
        "N02 SECOND",
        split_overall["SECOND"],
    )

    for split in ("FIRST", "SECOND"):
        print(
            f"\n=== N02 {split} x RACE_NO ===",
            flush=True,
        )
        for race_no in range(7, 11):
            stat = split_race_no.get(
                (split, race_no)
            )
            if stat and stat["bets"]:
                _print_stat(
                    f"N02 {split} R{race_no:02d}",
                    stat,
                )

        print(
            f"\n=== N02 {split} x PROB_RANK ===",
            flush=True,
        )
        for prob_rank in range(11, 21):
            stat = split_prob_rank.get(
                (split, prob_rank)
            )
            if stat and stat["bets"]:
                _print_stat(
                    f"N02 {split} pr={prob_rank}",
                    stat,
                )

        print(
            f"\n=== N02 {split} x MARKET_RANK ===",
            flush=True,
        )
        for market_rank in range(2, 6):
            stat = split_market_rank.get(
                (split, market_rank)
            )
            if stat and stat["bets"]:
                _print_stat(
                    f"N02 {split} mr={market_rank}",
                    stat,
                )

        print(
            f"\n=== N02 {split} x ODDS_BUCKET ===",
            flush=True,
        )
        for bucket in (
            "3.0-3.9",
            "4.0-4.9",
            "5.0-5.9",
            "other",
        ):
            stat = split_odds.get(
                (split, bucket)
            )
            if stat and stat["bets"]:
                _print_stat(
                    f"N02 {split} odds={bucket}",
                    stat,
                )

        print(
            f"\n=== N02 {split} x VENUE ===",
            flush=True,
        )
        venue_ids = sorted(
            venue_id
            for (
                split_name,
                venue_id,
            ) in split_venue
            if split_name == split
        )
        for venue_id in venue_ids:
            _print_stat(
                f"N02 {split} venue={venue_id}",
                split_venue[
                    (split, venue_id)
                ],
            )

    print("\n=== IMPORTANT NOTE ===", flush=True)
    print(
        "N02の条件は一切変更していません。"
        "この検証は期間前半・後半での再現性確認専用です。",
        flush=True,
    )
    print(
        "全期間結果を既に確認済みなので厳密な未知データOOSではありません。"
        "前半・後半の両方で黒字か、傾向が極端に反転していないかを重視してください。",
        flush=True,
    )
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()