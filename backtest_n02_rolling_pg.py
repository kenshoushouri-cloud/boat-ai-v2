# -*- coding: utf-8 -*-
"""
backtest_n02_rolling_pg.py

N02ルールを変更せず、連続Nか月のローリング窓で安定性を確認する
読み取り専用バックテスト。

DB更新なし / LINE通知なし。

Start Command:
    python -u backtest_n02_rolling_pg.py

Variables:
    DATABASE_URL

任意:
    BACKTEST_START_DATE=2025-07-01
    BACKTEST_END_DATE=2026-08-16
    BACKTEST_UNIT_YEN=100
    BACKTEST_ROLLING_MONTHS=3
    BACKTEST_PROGRESS_EVERY_DAYS=10
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION = "2026-08-18 n02-rolling-v1"

START_DATE = os.getenv("BACKTEST_START_DATE", "2025-07-01")
END_DATE = os.getenv("BACKTEST_END_DATE", "2026-08-16")
UNIT_YEN = max(1, int(os.getenv("BACKTEST_UNIT_YEN", "100")))
ROLLING_MONTHS = max(1, int(os.getenv("BACKTEST_ROLLING_MONTHS", "3")))
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


def _merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    target["bets"] += int(source["bets"])
    target["hits"] += int(source["hits"])
    target["investment"] += int(source["investment"])
    target["return"] += int(source["return"])
    target["hit_returns"].extend(source["hit_returns"])


def _metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    bets = int(stat["bets"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    profit = returned - investment

    hit_rate = hits / bets * 100.0 if bets else 0.0
    roi = returned / investment * 100.0 if investment else 0.0
    max_hit = max(stat["hit_returns"]) if stat["hit_returns"] else 0
    share = (
        max_hit / returned * 100.0
        if returned > 0
        else 0.0
    )

    return {
        "bets": bets,
        "hits": hits,
        "investment": investment,
        "return": returned,
        "profit": profit,
        "hit_rate": hit_rate,
        "roi": roi,
        "max_hit": max_hit,
        "single_hit_share": share,
    }


def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    print(
        f"{label}: "
        f"bets={m['bets']} "
        f"hits={m['hits']} "
        f"hit_rate={m['hit_rate']:.3f}% "
        f"investment={m['investment']} "
        f"return={m['return']} "
        f"profit={m['profit']} "
        f"ROI={m['roi']:.2f}% "
        f"max_hit={m['max_hit']} "
        f"single_hit_share={m['single_hit_share']:.2f}%",
        flush=True,
    )


def _month_start(month: str) -> datetime:
    return datetime.strptime(month + "-01", "%Y-%m-%d")


def _add_months(month: str, months: int) -> str:
    d = _month_start(month)
    total = d.year * 12 + (d.month - 1) + months
    year = total // 12
    mon = total % 12 + 1
    return f"{year:04d}-{mon:02d}"


def _month_range(start_month: str, end_month: str) -> List[str]:
    out: List[str] = []
    cur = start_month
    while cur <= end_month:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


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
        f"✅ backtest_n02_rolling_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"ROLLING_MONTHS={ROLLING_MONTHS} "
        f"UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print(
        "N02条件は変更しません。DB書き込みなし。LINE通知なし。",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    monthly: Dict[str, Dict[str, Any]] = defaultdict(_stat)
    overall = _stat()

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
            month = day[:7]

            selections += 1
            _add(overall, hit, payout)
            _add(monthly[month], hit, payout)

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

    print("\n=== N02 OVERALL ===", flush=True)
    _print_stat("N02 ALL", overall)

    print("\n=== N02 MONTHLY ===", flush=True)
    months = _month_range(
        START_DATE[:7],
        END_DATE[:7],
    )

    for month in months:
        _print_stat(
            month,
            monthly[month],
        )

    print(
        f"\n=== N02 ROLLING {ROLLING_MONTHS} MONTHS ===",
        flush=True,
    )

    rolling_rows: List[Tuple[str, str, Dict[str, Any]]] = []

    for start_index in range(
        0,
        len(months) - ROLLING_MONTHS + 1,
    ):
        window_months = months[
            start_index:
            start_index + ROLLING_MONTHS
        ]

        stat = _stat()

        for month in window_months:
            _merge(
                stat,
                monthly[month],
            )

        start_month = window_months[0]
        end_month = window_months[-1]

        rolling_rows.append(
            (
                start_month,
                end_month,
                stat,
            )
        )

        _print_stat(
            f"{start_month}..{end_month}",
            stat,
        )

    roi_values = [
        _metrics(stat)["roi"]
        for _, _, stat in rolling_rows
        if _metrics(stat)["bets"] > 0
    ]

    positive_windows = sum(
        1
        for _, _, stat in rolling_rows
        if _metrics(stat)["roi"] >= 100.0
    )

    total_windows = len(rolling_rows)

    print("\n=== ROLLING SUMMARY ===", flush=True)

    if roi_values:
        print(
            f"rolling_windows={total_windows}",
            flush=True,
        )
        print(
            f"positive_windows={positive_windows}/{total_windows}",
            flush=True,
        )
        print(
            f"positive_window_pct="
            f"{positive_windows / total_windows * 100.0:.2f}%",
            flush=True,
        )
        print(
            f"min_rolling_roi={min(roi_values):.2f}%",
            flush=True,
        )
        print(
            f"max_rolling_roi={max(roi_values):.2f}%",
            flush=True,
        )
        print(
            f"avg_rolling_roi="
            f"{sum(roi_values) / len(roi_values):.2f}%",
            flush=True,
        )
    else:
        print("rolling_windows=0", flush=True)

    print("\n=== IMPORTANT NOTE ===", flush=True)
    print(
        "N02の条件は一切変更していません。"
        "ローリング窓ごとのROIが継続的に100%以上か、"
        "一時的な不調期間がどの程度あるかを確認するための診断です。",
        flush=True,
    )
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()