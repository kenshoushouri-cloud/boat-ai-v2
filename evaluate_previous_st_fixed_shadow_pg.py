# -*- coding: utf-8 -*-
"""
evaluate_previous_st_fixed_shadow_pg.py

固定前走ST shadowを結果と照合し、日次・累積で評価します。
読み取り専用です。本番判定・LINE通知・購入処理は変更しません。

Start Command:
    python -u evaluate_previous_st_fixed_shadow_pg.py
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
MIN_PREVIOUS_ST_FILLED = int(os.getenv("MIN_PREVIOUS_ST_FILLED", "1"))

REPORT_DAYS = int(os.getenv("PREVIOUS_ST_REPORT_DAYS", "30"))
REPORT_START_DATE = os.getenv("PREVIOUS_ST_REPORT_START_DATE", "").strip()


def si(v: Any, d: int = 0) -> int:
    try:
        return d if v is None or v == "" else int(float(v))
    except Exception:
        return d


def norm_ticket(v: Any) -> str:
    nums = re.findall(r"[1-6]", str(v or ""))
    return f"{nums[0]}-{nums[1]}-{nums[2]}" if len(nums) >= 3 else ""


def result_ticket(row: Dict[str, Any]) -> str:
    for key in ("result_trifecta", "trifecta", "winning_ticket", "result", "finish_order"):
        ticket = norm_ticket(row.get(key))
        if ticket:
            return ticket
    a = si(row.get("first_lane") or row.get("first") or row.get("rank1"))
    b = si(row.get("second_lane") or row.get("second") or row.get("rank2"))
    c = si(row.get("third_lane") or row.get("third") or row.get("rank3"))
    return f"{a}-{b}-{c}" if all(1 <= x <= 6 for x in (a, b, c)) else ""


def date_range() -> tuple[str, str]:
    end_date = TARGET_DATE
    if REPORT_START_DATE:
        return REPORT_START_DATE, end_date
    start_date = (
        datetime.strptime(end_date, "%Y-%m-%d")
        - timedelta(days=max(1, REPORT_DAYS) - 1)
    ).strftime("%Y-%m-%d")
    return start_date, end_date


def summarize(label: str, ranks: List[int]) -> None:
    if not ranks:
        print(f"{label}: races=0", flush=True)
        return
    n = len(ranks)
    print(
        f"{label}: races={n} avg={sum(ranks)/n:.3f} "
        f"top3={sum(x<=3 for x in ranks)/n*100:.2f}% "
        f"top5={sum(x<=5 for x in ranks)/n*100:.2f}% "
        f"top10={sum(x<=10 for x in ranks)/n*100:.2f}% "
        f"top20={sum(x<=20 for x in ranks)/n*100:.2f}%",
        flush=True,
    )


def evaluate_period(start_date: str, end_date: str, label: str) -> None:
    shadow_rows = fetch_all(
        """
        select
            race_id,
            ticket,
            baseline_prob_rank,
            shadow_prob_rank,
            previous_st_filled,
            candidate_change
        from v2_previous_st_shadow_rankings
        where race_date >= %s
          and race_date <= %s
          and snapshot_label = %s
          and selector_mode = %s
          and previous_st_filled >= %s
        order by race_id,ticket;
        """,
        (
            start_date,
            end_date,
            SNAPSHOT_LABEL,
            SELECTOR_MODE,
            MIN_PREVIOUS_ST_FILLED,
        ),
    )

    next_day = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")
    result_rows = fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (start_date.replace("-", ""), next_day),
    )
    results = {
        str(row.get("race_id")): result_ticket(row)
        for row in result_rows
    }
    results = {rid: ticket for rid, ticket in results.items() if ticket}

    by_race: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in shadow_rows:
        by_race.setdefault(str(row.get("race_id")), {})[
            norm_ticket(row.get("ticket"))
        ] = row

    baseline_ranks: List[int] = []
    shadow_ranks: List[int] = []
    improved = worsened = same = missing_result = missing_ticket = 0

    for race_id, tickets in by_race.items():
        winning = results.get(race_id)
        if not winning:
            missing_result += 1
            continue
        row = tickets.get(winning)
        if not row:
            missing_ticket += 1
            continue

        br = si(row.get("baseline_prob_rank"), 999)
        sr = si(row.get("shadow_prob_rank"), 999)
        baseline_ranks.append(br)
        shadow_ranks.append(sr)

        improved += sr < br
        worsened += sr > br
        same += sr == br

    print(f"\n=== {label} ===", flush=True)
    print(f"PERIOD={start_date}..{end_date}", flush=True)
    print(f"shadow_rows={len(shadow_rows)} coverage_races={len(by_race)}", flush=True)
    print(
        f"evaluated_races={len(baseline_ranks)} "
        f"missing_result={missing_result} missing_ticket={missing_ticket}",
        flush=True,
    )
    summarize("BASELINE", baseline_ranks)
    summarize("PREVIOUS ST SHADOW", shadow_ranks)

    if baseline_ranks:
        base_avg = sum(baseline_ranks) / len(baseline_ranks)
        shadow_avg = sum(shadow_ranks) / len(shadow_ranks)
        print(
            f"DIFF avg={shadow_avg-base_avg:+.3f} "
            f"improved={improved} worsened={worsened} same={same}",
            flush=True,
        )


def main() -> None:
    print(
        "✅ evaluate_previous_st_fixed_shadow_pg.py "
        "VERSION 2026-07-16 fixed-oos-eval-v1",
        flush=True,
    )
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} "
        f"MIN_PREVIOUS_ST_FILLED={MIN_PREVIOUS_ST_FILLED}",
        flush=True,
    )
    print("読み取り専用です。本番判定・LINE通知は変更しません。", flush=True)

    evaluate_period(TARGET_DATE, TARGET_DATE, "DAILY OUT-OF-SAMPLE")
    start_date, end_date = date_range()
    evaluate_period(start_date, end_date, "CUMULATIVE OUT-OF-SAMPLE")

    print(
        "\n判定目安: 累積300R以上で、平均順位改善・Top5非悪化・"
        "Top10非悪化・改善R>悪化Rを満たす場合のみ次段階へ進む。",
        flush=True,
    )
    print("=== previous ST fixed shadow evaluation finished ===", flush=True)


if __name__ == "__main__":
    main()