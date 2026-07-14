# -*- coding: utf-8 -*-
"""
analyze_exhibition_scoring_pg.py

final_ab の展示・気象スナップショットを使い、
現行の基礎能力モデルへ展示補正を加えた場合の順位改善を比較します。

読み取り専用です。LINE送信・DB更新は行いません。

Railway Start Command:
    python -u analyze_exhibition_scoring_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    ANALYZE_START_DATE=2026-07-05
    ANALYZE_END_DATE=2026-07-14
    SNAPSHOT_LABEL=final_ab
    SCORE_SAMPLE_LIMIT=30
"""

from __future__ import annotations

import itertools
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

START_DATE = os.getenv("ANALYZE_START_DATE", "2026-07-05")
END_DATE = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SAMPLE_LIMIT = max(1, int(os.getenv("SCORE_SAMPLE_LIMIT", "30")))

PROB_TEMP = 2.20
CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}


def sf(v: Any, d: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return d
        return float(str(v).replace(",", ""))
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(str(v).replace(",", "")))
    except Exception:
        return d


def normalize_ticket(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    nums = re.findall(r"(?<!\d)([1-6])(?!\d)", s)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    compact = re.sub(r"\D", "", s)
    if len(compact) >= 3 and all(c in "123456" for c in compact[:3]):
        return f"{compact[0]}-{compact[1]}-{compact[2]}"
    return ""


def base_lane_strength(entry: Dict[str, Any], lane: int, venue_id: str) -> float:
    cls = si(entry.get("racer_class"), 2)
    cls_w = CLASS_WEIGHT.get(cls, 0.55)
    win_rate = sf(entry.get("national_win_rate"), 0.0)
    nat2 = sf(entry.get("national_place2_rate"), 32.0)
    loc2 = sf(entry.get("local_place2_rate"), 30.0)
    avg_st = sf(entry.get("avg_st"), 0.18)
    course_bias = VENUE_COURSE_BIAS.get(venue_id, DEFAULT_COURSE_BIAS).get(
        lane, DEFAULT_COURSE_BIAS[lane]
    )
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))

    # 現行v24と同じ固定モーター・ボート値
    return (
        cls_w * 1.00
        + win_rate * 0.16
        + (nat2 / 100.0) * 0.90
        + (loc2 / 100.0) * 0.55
        + (33.0 / 100.0) * 0.45
        + (34.0 / 100.0) * 0.25
        + st_score * 0.35
        + course_bias * 0.22
    )


def rank_centered(rank: int) -> float:
    """
    1位=+1.0, 2位=+0.6, 3位=+0.2,
    4位=-0.2, 5位=-0.6, 6位=-1.0
    """
    return {
        1: 1.0,
        2: 0.6,
        3: 0.2,
        4: -0.2,
        5: -0.6,
        6: -1.0,
    }.get(rank, 0.0)


def adjusted_lane_strength(
    entry: Dict[str, Any],
    exhibition: Dict[str, Any],
    lane: int,
    venue_id: str,
    wind_speed: float,
    config: Tuple[float, float, float],
) -> float:
    ex_weight, st_weight, strong_wind_lane1_penalty = config
    score = base_lane_strength(entry, lane, venue_id)

    ex_rank = si(exhibition.get("exhibition_time_rank"), 0)
    st_rank = si(exhibition.get("start_timing_rank"), 0)

    score += ex_weight * rank_centered(ex_rank)
    score += st_weight * rank_centered(st_rank)

    if lane == 1 and wind_speed >= 5.0:
        score -= strong_wind_lane1_penalty

    return score


def ticket_probabilities(
    entries: List[Dict[str, Any]],
    exhibitions: Dict[int, Dict[str, Any]],
    venue_id: str,
    wind_speed: float,
    config: Tuple[float, float, float],
) -> Dict[str, float]:
    by_lane = {si(e.get("lane")): e for e in entries}
    if len(by_lane) != 6 or len(exhibitions) != 6:
        return {}

    raw = {
        lane: adjusted_lane_strength(
            by_lane[lane],
            exhibitions.get(lane, {}),
            lane,
            venue_id,
            wind_speed,
            config,
        )
        for lane in range(1, 7)
    }

    weights = {lane: math.exp(raw[lane] / PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    probs: Dict[str, float] = {}

    for a in range(1, 7):
        pa = weights[a] / total
        total_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / total_b
            total_c = total_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                pc = weights[c] / total_c
                probs[f"{a}-{b}-{c}"] = pa * pb * pc

    return probs


def ranks_from_probs(probs: Dict[str, float]) -> Dict[str, int]:
    return {
        ticket: rank
        for rank, (ticket, _) in enumerate(
            sorted(probs.items(), key=lambda x: x[1], reverse=True),
            start=1,
        )
    }


def load_data() -> Tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Dict[int, Dict[str, Any]]],
    Dict[str, Dict[str, Any]],
    Dict[str, str],
]:
    entry_rows = fetch_all(
        """
        select
            r.race_id,
            r.race_date,
            coalesce(r.venue_id, r.venue_code) as venue_id,
            r.race_no,
            e.lane,
            e.racer_class,
            e.national_win_rate,
            e.national_place2_rate,
            e.local_place2_rate,
            e.avg_st
        from v2_races r
        join v2_race_entries e on e.race_id = r.race_id
        where r.race_date >= %s
          and r.race_date <= %s
        order by r.race_id, e.lane;
        """,
        (START_DATE, END_DATE),
    )

    exhibition_rows = fetch_all(
        """
        select
            race_id,
            lane,
            exhibition_time,
            exhibition_time_rank,
            exhibition_time_diff,
            start_timing,
            start_timing_rank,
            start_timing_diff,
            exhibition_course,
            tilt,
            tilt_change
        from v2_realtime_exhibition_snapshots
        where race_date >= %s
          and race_date <= %s
          and snapshot_label = %s
        order by race_id, lane;
        """,
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )

    weather_rows = fetch_all(
        """
        select race_id, wind_speed_m, wind_direction, wave_height_cm
        from v2_realtime_weather_snapshots
        where race_date >= %s
          and race_date <= %s
          and snapshot_label = %s;
        """,
        (START_DATE, END_DATE, SNAPSHOT_LABEL),
    )

    result_rows = fetch_all(
        """
        select race_id, first_lane, second_lane, third_lane, trifecta_ticket
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (
            START_DATE.replace("-", ""),
            (datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d"),
        ),
    )

    races: Dict[str, Dict[str, Any]] = {}
    for r in entry_rows:
        rid = str(r.get("race_id") or "")
        x = races.setdefault(
            rid,
            {
                "race_id": rid,
                "race_date": str(r.get("race_date") or ""),
                "venue_id": str(r.get("venue_id") or "").zfill(2),
                "race_no": si(r.get("race_no")),
                "entries": [],
            },
        )
        x["entries"].append(r)

    exhibitions: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
    for r in exhibition_rows:
        rid = str(r.get("race_id") or "")
        lane = si(r.get("lane"))
        if rid and 1 <= lane <= 6:
            exhibitions[rid][lane] = r

    weather = {
        str(r.get("race_id")): r
        for r in weather_rows
        if r.get("race_id")
    }

    results: Dict[str, str] = {}
    for r in result_rows:
        a = si(r.get("first_lane"))
        b = si(r.get("second_lane"))
        c = si(r.get("third_lane"))
        if all(1 <= x <= 6 for x in (a, b, c)):
            ticket = f"{a}-{b}-{c}"
        else:
            ticket = normalize_ticket(r.get("trifecta_ticket"))
        if ticket:
            results[str(r.get("race_id"))] = ticket

    return races, dict(exhibitions), weather, results


def evaluate(
    config: Tuple[float, float, float],
    races: Dict[str, Dict[str, Any]],
    exhibitions: Dict[str, Dict[int, Dict[str, Any]]],
    weather: Dict[str, Dict[str, Any]],
    results: Dict[str, str],
) -> Counter:
    stat = Counter()

    for rid, race in races.items():
        entries = race["entries"]
        ex = exhibitions.get(rid, {})
        w = weather.get(rid, {})
        result_ticket = results.get(rid)

        if len(entries) != 6 or len(ex) != 6 or not result_ticket:
            continue

        wind_speed = sf(w.get("wind_speed_m"), 0.0)
        probs = ticket_probabilities(
            entries,
            ex,
            race["venue_id"],
            wind_speed,
            config,
        )
        if not probs:
            continue

        ranks = ranks_from_probs(probs)
        result_rank = ranks.get(result_ticket, 999)

        stat["races"] += 1
        stat["rank_sum"] += result_rank
        for k in (1, 3, 5, 10, 20):
            stat[f"top{k}"] += int(result_rank <= k)

    return stat


def metric_tuple(stat: Counter) -> Tuple[float, float, float, float]:
    n = stat["races"]
    if not n:
        return (999.0, 0.0, 0.0, 0.0)
    avg_rank = stat["rank_sum"] / n
    top5 = stat["top5"] / n
    top10 = stat["top10"] / n
    top20 = stat["top20"] / n
    return (avg_rank, top5, top10, top20)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ analyze_exhibition_scoring_pg.py VERSION 2026-07-15", flush=True)
    print(
        f"PERIOD={START_DATE}..{END_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL}",
        flush=True,
    )
    print("読み取り専用です。", flush=True)

    races, exhibitions, weather, results = load_data()

    print(
        f"loaded races={len(races)} exhibition_races={len(exhibitions)} "
        f"weather={len(weather)} results={len(results)}",
        flush=True,
    )

    # 0,0,0 が現行基準
    configs = list(
        itertools.product(
            [0.0, 0.05, 0.10, 0.15, 0.20],  # 展示タイム順位
            [0.0, 0.03, 0.06, 0.10],        # 展示ST順位
            [0.0, 0.05, 0.10, 0.15],        # 強風時1号艇減点
        )
    )

    results_by_config = []
    for config in configs:
        stat = evaluate(config, races, exhibitions, weather, results)
        avg_rank, top5, top10, top20 = metric_tuple(stat)
        results_by_config.append(
            {
                "config": config,
                "stat": stat,
                "avg_rank": avg_rank,
                "top5": top5,
                "top10": top10,
                "top20": top20,
            }
        )

    baseline = next(x for x in results_by_config if x["config"] == (0.0, 0.0, 0.0))
    # 平均順位を最優先、次にTop10、Top5で並べる
    ranked = sorted(
        results_by_config,
        key=lambda x: (
            x["avg_rank"],
            -x["top10"],
            -x["top5"],
            -x["top20"],
        ),
    )

    def show(label: str, row: Dict[str, Any]) -> None:
        s = row["stat"]
        n = s["races"]
        ex_w, st_w, wind_pen = row["config"]
        print(f"\n{label}", flush=True)
        print(
            f"  ex_weight={ex_w:.2f} st_weight={st_w:.2f} "
            f"strong_wind_lane1_penalty={wind_pen:.2f}",
            flush=True,
        )
        print(f"  races={n} avg_result_prob_rank={row['avg_rank']:.3f}", flush=True)
        for k in (1, 3, 5, 10, 20):
            count = s[f"top{k}"]
            pct = count / n * 100 if n else 0.0
            print(f"  result_in_top{k}={count} ({pct:.2f}%)", flush=True)

    show("BASELINE", baseline)

    print("\nTOP CONFIGS", flush=True)
    for idx, row in enumerate(ranked[:15], start=1):
        s = row["stat"]
        n = s["races"]
        ex_w, st_w, wind_pen = row["config"]
        print(
            f"{idx:02d}. ex={ex_w:.2f} st={st_w:.2f} wind1pen={wind_pen:.2f} "
            f"avg_rank={row['avg_rank']:.3f} "
            f"top5={s['top5']/n*100:.2f}% "
            f"top10={s['top10']/n*100:.2f}% "
            f"top20={s['top20']/n*100:.2f}%",
            flush=True,
        )

    best = ranked[0]
    show("BEST", best)

    print("\nBASELINE -> BEST DIFFERENCE", flush=True)
    print(
        f"  avg_rank: {baseline['avg_rank']:.3f} -> {best['avg_rank']:.3f} "
        f"delta={best['avg_rank']-baseline['avg_rank']:+.3f}",
        flush=True,
    )
    for k in (1, 3, 5, 10, 20):
        n0 = baseline["stat"]["races"]
        n1 = best["stat"]["races"]
        p0 = baseline["stat"][f"top{k}"] / n0 * 100 if n0 else 0.0
        p1 = best["stat"][f"top{k}"] / n1 * 100 if n1 else 0.0
        print(f"  top{k}: {p0:.2f}% -> {p1:.2f}% delta={p1-p0:+.2f}pt", flush=True)

    print("\n判定目安", flush=True)
    print("- 平均順位とTop5/Top10が同時改善する設定だけを採用候補にする", flush=True)
    print("- 10日分程度なので、本番判定へ直結せず裏側A/B保存から始める", flush=True)
    print("- 展示STが悪化要因ならst_weight=0の設定が上位に残る", flush=True)
    print("- 強風補正は72件程度なので、過大な係数は避ける", flush=True)
    print("=== exhibition scoring analysis finished ===", flush=True)


if __name__ == "__main__":
    main()