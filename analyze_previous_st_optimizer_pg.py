# -*- coding: utf-8 -*-
"""
analyze_previous_st_optimizer_pg.py

前走ST補正の閾値・重みを総当たり評価します。
読み取り専用です。本番判定・LINE通知・購入処理は変更しません。

評価指標:
- 的中組の平均予測順位
- Top3 / Top5 / Top10 / Top20
- Baselineとの差
- 改善レース / 悪化レース / 同順位

Start Command:
    python -u analyze_previous_st_optimizer_pg.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD
    SNAPSHOT_LABEL=final_ab
    MIN_CONDITION_COVERAGE=6

任意:
    ST_OPT_FAST_BONUS_MIN=0.02
    ST_OPT_FAST_BONUS_MAX=0.20
    ST_OPT_FAST_BONUS_STEP=0.02
    ST_OPT_SLOW_PENALTY_MIN=0.02
    ST_OPT_SLOW_PENALTY_MAX=0.20
    ST_OPT_SLOW_PENALTY_STEP=0.02
    ST_OPT_TOP_N=30
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all
import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
MIN_CONDITION_COVERAGE = int(os.getenv("MIN_CONDITION_COVERAGE", "6"))

FAST_BONUS_MIN = float(os.getenv("ST_OPT_FAST_BONUS_MIN", "0.02"))
FAST_BONUS_MAX = float(os.getenv("ST_OPT_FAST_BONUS_MAX", "0.20"))
FAST_BONUS_STEP = float(os.getenv("ST_OPT_FAST_BONUS_STEP", "0.02"))

SLOW_PENALTY_MIN = float(os.getenv("ST_OPT_SLOW_PENALTY_MIN", "0.02"))
SLOW_PENALTY_MAX = float(os.getenv("ST_OPT_SLOW_PENALTY_MAX", "0.20"))
SLOW_PENALTY_STEP = float(os.getenv("ST_OPT_SLOW_PENALTY_STEP", "0.02"))

TOP_N = int(os.getenv("ST_OPT_TOP_N", "30"))

FAST_THRESHOLDS = [0.08, 0.10, 0.12, 0.14, 0.15]
SLOW_THRESHOLDS = [0.18, 0.20, 0.22, 0.25]


@dataclass(frozen=True)
class Config:
    fast_threshold: float
    fast_bonus: float
    slow_threshold: float
    slow_penalty: float


def sf(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def si(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def norm_ticket(value: Any) -> str:
    nums = re.findall(r"[1-6]", str(value or ""))
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return ""


def result_ticket(row: Dict[str, Any]) -> str:
    for key in (
        "result_trifecta",
        "trifecta",
        "winning_ticket",
        "result",
        "finish_order",
    ):
        ticket = norm_ticket(row.get(key))
        if ticket:
            return ticket

    first = si(
        row.get("first_lane")
        or row.get("first")
        or row.get("rank1")
        or row.get("first_place")
    )
    second = si(
        row.get("second_lane")
        or row.get("second")
        or row.get("rank2")
        or row.get("second_place")
    )
    third = si(
        row.get("third_lane")
        or row.get("third")
        or row.get("rank3")
        or row.get("third_place")
    )

    if all(1 <= x <= 6 for x in (first, second, third)):
        return f"{first}-{second}-{third}"
    return ""


def decimal_range(start: float, stop: float, step: float) -> List[float]:
    values: List[float] = []
    current = start
    while current <= stop + 1e-9:
        values.append(round(current, 10))
        current += step
    return values


def rank_rows(
    entries: List[Dict[str, Any]],
    venue_id: str,
    odds: Dict[str, float],
    conditions: Dict[int, Dict[str, Any]],
    config: Config | None,
) -> Dict[str, int]:
    by_lane = base._entry_by_lane(entries)
    raw: Dict[int, float] = {}

    for lane in range(1, 7):
        score = base._lane_raw_strength(
            by_lane[lane],
            lane,
            venue_id,
        )

        if config is not None:
            condition = conditions.get(lane, {})
            previous_st = condition.get("previous_st")

            if previous_st is not None:
                st = sf(previous_st, 0.18)

                if st <= config.fast_threshold:
                    score += config.fast_bonus
                elif st >= config.slow_threshold:
                    score -= config.slow_penalty

        raw[lane] = score

    weights = {
        lane: math.exp(raw[lane] / base.PROB_TEMP)
        for lane in range(1, 7)
    }
    total = sum(weights.values())

    rows: List[Tuple[str, float]] = []

    for first in range(1, 7):
        p_first = weights[first] / total
        second_total = total - weights[first]

        for second in range(1, 7):
            if second == first:
                continue

            p_second = weights[second] / second_total
            third_total = second_total - weights[second]

            for third in range(1, 7):
                if third in (first, second):
                    continue

                ticket = f"{first}-{second}-{third}"
                odd = sf(odds.get(ticket), 0.0)
                if odd <= 0:
                    continue

                probability = (
                    p_first
                    * p_second
                    * (weights[third] / third_total)
                )
                rows.append((ticket, probability))

    rows.sort(key=lambda item: item[1], reverse=True)
    return {
        ticket: rank
        for rank, (ticket, _) in enumerate(rows, start=1)
    }


def evaluate_ranks(ranks: List[int]) -> Dict[str, float]:
    count = len(ranks)
    if count == 0:
        return {
            "races": 0,
            "avg_rank": 999.0,
            "top3": 0.0,
            "top5": 0.0,
            "top10": 0.0,
            "top20": 0.0,
        }

    return {
        "races": count,
        "avg_rank": sum(ranks) / count,
        "top3": sum(rank <= 3 for rank in ranks) / count * 100.0,
        "top5": sum(rank <= 5 for rank in ranks) / count * 100.0,
        "top10": sum(rank <= 10 for rank in ranks) / count * 100.0,
        "top20": sum(rank <= 20 for rank in ranks) / count * 100.0,
    }


def composite_score(
    metrics: Dict[str, float],
    baseline: Dict[str, float],
) -> float:
    """
    平均順位を最重視しつつ、Top5 / Top10 / Top20も加点する。
    """
    return (
        (baseline["avg_rank"] - metrics["avg_rank"])
        + (metrics["top5"] - baseline["top5"]) * 0.20
        + (metrics["top10"] - baseline["top10"]) * 0.10
        + (metrics["top20"] - baseline["top20"]) * 0.05
    )


def main() -> None:
    print(
        "✅ analyze_previous_st_optimizer_pg.py "
        "VERSION 2026-07-15 previous-st-grid-v1",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"TARGET_DATE={TARGET_DATE} "
        f"SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"MIN_CONDITION_COVERAGE={MIN_CONDITION_COVERAGE}",
        flush=True,
    )
    print(
        "読み取り専用です。本番判定・LINE通知・購入処理は変更しません。",
        flush=True,
    )

    races = fetch_all(
        """
        select *
        from v2_races
        where race_date = %s
        order by venue_id, race_no;
        """,
        (TARGET_DATE,),
    )
    race_ids = [str(row.get("race_id")) for row in races]

    entries_rows = fetch_all(
        """
        select *
        from v2_race_entries
        where race_id = any(%s)
        order by race_id, lane;
        """,
        (race_ids,),
    )
    entries_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for row in entries_rows:
        entries_by_race.setdefault(
            str(row.get("race_id")),
            [],
        ).append(row)

    odds_rows = fetch_all(
        """
        select race_id, ticket, odds
        from v2_odds_trifecta
        where race_id = any(%s);
        """,
        (race_ids,),
    )
    odds_by_race: Dict[str, Dict[str, float]] = {}
    for row in odds_rows:
        ticket = norm_ticket(row.get("ticket"))
        odds = sf(row.get("odds"), 0.0)
        if ticket and odds > 0:
            odds_by_race.setdefault(
                str(row.get("race_id")),
                {},
            )[ticket] = odds

    condition_rows = fetch_all(
        """
        select *
        from v2_realtime_racer_condition_snapshots
        where race_id = any(%s)
          and snapshot_label = %s
        order by race_id, lane;
        """,
        (race_ids, SNAPSHOT_LABEL),
    )
    conditions_by_race: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for row in condition_rows:
        conditions_by_race.setdefault(
            str(row.get("race_id")),
            {},
        )[si(row.get("lane"))] = row

    next_day = (
        datetime.strptime(TARGET_DATE, "%Y-%m-%d")
        + timedelta(days=1)
    ).strftime("%Y%m%d")

    result_rows = fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (TARGET_DATE.replace("-", ""), next_day),
    )
    results = {
        str(row.get("race_id")): result_ticket(row)
        for row in result_rows
    }
    results = {
        race_id: ticket
        for race_id, ticket in results.items()
        if ticket
    }

    eligible_data = []

    for race in races:
        race_id = str(race.get("race_id"))
        entries = entries_by_race.get(race_id, [])
        odds = odds_by_race.get(race_id, {})
        conditions = conditions_by_race.get(race_id, {})
        winning_ticket = results.get(race_id)

        if len(base._entry_by_lane(entries)) != 6:
            continue
        if len(odds) < 100:
            continue
        if len(conditions) < MIN_CONDITION_COVERAGE:
            continue
        if not winning_ticket:
            continue

        eligible_data.append(
            (
                race_id,
                str(
                    race.get("venue_id")
                    or race.get("venue_code")
                    or ""
                ).zfill(2),
                entries,
                odds,
                conditions,
                winning_ticket,
            )
        )

    print(f"eligible_races={len(eligible_data)}", flush=True)

    baseline_ranks: List[int] = []

    for (
        _race_id,
        venue_id,
        entries,
        odds,
        conditions,
        winning_ticket,
    ) in eligible_data:
        rank_map = rank_rows(
            entries,
            venue_id,
            odds,
            conditions,
            None,
        )
        baseline_ranks.append(
            rank_map.get(winning_ticket, 999)
        )

    baseline_metrics = evaluate_ranks(baseline_ranks)

    print("\n=== BASELINE ===", flush=True)
    print(
        f"races={baseline_metrics['races']} "
        f"avg={baseline_metrics['avg_rank']:.3f} "
        f"top3={baseline_metrics['top3']:.2f}% "
        f"top5={baseline_metrics['top5']:.2f}% "
        f"top10={baseline_metrics['top10']:.2f}% "
        f"top20={baseline_metrics['top20']:.2f}%",
        flush=True,
    )

    fast_bonuses = decimal_range(
        FAST_BONUS_MIN,
        FAST_BONUS_MAX,
        FAST_BONUS_STEP,
    )
    slow_penalties = decimal_range(
        SLOW_PENALTY_MIN,
        SLOW_PENALTY_MAX,
        SLOW_PENALTY_STEP,
    )

    configs = [
        Config(
            fast_threshold=fast_threshold,
            fast_bonus=fast_bonus,
            slow_threshold=slow_threshold,
            slow_penalty=slow_penalty,
        )
        for fast_threshold in FAST_THRESHOLDS
        for fast_bonus in fast_bonuses
        for slow_threshold in SLOW_THRESHOLDS
        for slow_penalty in slow_penalties
        if fast_threshold < slow_threshold
    ]

    print(
        f"grid_configs={len(configs)} "
        f"fast_thresholds={FAST_THRESHOLDS} "
        f"slow_thresholds={SLOW_THRESHOLDS}",
        flush=True,
    )

    results_ranked = []

    for index, config in enumerate(configs, start=1):
        ranks: List[int] = []
        improved = 0
        worsened = 0
        same = 0

        for race_index, (
            _race_id,
            venue_id,
            entries,
            odds,
            conditions,
            winning_ticket,
        ) in enumerate(eligible_data):
            rank_map = rank_rows(
                entries,
                venue_id,
                odds,
                conditions,
                config,
            )
            rank = rank_map.get(winning_ticket, 999)
            baseline_rank = baseline_ranks[race_index]

            ranks.append(rank)

            if rank < baseline_rank:
                improved += 1
            elif rank > baseline_rank:
                worsened += 1
            else:
                same += 1

        metrics = evaluate_ranks(ranks)
        score = composite_score(
            metrics,
            baseline_metrics,
        )

        results_ranked.append(
            {
                "config": config,
                "metrics": metrics,
                "score": score,
                "improved": improved,
                "worsened": worsened,
                "same": same,
            }
        )

        if index % 250 == 0 or index == len(configs):
            print(
                f"progress={index}/{len(configs)}",
                flush=True,
            )

    results_ranked.sort(
        key=lambda row: (
            row["score"],
            -row["metrics"]["avg_rank"],
            row["metrics"]["top5"],
            row["metrics"]["top10"],
        ),
        reverse=True,
    )

    print("\n=== TOP CONFIGS ===", flush=True)

    for rank, row in enumerate(
        results_ranked[:TOP_N],
        start=1,
    ):
        config: Config = row["config"]
        metrics = row["metrics"]

        print(
            f"{rank:02d}. "
            f"fast<={config.fast_threshold:.2f} "
            f"bonus=+{config.fast_bonus:.2f} "
            f"slow>={config.slow_threshold:.2f} "
            f"penalty=-{config.slow_penalty:.2f} "
            f"score={row['score']:+.3f} "
            f"avg={metrics['avg_rank']:.3f} "
            f"top5={metrics['top5']:.2f}% "
            f"top10={metrics['top10']:.2f}% "
            f"top20={metrics['top20']:.2f}% "
            f"improved={row['improved']} "
            f"worsened={row['worsened']} "
            f"same={row['same']}",
            flush=True,
        )

    strict_candidates = [
        row
        for row in results_ranked
        if (
            row["metrics"]["avg_rank"]
            < baseline_metrics["avg_rank"]
            and row["metrics"]["top5"]
            >= baseline_metrics["top5"]
            and row["metrics"]["top10"]
            >= baseline_metrics["top10"]
        )
    ]

    print("\n=== STRICT IMPROVEMENT ===", flush=True)
    print(
        f"strict_candidate_configs={len(strict_candidates)}",
        flush=True,
    )

    for rank, row in enumerate(
        strict_candidates[:20],
        start=1,
    ):
        config: Config = row["config"]
        metrics = row["metrics"]

        print(
            f"{rank:02d}. "
            f"fast<={config.fast_threshold:.2f} "
            f"bonus=+{config.fast_bonus:.2f} "
            f"slow>={config.slow_threshold:.2f} "
            f"penalty=-{config.slow_penalty:.2f} "
            f"avg={metrics['avg_rank']:.3f} "
            f"top5={metrics['top5']:.2f}% "
            f"top10={metrics['top10']:.2f}%",
            flush=True,
        )

    print(
        "判定目安: STRICT IMPROVEMENTが0件なら、"
        "前走STは本番採用せずデータ蓄積を継続します。",
        flush=True,
    )
    print("=== previous ST optimizer finished ===", flush=True)


if __name__ == "__main__":
    main()