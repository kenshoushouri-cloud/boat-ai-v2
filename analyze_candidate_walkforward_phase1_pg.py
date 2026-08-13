# -*- coding: utf-8 -*-
"""
analyze_candidate_walkforward_phase1_pg.py

2025-07以降の保存済み履歴を月単位で読み込み、
v24と同じ候補ランキングを使って「prob_rank × market_rank × odds × 選定方法」
の基礎条件を3期間のウォークフォワードで評価します。

Phase 1の目的:
- まず場・開催カテゴリを混ぜる前の「買い目選定の核」を探す
- TRAINだけ良い条件を排除する
- VALIDATIONとTESTでも再現する条件だけPhase 2へ渡す
- 月ごとの安定性と単一的中依存を確認する

重要:
- 読み取り専用です。
- DB更新、LINE通知、本番判定、購入処理はありません。
- v2_odds_trifectaの保存済みオッズを使うため、厳密な当時時点オッズではありません。
- 完全オッズ(120/60/24通り)かつ有効結果のあるレースだけを使います。

Start Command:
    python -u analyze_candidate_walkforward_phase1_pg.py

推奨Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}
    BT_START_DATE=2025-07-01
    BT_VALID_START_DATE=2026-03-01
    BT_TEST_START_DATE=2026-06-01
    BT_END_DATE=2026-08-12

    BT_MIN_TRAIN=150
    BT_MIN_VALID=50
    BT_MIN_TEST=40
    BT_MIN_MONTH_CANDIDATES=10

    BT_MIN_TRAIN_ROI=90
    BT_MIN_VALID_ROI=100
    BT_MIN_TEST_ROI=100
    BT_MAX_SINGLE_HIT_SHARE=40
    BT_MIN_POSITIVE_MONTH_RATIO=45

    BT_TOP_N=100
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24


JST = timezone(timedelta(hours=9))

START_DATE = os.getenv("BT_START_DATE", "2025-07-01")
VALID_START_DATE = os.getenv("BT_VALID_START_DATE", "2026-03-01")
TEST_START_DATE = os.getenv("BT_TEST_START_DATE", "2026-06-01")
END_DATE = os.getenv(
    "BT_END_DATE",
    datetime.now(JST).strftime("%Y-%m-%d"),
)

MIN_TRAIN = max(1, int(os.getenv("BT_MIN_TRAIN", "150")))
MIN_VALID = max(1, int(os.getenv("BT_MIN_VALID", "50")))
MIN_TEST = max(1, int(os.getenv("BT_MIN_TEST", "40")))
MIN_MONTH_CANDIDATES = max(
    1, int(os.getenv("BT_MIN_MONTH_CANDIDATES", "10"))
)

MIN_TRAIN_ROI = float(os.getenv("BT_MIN_TRAIN_ROI", "90"))
MIN_VALID_ROI = float(os.getenv("BT_MIN_VALID_ROI", "100"))
MIN_TEST_ROI = float(os.getenv("BT_MIN_TEST_ROI", "100"))
MAX_SINGLE_HIT_SHARE = float(
    os.getenv("BT_MAX_SINGLE_HIT_SHARE", "40")
)
MIN_POSITIVE_MONTH_RATIO = float(
    os.getenv("BT_MIN_POSITIVE_MONTH_RATIO", "45")
)
TOP_N = max(1, int(os.getenv("BT_TOP_N", "100")))

PROB_WINDOWS: List[Tuple[int, int]] = [
    (1, 3),
    (1, 5),
    (1, 10),
    (4, 10),
    (6, 15),
    (6, 20),
    (11, 20),
    (11, 25),
    (16, 30),
    (21, 40),
]

MARKET_WINDOWS: List[Tuple[int, int]] = [
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 5),
    (2, 5),
    (3, 8),
    (6, 10),
    (11, 20),
    (21, 30),
    (31, 50),
]

ODDS_WINDOWS: List[Tuple[float, float]] = [
    (2.0, 3.0),
    (3.0, 5.0),
    (3.0, 6.0),
    (3.0, 8.0),
    (5.0, 8.0),
    (5.0, 10.0),
    (8.0, 15.0),
    (10.0, 20.0),
    (15.0, 25.0),
    (20.0, 30.0),
    (30.0, 50.0),
    (50.0, 80.0),
]

SELECT_MODES = ("prob", "ev")
PERIODS = ("TRAIN", "VALID", "TEST")


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


def _next_day(value: str) -> str:
    return (
        datetime.strptime(value, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")


def _month_starts(start_date: str, end_date: str) -> Iterable[str]:
    current = datetime.strptime(start_date[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(end_date[:7] + "-01", "%Y-%m-%d")
    while current <= end:
        yield current.strftime("%Y-%m-01")
        if current.month == 12:
            current = current.replace(
                year=current.year + 1, month=1, day=1
            )
        else:
            current = current.replace(month=current.month + 1, day=1)


def _month_end_exclusive(month_start: str) -> str:
    dt = datetime.strptime(month_start, "%Y-%m-%d")
    if dt.month == 12:
        nxt = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        nxt = dt.replace(month=dt.month + 1, day=1)
    return nxt.strftime("%Y-%m-%d")


def _new_stat() -> Dict[str, int]:
    return {
        "n": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "max_hit": 0,
    }


def _add_result(
    stat: Dict[str, int],
    hit: bool,
    payout: int,
) -> None:
    stat["n"] += 1
    stat["investment"] += 100
    if hit:
        payout = int(payout)
        stat["hits"] += 1
        stat["return"] += payout
        stat["max_hit"] = max(stat["max_hit"], payout)


def _metrics(stat: Dict[str, int]) -> Dict[str, float]:
    n = int(stat["n"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    roi = returned / investment * 100.0 if investment else 0.0
    return {
        "n": float(n),
        "hits": float(hits),
        "hit_rate": hits / n * 100.0 if n else 0.0,
        "investment": float(investment),
        "return": float(returned),
        "profit": float(returned - investment),
        "roi": roi,
        "single_hit_share": (
            int(stat["max_hit"]) / returned * 100.0
            if returned > 0
            else 0.0
        ),
    }


def _wilson_lower(hits: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = hits / n
    denominator = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    adjusted = z * math.sqrt(
        p * (1 - p) / n + z * z / (4 * n * n)
    )
    return (centre - adjusted) / denominator


def _period_for(race_date: str) -> str:
    if race_date < VALID_START_DATE:
        return "TRAIN"
    if race_date < TEST_START_DATE:
        return "VALID"
    return "TEST"


def _condition_key(
    p_idx: int,
    m_idx: int,
    o_idx: int,
    mode: str,
) -> Tuple[int, int, int, str]:
    return (p_idx, m_idx, o_idx, mode)


def _condition_text(key: Tuple[int, int, int, str]) -> str:
    p_idx, m_idx, o_idx, mode = key
    p = PROB_WINDOWS[p_idx]
    m = MARKET_WINDOWS[m_idx]
    o = ODDS_WINDOWS[o_idx]
    return (
        f"pr={p[0]}-{p[1]} "
        f"mr={m[0]}-{m[1]} "
        f"odds={o[0]:g}-{o[1]:g} "
        f"select={mode}"
    )


def _matching_rank_windows(
    value: int,
    windows: List[Tuple[int, int]],
) -> List[int]:
    return [
        idx
        for idx, (lower, upper) in enumerate(windows)
        if lower <= value <= upper
    ]


def _matching_odds_windows(value: float) -> List[int]:
    return [
        idx
        for idx, (lower, upper) in enumerate(ODDS_WINDOWS)
        if lower <= value < upper
    ]


PROB_MATCH = {
    rank: _matching_rank_windows(rank, PROB_WINDOWS)
    for rank in range(1, 121)
}
MARKET_MATCH = {
    rank: _matching_rank_windows(rank, MARKET_WINDOWS)
    for rank in range(1, 121)
}


def _fetch_month(
    month_start: str,
    month_end_exclusive: str,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    actual_start = max(START_DATE, month_start)
    actual_end_exclusive = min(
        _next_day(END_DATE),
        month_end_exclusive,
    )
    if actual_start >= actual_end_exclusive:
        return [], [], [], []

    start_rid = actual_start.replace("-", "")
    end_rid = actual_end_exclusive.replace("-", "")

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date >= %s
          and race_date < %s
        order by race_date, venue_id, race_no;
        """,
        (actual_start, actual_end_exclusive),
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
        select race_id, trifecta_ticket, trifecta_payout_yen
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (start_rid, end_rid),
    )

    return races, entries, odds, results


def _best_for_base_conditions(
    ranked: List[Dict[str, Any]],
) -> Dict[Tuple[int, int, int, str], Dict[str, Any]]:
    best: Dict[
        Tuple[int, int, int, str],
        Dict[str, Any],
    ] = {}

    for row in ranked:
        pr = _safe_int(row.get("prob_rank"), 999)
        mr = _safe_int(row.get("market_rank"), 999)
        odd = _safe_float(row.get("odds"), 0.0)

        if pr not in PROB_MATCH or mr not in MARKET_MATCH or odd <= 0:
            continue

        p_idxs = PROB_MATCH[pr]
        m_idxs = MARKET_MATCH[mr]
        o_idxs = _matching_odds_windows(odd)
        if not p_idxs or not m_idxs or not o_idxs:
            continue

        prob = _safe_float(row.get("prob"), 0.0)
        raw_ev = _safe_float(row.get("raw_ev"), 0.0)

        for p_idx in p_idxs:
            for m_idx in m_idxs:
                for o_idx in o_idxs:
                    for mode in SELECT_MODES:
                        key = _condition_key(
                            p_idx, m_idx, o_idx, mode
                        )
                        current = best.get(key)
                        if current is None:
                            best[key] = row
                            continue

                        if mode == "ev":
                            current_key = (
                                _safe_float(current.get("raw_ev"), 0.0),
                                _safe_float(current.get("prob"), 0.0),
                            )
                            new_key = (raw_ev, prob)
                        else:
                            current_key = (
                                _safe_float(current.get("prob"), 0.0),
                                _safe_float(current.get("raw_ev"), 0.0),
                            )
                            new_key = (prob, raw_ev)

                        if new_key > current_key:
                            best[key] = row

    return best


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    if not (
        START_DATE < VALID_START_DATE < TEST_START_DATE <= END_DATE
    ):
        raise RuntimeError(
            "日付条件は "
            "BT_START_DATE < BT_VALID_START_DATE < "
            "BT_TEST_START_DATE <= BT_END_DATE が必要です。"
        )

    print(
        "✅ analyze_candidate_walkforward_phase1_pg.py "
        "VERSION 2026-08-13 three-period-month-stream-v1",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"TRAIN={START_DATE}..{VALID_START_DATE}未満 "
        f"VALID={VALID_START_DATE}..{TEST_START_DATE}未満 "
        f"TEST={TEST_START_DATE}..{END_DATE}",
        flush=True,
    )
    print(
        f"MIN TRAIN/VALID/TEST={MIN_TRAIN}/{MIN_VALID}/{MIN_TEST} "
        f"MIN_MONTH={MIN_MONTH_CANDIDATES}",
        flush=True,
    )
    print(
        f"ROI thresholds TRAIN/VALID/TEST="
        f"{MIN_TRAIN_ROI:.1f}/{MIN_VALID_ROI:.1f}/{MIN_TEST_ROI:.1f} "
        f"MAX_SINGLE_HIT_SHARE={MAX_SINGLE_HIT_SHARE:.1f}% "
        f"MIN_POSITIVE_MONTH_RATIO={MIN_POSITIVE_MONTH_RATIO:.1f}%",
        flush=True,
    )
    print(
        "読み取り専用です。DB更新・LINE通知・本番判定変更はありません。",
        flush=True,
    )
    print(
        "注意: 保存済み確定オッズを使うため、"
        "実運用時点のオッズを完全再現するバックテストではありません。",
        flush=True,
    )

    stats: Dict[
        Tuple[int, int, int, str],
        Dict[str, Dict[str, int]],
    ] = defaultdict(
        lambda: {period: _new_stat() for period in PERIODS}
    )
    monthly: Dict[
        Tuple[int, int, int, str],
        Dict[str, Dict[str, int]],
    ] = defaultdict(lambda: defaultdict(_new_stat))

    total_races = 0
    ready_races = 0
    skipped_entries = 0
    skipped_odds = 0
    skipped_result = 0

    for month_start in _month_starts(START_DATE, END_DATE):
        month_end = _month_end_exclusive(month_start)
        print(
            f"\n=== loading month {month_start[:7]} ===",
            flush=True,
        )

        races, entries_rows, odds_rows, results_rows = _fetch_month(
            month_start, month_end
        )

        entries_by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in entries_rows:
            entries_by[str(row.get("race_id") or "")].append(row)

        odds_by: Dict[str, Dict[str, float]] = defaultdict(dict)
        for row in odds_rows:
            rid = str(row.get("race_id") or "")
            ticket = v24._norm_ticket(row.get("ticket"))
            odd = _safe_float(row.get("odds"), 0.0)
            if rid and ticket and odd > 0:
                odds_by[rid][ticket] = odd

        results_by = {
            str(row.get("race_id") or ""): {
                "ticket": v24._norm_ticket(row.get("trifecta_ticket")),
                "payout": _safe_int(row.get("trifecta_payout_yen"), 0),
            }
            for row in results_rows
            if row.get("race_id")
        }

        month_ready = 0
        month_skipped_odds = 0

        for race in races:
            total_races += 1
            rid = str(race.get("race_id") or "")
            race_date = str(race.get("race_date") or "")[:10]
            venue_id = str(
                race.get("venue_id")
                or race.get("venue_code")
                or ""
            ).zfill(2)

            entries = entries_by.get(rid, [])
            if len(v24._entry_by_lane(entries)) != 6:
                skipped_entries += 1
                continue

            odds = odds_by.get(rid, {})
            ready, _ = v24._validate_odds_snapshot(odds)
            if not ready:
                skipped_odds += 1
                month_skipped_odds += 1
                continue

            result = results_by.get(rid)
            if (
                not result
                or not result.get("ticket")
                or _safe_int(result.get("payout"), 0) <= 0
            ):
                skipped_result += 1
                continue

            ranked = v24._rank_candidates(entries, venue_id, odds)
            selections = _best_for_base_conditions(ranked)
            period = _period_for(race_date)
            month_key = race_date[:7]
            result_ticket = str(result["ticket"])
            payout = int(result["payout"])

            for key, selected in selections.items():
                ticket = str(selected.get("ticket") or "")
                hit = ticket == result_ticket
                _add_result(stats[key][period], hit, payout)
                _add_result(monthly[key][month_key], hit, payout)

            ready_races += 1
            month_ready += 1

        print(
            f"month={month_start[:7]} races={len(races)} "
            f"ready={month_ready} skipped_odds={month_skipped_odds} "
            f"entries_rows={len(entries_rows)} odds_rows={len(odds_rows)}",
            flush=True,
        )

        del races, entries_rows, odds_rows, results_rows
        del entries_by, odds_by, results_by

    print("\n=== data coverage ===", flush=True)
    print(
        f"total_races={total_races} ready_races={ready_races} "
        f"skipped_entries={skipped_entries} "
        f"skipped_odds={skipped_odds} "
        f"skipped_result={skipped_result}",
        flush=True,
    )

    rows: List[Dict[str, Any]] = []

    for key, period_stats in stats.items():
        train = period_stats["TRAIN"]
        valid = period_stats["VALID"]
        test = period_stats["TEST"]

        if (
            train["n"] < MIN_TRAIN
            or valid["n"] < MIN_VALID
            or test["n"] < MIN_TEST
        ):
            continue

        tm = _metrics(train)
        vm = _metrics(valid)
        xm = _metrics(test)

        month_metrics = []
        for month_key, month_stat in sorted(monthly[key].items()):
            if month_stat["n"] < MIN_MONTH_CANDIDATES:
                continue
            mm = _metrics(month_stat)
            month_metrics.append((month_key, mm))

        positive_months = sum(
            1 for _, mm in month_metrics
            if mm["profit"] > 0
        )
        positive_month_ratio = (
            positive_months / len(month_metrics) * 100.0
            if month_metrics
            else 0.0
        )

        worst_roi = min(tm["roi"], vm["roi"], xm["roi"])
        roi_spread = max(tm["roi"], vm["roi"], xm["roi"]) - worst_roi
        max_single_share = max(
            tm["single_hit_share"],
            vm["single_hit_share"],
            xm["single_hit_share"],
        )
        test_hit_lb = _wilson_lower(
            int(test["hits"]), int(test["n"])
        ) * 100.0

        total_profit = (
            tm["profit"] + vm["profit"] + xm["profit"]
        )

        score = (
            worst_roi
            + min(total_profit / 3000.0, 30.0)
            + test_hit_lb * 1.5
            + positive_month_ratio * 0.25
            + min(math.log10(max(test["n"], 1)) * 5.0, 15.0)
            - roi_spread * 0.18
            - max_single_share * 0.12
        )

        rows.append(
            {
                "key": key,
                "text": _condition_text(key),
                "train": tm,
                "valid": vm,
                "test": xm,
                "positive_month_ratio": positive_month_ratio,
                "months_evaluated": len(month_metrics),
                "worst_roi": worst_roi,
                "roi_spread": roi_spread,
                "max_single_share": max_single_share,
                "test_hit_lb": test_hit_lb,
                "total_profit": total_profit,
                "score": score,
            }
        )

    rows.sort(
        key=lambda row: (
            row["score"],
            row["worst_roi"],
            row["test"]["roi"],
            row["test"]["profit"],
            row["test"]["n"],
        ),
        reverse=True,
    )

    print("\n=== top base conditions ===", flush=True)
    for idx, row in enumerate(rows[:TOP_N], start=1):
        print(f"{idx:03d}. {row['text']}", flush=True)
        print(
            "     "
            f"TRAIN n={int(row['train']['n'])} "
            f"hits={int(row['train']['hits'])} "
            f"ROI={row['train']['roi']:.2f}% "
            f"profit={int(row['train']['profit'])} "
            f"single={row['train']['single_hit_share']:.1f}%",
            flush=True,
        )
        print(
            "     "
            f"VALID n={int(row['valid']['n'])} "
            f"hits={int(row['valid']['hits'])} "
            f"ROI={row['valid']['roi']:.2f}% "
            f"profit={int(row['valid']['profit'])} "
            f"single={row['valid']['single_hit_share']:.1f}%",
            flush=True,
        )
        print(
            "     "
            f"TEST n={int(row['test']['n'])} "
            f"hits={int(row['test']['hits'])} "
            f"hit_rate={row['test']['hit_rate']:.2f}% "
            f"ROI={row['test']['roi']:.2f}% "
            f"profit={int(row['test']['profit'])} "
            f"hit_lb={row['test_hit_lb']:.2f}% "
            f"single={row['test']['single_hit_share']:.1f}%",
            flush=True,
        )
        print(
            "     "
            f"months+={row['positive_month_ratio']:.1f}%/"
            f"{row['months_evaluated']} "
            f"worstROI={row['worst_roi']:.2f}% "
            f"spread={row['roi_spread']:.2f}pt "
            f"score={row['score']:.2f}",
            flush=True,
        )

    robust = [
        row for row in rows
        if row["train"]["roi"] >= MIN_TRAIN_ROI
        and row["valid"]["roi"] >= MIN_VALID_ROI
        and row["test"]["roi"] >= MIN_TEST_ROI
        and row["valid"]["profit"] > 0
        and row["test"]["profit"] > 0
        and row["max_single_share"] <= MAX_SINGLE_HIT_SHARE
        and row["positive_month_ratio"] >= MIN_POSITIVE_MONTH_RATIO
    ]

    print("\n=== robust phase1 shortlist ===", flush=True)
    if not robust:
        print(
            "現基準ではPhase 2へ進める基礎条件なし。"
            "閾値を下げる前に上位条件を確認してください。",
            flush=True,
        )
    else:
        for idx, row in enumerate(robust[:TOP_N], start=1):
            print(
                f"{idx:03d}. {row['text']} "
                f"| TRAIN {row['train']['roi']:.1f}% "
                f"| VALID {row['valid']['roi']:.1f}% "
                f"| TEST {row['test']['roi']:.1f}% "
                f"| TEST n={int(row['test']['n'])} "
                f"| months+={row['positive_month_ratio']:.1f}% "
                f"| single<={row['max_single_share']:.1f}% "
                f"| score={row['score']:.1f}",
                flush=True,
            )

    print(
        f"\nPHASE2_BASE_KEYS={len(robust[:30])}",
        flush=True,
    )
    for idx, row in enumerate(robust[:30], start=1):
        p_idx, m_idx, o_idx, mode = row["key"]
        p = PROB_WINDOWS[p_idx]
        m = MARKET_WINDOWS[m_idx]
        o = ODDS_WINDOWS[o_idx]
        print(
            f"PHASE2_{idx:02d}="
            f"{p[0]}-{p[1]}|{m[0]}-{m[1]}|"
            f"{o[0]:g}-{o[1]:g}|{mode}",
            flush=True,
        )

    print("\n=== phase1 analysis finished ===", flush=True)


if __name__ == "__main__":
    main()