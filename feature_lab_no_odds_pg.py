# -*- coding: utf-8 -*-
"""
feature_lab_no_odds_pg.py

過去期間向けのFeature Lab（オッズ不要版）。

比較:
- BASELINE_NO_ODDS
- PREVIOUS_ST_FIXED_NO_ODDS
- RACER_COURSE_NO_ODDS
- PREVIOUS_ST_PLUS_RACER_COURSE_NO_ODDS

特徴:
- v2_odds_trifecta を参照しない
- 120通りすべてを確率順位で評価
- 期間・設定ごとの集計4行だけ保存
- 本番判定・LINE通知・購入処理は変更しない

注意:
- 選手コース別成績は race_date 以前のsnapshotのみ使用
- 過去時点snapshotが無い期間ではRACER_COURSE設定はBaselineと同等になる

Start Command:
    python -u feature_lab_no_odds_pg.py

Variables:
    DATABASE_URL
    FEATURE_LAB_START_DATE=2026-01-01
    FEATURE_LAB_END_DATE=2026-01-31
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    FEATURE_LAB_SAVE=1
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db_pg import execute, fetch_all, upsert_rows
import v22_realtime_decision_engine_pg as base

JST = timezone(timedelta(hours=9))

TODAY = datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("FEATURE_LAB_START_DATE", TODAY).strip()
END_DATE = os.getenv("FEATURE_LAB_END_DATE", TODAY).strip()
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
SAVE_RESULTS = os.getenv("FEATURE_LAB_SAVE", "1").strip().lower() not in {
    "0", "false", "no"
}

PREV_ST_FAST_THRESHOLD = 0.08
PREV_ST_FAST_BONUS = 0.08
PREV_ST_SLOW_THRESHOLD = 0.18
PREV_ST_SLOW_PENALTY = 0.18
RACER_COURSE_WEIGHT = 0.20

CONFIGS = {
    "BASELINE_NO_ODDS": (False, False),
    "PREVIOUS_ST_FIXED_NO_ODDS": (True, False),
    "RACER_COURSE_NO_ODDS": (False, True),
    "PREVIOUS_ST_PLUS_RACER_COURSE_NO_ODDS": (True, True),
}


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
        "trifecta_ticket",
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


def ensure_schema() -> None:
    sqls = [
        "create table if not exists v2_feature_lab_results (id bigserial primary key);",
        "alter table v2_feature_lab_results add column if not exists period_start date;",
        "alter table v2_feature_lab_results add column if not exists period_end date;",
        "alter table v2_feature_lab_results add column if not exists snapshot_label text;",
        "alter table v2_feature_lab_results add column if not exists selector_mode text;",
        "alter table v2_feature_lab_results add column if not exists config_name text;",
        "alter table v2_feature_lab_results add column if not exists evaluated_races integer;",
        "alter table v2_feature_lab_results add column if not exists avg_result_prob_rank numeric;",
        "alter table v2_feature_lab_results add column if not exists top3_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top5_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top10_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists top20_rate numeric;",
        "alter table v2_feature_lab_results add column if not exists improved_races integer;",
        "alter table v2_feature_lab_results add column if not exists worsened_races integer;",
        "alter table v2_feature_lab_results add column if not exists same_races integer;",
        "alter table v2_feature_lab_results add column if not exists previous_st_coverage_races integer;",
        "alter table v2_feature_lab_results add column if not exists racer_course_full_coverage_races integer;",
        "alter table v2_feature_lab_results add column if not exists baseline_avg_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists baseline_top5_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists baseline_top10_delta numeric;",
        "alter table v2_feature_lab_results add column if not exists score numeric;",
        "alter table v2_feature_lab_results add column if not exists config jsonb;",
        "alter table v2_feature_lab_results add column if not exists updated_at timestamptz;",
        """
        create unique index if not exists uq_v2_feature_lab_results
        on v2_feature_lab_results(
            period_start,
            period_end,
            snapshot_label,
            selector_mode,
            config_name
        );
        """,
    ]
    for sql in sqls:
        execute(sql)


def group_by_race(
    rows: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("race_id")), []).append(row)
    return grouped


def previous_st_adjustment(
    condition: Optional[Dict[str, Any]],
) -> float:
    if not condition or condition.get("previous_st") is None:
        return 0.0

    st = sf(condition.get("previous_st"), 0.18)
    if st <= PREV_ST_FAST_THRESHOLD:
        return PREV_ST_FAST_BONUS
    if st >= PREV_ST_SLOW_THRESHOLD:
        return -PREV_ST_SLOW_PENALTY
    return 0.0


def racer_course_adjustment(
    stat: Optional[Dict[str, Any]],
) -> float:
    if not stat:
        return 0.0

    entry_rate = sf(stat.get("entry_rate"), 16.67)
    top3_rate = sf(stat.get("top3_rate"), 33.33)
    avg_st = sf(stat.get("avg_st"), 0.18)

    top3_component = max(
        -1.0,
        min(1.0, (top3_rate - 33.33) / 40.0),
    )
    st_component = max(
        -1.0,
        min(1.0, (0.18 - avg_st) / 0.08),
    )
    entry_component = max(
        -1.0,
        min(1.0, (entry_rate - 16.67) / 20.0),
    )

    combined = (
        top3_component * 0.55
        + st_component * 0.30
        + entry_component * 0.15
    )
    return combined * RACER_COURSE_WEIGHT


def latest_course_stat(
    rows_by_key: Dict[Tuple[int, int], List[Dict[str, Any]]],
    racer_number: int,
    course: int,
    race_date: str,
) -> Optional[Dict[str, Any]]:
    rows = rows_by_key.get((racer_number, course), [])
    for row in rows:
        if str(row.get("snapshot_date")) <= race_date:
            return row
    return None


def make_rank_map(
    entries: List[Dict[str, Any]],
    venue_id: str,
    race_date: str,
    conditions: Dict[int, Dict[str, Any]],
    course_stats: Dict[Tuple[int, int], List[Dict[str, Any]]],
    use_previous_st: bool,
    use_racer_course: bool,
) -> Tuple[Dict[str, int], int, int]:
    by_lane = base._entry_by_lane(entries)

    raw: Dict[int, float] = {}
    previous_st_filled = 0
    course_coverage = 0

    for lane in range(1, 7):
        entry = by_lane[lane]
        score = base._lane_raw_strength(entry, lane, venue_id)

        if use_previous_st:
            condition = conditions.get(lane)
            if condition and condition.get("previous_st") is not None:
                previous_st_filled += 1
            score += previous_st_adjustment(condition)

        if use_racer_course:
            racer_number = si(entry.get("racer_number"))
            stat = latest_course_stat(
                course_stats,
                racer_number,
                lane,
                race_date,
            )
            if stat:
                course_coverage += 1
            score += racer_course_adjustment(stat)

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
                probability = (
                    p_first
                    * p_second
                    * (weights[third] / third_total)
                )
                rows.append((ticket, probability))

    rows.sort(key=lambda item: item[1], reverse=True)

    return (
        {
            ticket: rank
            for rank, (ticket, _) in enumerate(rows, start=1)
        },
        previous_st_filled,
        course_coverage,
    )


def metrics(ranks: List[int]) -> Dict[str, float]:
    count = len(ranks)
    if count == 0:
        return {
            "n": 0,
            "avg": 999.0,
            "top3": 0.0,
            "top5": 0.0,
            "top10": 0.0,
            "top20": 0.0,
        }

    return {
        "n": count,
        "avg": sum(ranks) / count,
        "top3": sum(rank <= 3 for rank in ranks) / count * 100.0,
        "top5": sum(rank <= 5 for rank in ranks) / count * 100.0,
        "top10": sum(rank <= 10 for rank in ranks) / count * 100.0,
        "top20": sum(rank <= 20 for rank in ranks) / count * 100.0,
    }


def score_vs_baseline(
    current: Dict[str, float],
    baseline: Dict[str, float],
) -> float:
    return (
        (baseline["avg"] - current["avg"])
        + (current["top5"] - baseline["top5"]) * 0.20
        + (current["top10"] - baseline["top10"]) * 0.10
        + (current["top20"] - baseline["top20"]) * 0.05
    )


def main() -> None:
    print(
        "✅ feature_lab_no_odds_pg.py "
        "VERSION 2026-07-16 no-odds-history-v1",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    ensure_schema()

    print(
        f"PERIOD={START_DATE}..{END_DATE} "
        f"SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE}",
        flush=True,
    )
    print(
        "オッズ不要版です。本番判定・LINE通知・購入処理は変更しません。",
        flush=True,
    )

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
    race_ids = [str(row.get("race_id")) for row in races]

    if not race_ids:
        print("対象レースはありません。", flush=True)
        return

    entries_by = group_by_race(
        fetch_all(
            """
            select *
            from v2_race_entries
            where race_id = any(%s)
            order by race_id, lane;
            """,
            (race_ids,),
        )
    )

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
    conditions_by_rows = group_by_race(condition_rows)
    conditions_by = {
        race_id: {
            si(row.get("lane")): row
            for row in rows
        }
        for race_id, rows in conditions_by_rows.items()
    }

    course_rows = fetch_all(
        """
        select
            racer_number,
            course,
            snapshot_date,
            entry_rate,
            top3_rate,
            avg_st
        from v2_racer_course_stats_snapshots
        where snapshot_date <= %s
        order by racer_number, course, snapshot_date desc;
        """,
        (END_DATE,),
    )
    course_stats: Dict[
        Tuple[int, int],
        List[Dict[str, Any]],
    ] = {}
    for row in course_rows:
        course_stats.setdefault(
            (
                si(row.get("racer_number")),
                si(row.get("course")),
            ),
            [],
        ).append(row)

    next_day = (
        datetime.strptime(END_DATE, "%Y-%m-%d")
        + timedelta(days=1)
    ).strftime("%Y%m%d")

    results: Dict[str, str] = {}
    for row in fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (START_DATE.replace("-", ""), next_day),
    ):
        winning = result_ticket(row)
        if winning:
            results[str(row.get("race_id"))] = winning

    ranks_by_config = {
        name: []
        for name in CONFIGS
    }
    improved = {
        name: 0
        for name in CONFIGS
    }
    worsened = {
        name: 0
        for name in CONFIGS
    }
    same = {
        name: 0
        for name in CONFIGS
    }

    eligible_races = 0
    previous_st_coverage_races = 0
    racer_course_full_coverage_races = 0
    missing_entries = 0
    missing_result = 0

    for race in races:
        race_id = str(race.get("race_id"))
        entries = entries_by.get(race_id, [])
        winning_ticket = results.get(race_id)

        if len(base._entry_by_lane(entries)) != 6:
            missing_entries += 1
            continue
        if not winning_ticket:
            missing_result += 1
            continue

        eligible_races += 1
        venue_id = str(
            race.get("venue_id")
            or race.get("venue_code")
            or ""
        ).zfill(2)
        race_date = str(race.get("race_date"))

        race_ranks: Dict[str, int] = {}

        for name, (
            use_previous_st,
            use_racer_course,
        ) in CONFIGS.items():
            rank_map, st_filled, course_coverage = make_rank_map(
                entries,
                venue_id,
                race_date,
                conditions_by.get(race_id, {}),
                course_stats,
                use_previous_st,
                use_racer_course,
            )
            race_ranks[name] = rank_map.get(
                winning_ticket,
                999,
            )

            if (
                name == "PREVIOUS_ST_FIXED_NO_ODDS"
                and st_filled > 0
            ):
                previous_st_coverage_races += 1

            if (
                name == "RACER_COURSE_NO_ODDS"
                and course_coverage == 6
            ):
                racer_course_full_coverage_races += 1

        baseline_rank = race_ranks["BASELINE_NO_ODDS"]

        for name in CONFIGS:
            current_rank = race_ranks[name]
            ranks_by_config[name].append(current_rank)

            if current_rank < baseline_rank:
                improved[name] += 1
            elif current_rank > baseline_rank:
                worsened[name] += 1
            else:
                same[name] += 1

    baseline_metrics = metrics(
        ranks_by_config["BASELINE_NO_ODDS"]
    )

    print(
        f"eligible_races={eligible_races} "
        f"missing_entries={missing_entries} "
        f"missing_result={missing_result}",
        flush=True,
    )
    print(
        f"previous_st_coverage_races="
        f"{previous_st_coverage_races}",
        flush=True,
    )
    print(
        f"racer_course_full_coverage_races="
        f"{racer_course_full_coverage_races}",
        flush=True,
    )

    now_iso = datetime.now(JST).isoformat()
    save_rows = []
    report_rows = []

    for name in CONFIGS:
        current = metrics(ranks_by_config[name])

        avg_delta = (
            0.0
            if name == "BASELINE_NO_ODDS"
            else current["avg"] - baseline_metrics["avg"]
        )
        top5_delta = (
            0.0
            if name == "BASELINE_NO_ODDS"
            else current["top5"] - baseline_metrics["top5"]
        )
        top10_delta = (
            0.0
            if name == "BASELINE_NO_ODDS"
            else current["top10"] - baseline_metrics["top10"]
        )
        score = (
            0.0
            if name == "BASELINE_NO_ODDS"
            else score_vs_baseline(
                current,
                baseline_metrics,
            )
        )

        report_rows.append(
            (
                score,
                name,
                current,
                avg_delta,
                top5_delta,
                top10_delta,
            )
        )

        save_rows.append(
            {
                "period_start": START_DATE,
                "period_end": END_DATE,
                "snapshot_label": SNAPSHOT_LABEL,
                "selector_mode": SELECTOR_MODE,
                "config_name": name,
                "evaluated_races": current["n"],
                "avg_result_prob_rank": current["avg"],
                "top3_rate": current["top3"],
                "top5_rate": current["top5"],
                "top10_rate": current["top10"],
                "top20_rate": current["top20"],
                "improved_races": improved[name],
                "worsened_races": worsened[name],
                "same_races": same[name],
                "previous_st_coverage_races":
                    previous_st_coverage_races,
                "racer_course_full_coverage_races":
                    racer_course_full_coverage_races,
                "baseline_avg_delta": avg_delta,
                "baseline_top5_delta": top5_delta,
                "baseline_top10_delta": top10_delta,
                "score": score,
                "config": {
                    "mode": "no_odds_all_120_tickets",
                    "previous_st": {
                        "fast_threshold":
                            PREV_ST_FAST_THRESHOLD,
                        "fast_bonus":
                            PREV_ST_FAST_BONUS,
                        "slow_threshold":
                            PREV_ST_SLOW_THRESHOLD,
                        "slow_penalty":
                            PREV_ST_SLOW_PENALTY,
                    },
                    "racer_course_weight":
                        RACER_COURSE_WEIGHT,
                },
                "updated_at": now_iso,
            }
        )

    saved = (
        upsert_rows(
            "v2_feature_lab_results",
            save_rows,
            [
                "period_start",
                "period_end",
                "snapshot_label",
                "selector_mode",
                "config_name",
            ],
        )
        if SAVE_RESULTS
        else 0
    )

    print("=== FEATURE LAB NO-ODDS RESULTS ===", flush=True)

    for (
        score,
        name,
        current,
        avg_delta,
        top5_delta,
        top10_delta,
    ) in sorted(
        report_rows,
        key=lambda row: (
            row[0],
            -row[2]["avg"],
            row[2]["top5"],
            row[2]["top10"],
        ),
        reverse=True,
    ):
        print(
            f"{name}: "
            f"races={current['n']} "
            f"avg={current['avg']:.3f} "
            f"top3={current['top3']:.2f}% "
            f"top5={current['top5']:.2f}% "
            f"top10={current['top10']:.2f}% "
            f"top20={current['top20']:.2f}% "
            f"avg_delta={avg_delta:+.3f} "
            f"top5_delta={top5_delta:+.2f}pt "
            f"top10_delta={top10_delta:+.2f}pt "
            f"improved={improved[name]} "
            f"worsened={worsened[name]} "
            f"same={same[name]} "
            f"score={score:+.3f}",
            flush=True,
        )

    print(f"saved_summary_rows={saved}", flush=True)
    print(
        "注意: 1月以前の選手コース別snapshotが無ければ、"
        "RACER_COURSE設定はBaselineと同等です。",
        flush=True,
    )
    print(
        "判定目安: 前走STは300R以上かつ、平均順位改善・"
        "Top5非悪化・Top10非悪化・改善R>悪化Rで採用候補。",
        flush=True,
    )
    print("=== feature lab no-odds finished ===", flush=True)


if __name__ == "__main__":
    main()