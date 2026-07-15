# -*- coding: utf-8 -*-
"""
evaluate_realtime_condition_shadow_pg.py

保存済み v2_realtime_condition_shadow_rankings と v2_results を使い、
当日コンディション補正の実績順位を評価します。

読み取り専用です。
本番判定・LINE通知・購入処理は変更しません。

Start Command:
    python -u evaluate_realtime_condition_shadow_pg.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    MIN_CONDITION_COVERAGE=6
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
MIN_CONDITION_COVERAGE = int(os.getenv("MIN_CONDITION_COVERAGE", "6"))


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


def _norm_ticket(v: Any) -> str:
    nums = re.findall(r"[1-6]", str(v or ""))
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return ""


def _result_ticket(row: Dict[str, Any]) -> str:
    for key in (
        "result_trifecta",
        "trifecta",
        "winning_ticket",
        "result",
        "finish_order",
    ):
        ticket = _norm_ticket(row.get(key))
        if ticket:
            return ticket

    first = _safe_int(
        row.get("first_lane")
        or row.get("first")
        or row.get("rank1")
        or row.get("first_place")
    )
    second = _safe_int(
        row.get("second_lane")
        or row.get("second")
        or row.get("rank2")
        or row.get("second_place")
    )
    third = _safe_int(
        row.get("third_lane")
        or row.get("third")
        or row.get("rank3")
        or row.get("third_place")
    )
    if all(1 <= x <= 6 for x in (first, second, third)):
        return f"{first}-{second}-{third}"
    return ""


def _summary(name: str, ranks: List[int]) -> None:
    if not ranks:
        print(f"{name}: races=0", flush=True)
        return

    n = len(ranks)
    avg = sum(ranks) / n
    print(f"{name}", flush=True)
    print(f"  races={n} avg_result_prob_rank={avg:.3f}", flush=True)
    for top in (1, 3, 5, 10, 20):
        hits = sum(rank <= top for rank in ranks)
        print(
            f"  result_in_top{top}={hits} ({hits/n*100:.2f}%)",
            flush=True,
        )


def main() -> None:
    print(
        "✅ evaluate_realtime_condition_shadow_pg.py "
        "VERSION 2026-07-15 result-rank-eval-v1",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} "
        f"MIN_CONDITION_COVERAGE={MIN_CONDITION_COVERAGE}",
        flush=True,
    )
    print(
        "読み取り専用です。本番判定・LINE通知は変更しません。",
        flush=True,
    )

    shadow_rows = fetch_all(
        """
        select
            race_id,
            ticket,
            baseline_prob_rank,
            shadow_prob_rank,
            rank_delta,
            condition_coverage,
            baseline_candidate,
            shadow_candidate,
            candidate_change
        from v2_realtime_condition_shadow_rankings
        where race_date = %s
          and snapshot_label = %s
          and selector_mode = %s
          and condition_coverage >= %s
        order by race_id, ticket;
        """,
        (
            TARGET_DATE,
            SNAPSHOT_LABEL,
            SELECTOR_MODE,
            MIN_CONDITION_COVERAGE,
        ),
    )

    result_rows = fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s
        order by race_id;
        """,
        (
            TARGET_DATE.replace("-", ""),
            (
                datetime.strptime(TARGET_DATE, "%Y-%m-%d")
                + timedelta(days=1)
            ).strftime("%Y%m%d"),
        ),
    )

    results = {
        str(row.get("race_id")): _result_ticket(row)
        for row in result_rows
    }
    results = {rid: ticket for rid, ticket in results.items() if ticket}

    by_race: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in shadow_rows:
        by_race.setdefault(str(row.get("race_id")), {})[
            _norm_ticket(row.get("ticket"))
        ] = row

    baseline_ranks: List[int] = []
    shadow_ranks: List[int] = []
    improved = worsened = same = missing_result = missing_ticket = 0
    samples = []
    change_counter = Counter()

    for race_id, tickets in by_race.items():
        winning = results.get(race_id)
        if not winning:
            missing_result += 1
            continue

        row = tickets.get(winning)
        if not row:
            missing_ticket += 1
            continue

        br = _safe_int(row.get("baseline_prob_rank"), 999)
        sr = _safe_int(row.get("shadow_prob_rank"), 999)

        baseline_ranks.append(br)
        shadow_ranks.append(sr)

        if sr < br:
            improved += 1
        elif sr > br:
            worsened += 1
        else:
            same += 1

        change_counter[str(row.get("candidate_change") or "none")] += 1

        delta = br - sr
        if abs(delta) >= 3:
            samples.append(
                (
                    race_id,
                    winning,
                    br,
                    sr,
                    delta,
                    _safe_int(row.get("condition_coverage"), 0),
                )
            )

    print("\n=== realtime condition shadow result evaluation ===", flush=True)
    print(f"shadow_rows={len(shadow_rows)}", flush=True)
    print(f"coverage_races={len(by_race)}", flush=True)
    print(f"results_available={len(results)}", flush=True)
    print(
        f"evaluated_races={len(baseline_ranks)} "
        f"missing_result={missing_result} "
        f"missing_ticket={missing_ticket}",
        flush=True,
    )

    _summary("BASELINE", baseline_ranks)
    _summary("REALTIME CONDITION SHADOW", shadow_ranks)

    if baseline_ranks:
        base_avg = sum(baseline_ranks) / len(baseline_ranks)
        shadow_avg = sum(shadow_ranks) / len(shadow_ranks)
        print("DIFFERENCE", flush=True)
        print(
            f"  avg_rank: {base_avg:.3f} -> {shadow_avg:.3f} "
            f"delta={shadow_avg-base_avg:+.3f}",
            flush=True,
        )
        print(
            f"  winning_ticket_rank_improved={improved} "
            f"worsened={worsened} same={same}",
            flush=True,
        )

    print("WINNING TICKET CANDIDATE CHANGE", flush=True)
    for key in ("added", "removed", "kept", "none"):
        print(f"  {key}: {change_counter.get(key, 0)}", flush=True)

    print("--- large rank movement samples ---", flush=True)
    for row in sorted(samples, key=lambda x: abs(x[4]), reverse=True)[:30]:
        print(row, flush=True)

    print(
        "判定目安: 平均順位とTop5/Top10が同時改善した場合のみ、"
        "次の重み比較へ進む。",
        flush=True,
    )
    print("=== realtime condition shadow evaluation finished ===", flush=True)


if __name__ == "__main__":
    main()