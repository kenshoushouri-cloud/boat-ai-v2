# -*- coding: utf-8 -*-
"""
analyze_candidate_grid_pg.py

2025年7月以降の履歴データを使い、v24と同じ確率計算で候補条件を総当たり比較する
読み取り専用スクリプトです。

重要:
- DB更新、LINE通知、本番判定の変更は行いません。
- 過学習を避けるため、前半をTRAIN、後半をTESTとして時系列分割します。
- TRAINだけ良くTESTで崩れる条件は採用候補から除外します。
- v2_odds_trifectaに保存されているオッズを使うため、厳密な「当時時点」再現ではありません。

Start Command:
    python -u analyze_candidate_grid_pg.py

必須Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}

推奨Variables:
    ANALYZE_START_DATE=2025-07-01
    ANALYZE_END_DATE=2026-08-01
    ANALYZE_TEST_START_DATE=2026-05-01
    ANALYZE_MIN_TRAIN_CANDIDATES=50
    ANALYZE_MIN_TEST_CANDIDATES=20
    ANALYZE_TOP_N=100
    ANALYZE_MAX_RACE_NO=12
    ANALYZE_REQUIRE_COMPLETE_ODDS=1
    ANALYZE_MAX_CONDITIONS=0

任意:
    ANALYZE_VENUES=01,02,...,24
    ANALYZE_SHOW_PROGRESS_EVERY=500
"""

from __future__ import annotations

import itertools
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))

START_DATE = os.getenv("ANALYZE_START_DATE", "2025-07-01")
END_DATE = os.getenv(
    "ANALYZE_END_DATE",
    datetime.now(JST).strftime("%Y-%m-%d"),
)
TEST_START_DATE = os.getenv("ANALYZE_TEST_START_DATE", "2026-05-01")

MIN_TRAIN_CANDIDATES = max(
    1,
    int(os.getenv("ANALYZE_MIN_TRAIN_CANDIDATES", "50")),
)
MIN_TEST_CANDIDATES = max(
    1,
    int(os.getenv("ANALYZE_MIN_TEST_CANDIDATES", "20")),
)
TOP_N = max(1, int(os.getenv("ANALYZE_TOP_N", "100")))
MAX_RACE_NO = max(
    1,
    min(12, int(os.getenv("ANALYZE_MAX_RACE_NO", "12"))),
)
MAX_CONDITIONS = max(
    0,
    int(os.getenv("ANALYZE_MAX_CONDITIONS", "0")),
)
PROGRESS_EVERY = max(
    1,
    int(os.getenv("ANALYZE_SHOW_PROGRESS_EVERY", "500")),
)
REQUIRE_COMPLETE_ODDS = (
    os.getenv("ANALYZE_REQUIRE_COMPLETE_ODDS", "1")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)

raw_venues = os.getenv("ANALYZE_VENUES", "")
VENUES = {
    value.strip().zfill(2)
    for value in raw_venues.split(",")
    if value.strip()
} or {f"{i:02d}" for i in range(1, 25)}

# 総当たり軸。必要に応じて後から拡張可能。
PROB_WINDOWS = [
    (1, 5),
    (1, 10),
    (6, 15),
    (6, 20),
    (11, 20),
    (11, 25),
    (16, 30),
]

MARKET_WINDOWS = [
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 5),
    (2, 5),
    (6, 10),
    (11, 20),
    (21, 30),
]

ODDS_WINDOWS = [
    (2.0, 3.0),
    (3.0, 5.0),
    (3.0, 6.0),
    (3.0, 8.0),
    (5.0, 8.0),
    (5.0, 10.0),
    (8.0, 15.0),
    (10.0, 20.0),
    (20.0, 30.0),
    (30.0, 50.0),
]

RACE_GROUPS = {
    "ALL": set(range(1, 13)),
    "R01_03": {1, 2, 3},
    "R04_06": {4, 5, 6},
    "R07_09": {7, 8, 9},
    "R10_12": {10, 11, 12},
    "R04_09": {4, 5, 6, 7, 8, 9},
    "R01_09": set(range(1, 10)),
}

VENUE_STYLES = {
    "ALL",
    "bad5",
    "rough",
    "in_strong",
    "standard",
}

EVENT_CATEGORIES = {
    "ALL",
    "general_cup_award",
    "general_named",
    "all_ladies",
    "venus",
    "ladies_other",
    "rookie",
    "young",
    "masters",
    "SG_like",
    "G1_like",
    "G2_like",
    "G3_like",
    "category_other",
    "category_unknown",
}

DAY_GROUPS = {
    "ALL",
    "DAY1",
    "DAY2_3",
    "DAY4_5",
    "DAY6PLUS",
}

SELECT_MODES = {
    "prob",
    "ev",
}


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _next_day(date_str: str) -> str:
    return (
        datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")


def _date_text(value: Any) -> str:
    return str(value or "")[:10]


def _day_group(day_no: int) -> str:
    if day_no <= 1:
        return "DAY1"
    if day_no <= 3:
        return "DAY2_3"
    if day_no <= 5:
        return "DAY4_5"
    return "DAY6PLUS"


def _new_stat() -> Dict[str, int]:
    return {
        "candidates": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
    }


def _add_stat(
    stat: Dict[str, int],
    *,
    hit: bool,
    payout: int,
) -> None:
    stat["candidates"] += 1
    stat["investment"] += 100
    if hit:
        stat["hits"] += 1
        stat["return"] += int(payout)


def _metrics(stat: Dict[str, int]) -> Dict[str, float]:
    candidates = int(stat["candidates"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])

    hit_rate = (
        hits / candidates * 100.0
        if candidates > 0
        else 0.0
    )
    roi = (
        returned / investment * 100.0
        if investment > 0
        else 0.0
    )
    profit = returned - investment

    return {
        "candidates": float(candidates),
        "hits": float(hits),
        "investment": float(investment),
        "return": float(returned),
        "profit": float(profit),
        "hit_rate": hit_rate,
        "roi": roi,
    }


def _wilson_lower_bound(
    hits: int,
    n: int,
    z: float = 1.96,
) -> float:
    if n <= 0:
        return 0.0
    p = hits / n
    denominator = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    adjusted = z * (
        (
            p * (1.0 - p) / n
            + z * z / (4.0 * n * n)
        )
        ** 0.5
    )
    return (centre - adjusted) / denominator


def _condition_key(
    prob_window: Tuple[int, int],
    market_window: Tuple[int, int],
    odds_window: Tuple[float, float],
    race_group: str,
    venue_style: str,
    event_category: str,
    day_group: str,
    select_mode: str,
) -> str:
    return (
        f"pr={prob_window[0]}-{prob_window[1]} "
        f"mr={market_window[0]}-{market_window[1]} "
        f"odds={odds_window[0]:g}-{odds_window[1]:g} "
        f"race={race_group} "
        f"venue={venue_style} "
        f"cat={event_category} "
        f"day={day_group} "
        f"select={select_mode}"
    )


def _condition_matches_meta(
    *,
    race_no: int,
    actual_venue_style: str,
    actual_event_category: str,
    actual_day_group: str,
    race_group: str,
    venue_style: str,
    event_category: str,
    day_group: str,
) -> bool:
    if race_no not in RACE_GROUPS[race_group]:
        return False
    if (
        venue_style != "ALL"
        and actual_venue_style != venue_style
    ):
        return False
    if (
        event_category != "ALL"
        and actual_event_category != event_category
    ):
        return False
    if (
        day_group != "ALL"
        and actual_day_group != day_group
    ):
        return False
    return True


def _candidate_rows(
    ranked: List[Dict[str, Any]],
    prob_window: Tuple[int, int],
    market_window: Tuple[int, int],
    odds_window: Tuple[float, float],
) -> List[Dict[str, Any]]:
    pr_min, pr_max = prob_window
    mr_min, mr_max = market_window
    odds_min, odds_max = odds_window

    rows: List[Dict[str, Any]] = []
    for row in ranked:
        pr = _safe_int(row.get("prob_rank"), 999)
        mr = _safe_int(row.get("market_rank"), 999)
        odd = _safe_float(row.get("odds"), 0.0)
        if (
            pr_min <= pr <= pr_max
            and mr_min <= mr <= mr_max
            and odds_min <= odd < odds_max
        ):
            rows.append(row)
    return rows


def _select_one(
    rows: List[Dict[str, Any]],
    select_mode: str,
) -> Optional[Dict[str, Any]]:
    if not rows:
        return None

    if select_mode == "ev":
        return max(
            rows,
            key=lambda row: (
                _safe_float(row.get("raw_ev"), 0.0),
                _safe_float(row.get("prob"), 0.0),
            ),
        )

    return max(
        rows,
        key=lambda row: (
            _safe_float(row.get("prob"), 0.0),
            _safe_float(row.get("raw_ev"), 0.0),
        ),
    )


def _fetch_all_data():
    start_rid = START_DATE.replace("-", "")
    end_rid = _next_day(END_DATE).replace("-", "")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s
          and race_date <= %s
        order by race_date, venue_id, race_no;
        """,
        (START_DATE, END_DATE),
    )

    entries = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id >= %s
          and race_id < %s
        order by race_id, lane;
        """,
        (start_rid, end_rid),
    )

    odds = fetch_all(
        """
        select race_id, ticket, odds
        from v2_odds_trifecta
        where race_id >= %s
          and race_id < %s
        order by race_id, ticket;
        """,
        (start_rid, end_rid),
    )

    results = fetch_all(
        """
        select
            race_id,
            trifecta_ticket,
            trifecta_payout_yen,
            result_status
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (start_rid, end_rid),
    )

    return races, entries, odds, results


def _condition_iter() -> Iterable[
    Tuple[
        Tuple[int, int],
        Tuple[int, int],
        Tuple[float, float],
        str,
        str,
        str,
        str,
        str,
    ]
]:
    count = 0

    # まず広い条件
    broad_meta = [
        ("ALL", "ALL", "ALL"),
        ("R01_03", "ALL", "ALL"),
        ("R04_06", "ALL", "ALL"),
        ("R07_09", "ALL", "ALL"),
        ("R10_12", "ALL", "ALL"),
        ("R04_09", "ALL", "ALL"),
        ("ALL", "bad5", "ALL"),
        ("ALL", "rough", "ALL"),
        ("ALL", "in_strong", "ALL"),
        ("ALL", "standard", "ALL"),
        ("ALL", "ALL", "DAY1"),
        ("ALL", "ALL", "DAY2_3"),
        ("ALL", "ALL", "DAY4_5"),
        ("ALL", "ALL", "DAY6PLUS"),
    ]

    # 次にレース帯×会場タイプ
    for race_group in RACE_GROUPS:
        for venue_style in VENUE_STYLES:
            broad_meta.append(
                (race_group, venue_style, "ALL")
            )

    # 開催カテゴリは単独評価
    category_meta = [
        ("ALL", "ALL", category)
        for category in EVENT_CATEGORIES
        if category != "ALL"
    ]

    meta_conditions = list(dict.fromkeys(
        broad_meta + category_meta
    ))

    for (
        prob_window,
        market_window,
        odds_window,
        meta_tuple,
        select_mode,
    ) in itertools.product(
        PROB_WINDOWS,
        MARKET_WINDOWS,
        ODDS_WINDOWS,
        meta_conditions,
        SELECT_MODES,
    ):
        race_group, venue_style, day_group = meta_tuple
        event_category = "ALL"

        if (
            venue_style == "ALL"
            and day_group not in DAY_GROUPS
        ):
            event_category = day_group
            day_group = "ALL"

        yield (
            prob_window,
            market_window,
            odds_window,
            race_group,
            venue_style,
            event_category,
            day_group,
            select_mode,
        )
        count += 1
        if MAX_CONDITIONS and count >= MAX_CONDITIONS:
            return


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        "✅ analyze_candidate_grid_pg.py "
        "VERSION 2026-08-01 chronological-grid-v1",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"TEST_START_DATE={TEST_START_DATE}",
        flush=True,
    )
    print(
        f"MIN_TRAIN_CANDIDATES={MIN_TRAIN_CANDIDATES} "
        f"MIN_TEST_CANDIDATES={MIN_TEST_CANDIDATES} "
        f"TOP_N={TOP_N}",
        flush=True,
    )
    print(
        f"MAX_RACE_NO={MAX_RACE_NO} "
        f"REQUIRE_COMPLETE_ODDS={REQUIRE_COMPLETE_ODDS}",
        flush=True,
    )
    print(
        "読み取り専用です。DB更新・LINE通知・本番判定変更はありません。",
        flush=True,
    )
    print(
        "注意: v2_odds_trifectaの保存値を使うため、"
        "厳密な当時時点バックテストではありません。",
        flush=True,
    )

    races, entries_rows, odds_rows, results_rows = (
        _fetch_all_data()
    )

    entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in entries_rows:
        entries_by[str(row.get("race_id"))].append(row)

    odds_by: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in odds_rows:
        race_id = str(row.get("race_id") or "")
        ticket = v24._norm_ticket(row.get("ticket"))
        odd = _safe_float(row.get("odds"), 0.0)
        if race_id and ticket and odd > 0:
            odds_by[race_id][ticket] = odd

    results_by: Dict[str, Dict[str, Any]] = {}
    for row in results_rows:
        race_id = str(row.get("race_id") or "")
        if not race_id:
            continue
        results_by[race_id] = {
            "ticket": v24._norm_ticket(
                row.get("trifecta_ticket")
            ),
            "payout": _safe_int(
                row.get("trifecta_payout_yen"),
                0,
            ),
            "status": str(
                row.get("result_status") or ""
            ),
        }

    event_day_by_date: Dict[str, Dict[str, int]] = {}
    for date_str in sorted(
        {_date_text(r.get("race_date")) for r in races}
    ):
        if date_str:
            event_day_by_date[date_str] = (
                v24._compute_event_day_by_venue(date_str)
            )

    prepared: List[Dict[str, Any]] = []

    total_races = 0
    skipped_venue = 0
    skipped_race_no = 0
    skipped_entries = 0
    skipped_odds = 0
    skipped_result = 0

    for index, race in enumerate(races, start=1):
        total_races += 1

        race_id = str(race.get("race_id") or "")
        race_date = _date_text(race.get("race_date"))
        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)
        race_no = _safe_int(race.get("race_no"), 0)

        if venue_id not in VENUES:
            skipped_venue += 1
            continue
        if race_no <= 0 or race_no > MAX_RACE_NO:
            skipped_race_no += 1
            continue

        entries = entries_by.get(race_id, [])
        if len(v24._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue

        odds = odds_by.get(race_id, {})
        if REQUIRE_COMPLETE_ODDS:
            ready, _ = v24._validate_odds_snapshot(odds)
            if not ready:
                skipped_odds += 1
                continue
        elif not odds:
            skipped_odds += 1
            continue

        result = results_by.get(race_id)
        if (
            not result
            or not result.get("ticket")
            or _safe_int(result.get("payout"), 0) <= 0
        ):
            skipped_result += 1
            continue

        meta_text = v24._metadata_text(race)
        actual_venue_style = v24._infer_venue_style(
            venue_id
        )
        actual_event_category = (
            v24._infer_event_category(meta_text)
        )

        day_no = (
            event_day_by_date
            .get(race_date, {})
            .get(venue_id, 1)
        )
        actual_day_group = _day_group(day_no)

        ranked = v24._rank_candidates(
            entries,
            venue_id,
            odds,
        )

        prepared.append(
            {
                "race_id": race_id,
                "race_date": race_date,
                "venue_id": venue_id,
                "race_no": race_no,
                "venue_style": actual_venue_style,
                "event_category": actual_event_category,
                "day_group": actual_day_group,
                "ranked": ranked,
                "result_ticket": str(
                    result.get("ticket") or ""
                ),
                "payout": _safe_int(
                    result.get("payout"),
                    0,
                ),
            }
        )

        if index % PROGRESS_EVERY == 0:
            print(
                f"prepare progress={index}/{len(races)} "
                f"ready={len(prepared)}",
                flush=True,
            )

    print("\n=== data coverage ===", flush=True)
    print(f"total_races={total_races}", flush=True)
    print(f"prepared_races={len(prepared)}", flush=True)
    print(f"skipped_venue={skipped_venue}", flush=True)
    print(f"skipped_race_no={skipped_race_no}", flush=True)
    print(f"skipped_entries={skipped_entries}", flush=True)
    print(f"skipped_odds={skipped_odds}", flush=True)
    print(f"skipped_result={skipped_result}", flush=True)

    train_races = [
        row for row in prepared
        if row["race_date"] < TEST_START_DATE
    ]
    test_races = [
        row for row in prepared
        if row["race_date"] >= TEST_START_DATE
    ]

    print(
        f"train_races={len(train_races)} "
        f"test_races={len(test_races)}",
        flush=True,
    )

    condition_rows: List[Dict[str, Any]] = []

    for condition_index, condition in enumerate(
        _condition_iter(),
        start=1,
    ):
        (
            prob_window,
            market_window,
            odds_window,
            race_group,
            venue_style,
            event_category,
            day_group,
            select_mode,
        ) = condition

        train_stat = _new_stat()
        test_stat = _new_stat()

        for dataset_name, dataset, stat in (
            ("train", train_races, train_stat),
            ("test", test_races, test_stat),
        ):
            for race in dataset:
                if not _condition_matches_meta(
                    race_no=race["race_no"],
                    actual_venue_style=race[
                        "venue_style"
                    ],
                    actual_event_category=race[
                        "event_category"
                    ],
                    actual_day_group=race[
                        "day_group"
                    ],
                    race_group=race_group,
                    venue_style=venue_style,
                    event_category=event_category,
                    day_group=day_group,
                ):
                    continue

                candidates = _candidate_rows(
                    race["ranked"],
                    prob_window,
                    market_window,
                    odds_window,
                )
                selected = _select_one(
                    candidates,
                    select_mode,
                )
                if not selected:
                    continue

                ticket = str(
                    selected.get("ticket") or ""
                )
                hit = (
                    ticket == race["result_ticket"]
                )
                payout = (
                    race["payout"]
                    if hit
                    else 0
                )
                _add_stat(
                    stat,
                    hit=hit,
                    payout=payout,
                )

        train_metrics = _metrics(train_stat)
        test_metrics = _metrics(test_stat)

        if (
            train_stat["candidates"]
            < MIN_TRAIN_CANDIDATES
            or test_stat["candidates"]
            < MIN_TEST_CANDIDATES
        ):
            continue

        test_hit_lb = _wilson_lower_bound(
            test_stat["hits"],
            test_stat["candidates"],
        )

        # TESTを優先。TRAINとの乖離が小さく、候補数が多い条件を上位へ。
        stability_penalty = abs(
            train_metrics["roi"]
            - test_metrics["roi"]
        )
        score = (
            test_metrics["roi"]
            + min(
                test_metrics["profit"] / 1000.0,
                30.0,
            )
            + test_hit_lb * 100.0
            + min(
                test_stat["candidates"] / 100.0,
                10.0,
            )
            - stability_penalty * 0.25
        )

        condition_rows.append(
            {
                "condition": _condition_key(
                    prob_window,
                    market_window,
                    odds_window,
                    race_group,
                    venue_style,
                    event_category,
                    day_group,
                    select_mode,
                ),
                "train_candidates": train_stat[
                    "candidates"
                ],
                "train_hits": train_stat["hits"],
                "train_roi": train_metrics["roi"],
                "train_profit": train_metrics[
                    "profit"
                ],
                "test_candidates": test_stat[
                    "candidates"
                ],
                "test_hits": test_stat["hits"],
                "test_hit_rate": test_metrics[
                    "hit_rate"
                ],
                "test_roi": test_metrics["roi"],
                "test_profit": test_metrics[
                    "profit"
                ],
                "test_hit_lb": (
                    test_hit_lb * 100.0
                ),
                "stability_gap": (
                    stability_penalty
                ),
                "score": score,
            }
        )

        if condition_index % 1000 == 0:
            print(
                f"grid progress={condition_index} "
                f"qualified={len(condition_rows)}",
                flush=True,
            )

    condition_rows.sort(
        key=lambda row: (
            row["score"],
            row["test_roi"],
            row["test_profit"],
            row["test_candidates"],
        ),
        reverse=True,
    )

    print("\n=== top chronological holdout conditions ===", flush=True)
    if not condition_rows:
        print(
            "条件を満たす結果がありません。"
            "MIN_TRAIN/TEST_CANDIDATESを確認してください。",
            flush=True,
        )
    else:
        for index, row in enumerate(
            condition_rows[:TOP_N],
            start=1,
        ):
            print(
                f"{index:03d}. {row['condition']}",
                flush=True,
            )
            print(
                "     "
                f"TRAIN n={row['train_candidates']} "
                f"hits={row['train_hits']} "
                f"ROI={row['train_roi']:.2f}% "
                f"profit={int(row['train_profit'])}",
                flush=True,
            )
            print(
                "     "
                f"TEST n={row['test_candidates']} "
                f"hits={row['test_hits']} "
                f"hit_rate={row['test_hit_rate']:.2f}% "
                f"ROI={row['test_roi']:.2f}% "
                f"profit={int(row['test_profit'])} "
                f"hit_lb={row['test_hit_lb']:.2f}% "
                f"gap={row['stability_gap']:.2f}pt "
                f"score={row['score']:.2f}",
                flush=True,
            )

    print("\n=== robust shortlist ===", flush=True)
    robust = [
        row
        for row in condition_rows
        if row["train_roi"] >= 95.0
        and row["test_roi"] >= 100.0
        and row["test_profit"] > 0
        and row["stability_gap"] <= 35.0
    ]

    if not robust:
        print(
            "現基準では堅牢候補なし。"
            "本番条件は変更しないでください。",
            flush=True,
        )
    else:
        for index, row in enumerate(
            robust[:TOP_N],
            start=1,
        ):
            print(
                f"{index:03d}. {row['condition']} "
                f"| TRAIN n={row['train_candidates']} "
                f"ROI={row['train_roi']:.2f}% "
                f"| TEST n={row['test_candidates']} "
                f"ROI={row['test_roi']:.2f}% "
                f"profit={int(row['test_profit'])}",
                flush=True,
            )

    print("\n=== analysis finished ===", flush=True)


if __name__ == "__main__":
    main()