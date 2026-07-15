# -*- coding: utf-8 -*-
"""
report_exhibition_shadow_performance_pg.py

展示補正shadow結果の累積成績を集計します。
本番BUY/WATCH/SKIP判定、LINE通知、購入処理には影響しません。

Start Command:
    python -u report_exhibition_shadow_performance_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    SHADOW_REPORT_DAYS=30
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SHADOW_REPORT_DAYS = max(1, int(os.getenv("SHADOW_REPORT_DAYS", "30")))
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"

SHADOW_READY_MIN_ROWS = max(
    1,
    int(os.getenv("SHADOW_READY_MIN_ROWS", "300")),
)
SHADOW_READY_MIN_BASE_CANDIDATES = max(
    1,
    int(os.getenv("SHADOW_READY_MIN_BASE_CANDIDATES", "20")),
)
SHADOW_READY_MIN_SHADOW_CANDIDATES = max(
    1,
    int(os.getenv("SHADOW_READY_MIN_SHADOW_CANDIDATES", "20")),
)
SHADOW_READY_MIN_ADDED = max(
    1,
    int(os.getenv("SHADOW_READY_MIN_ADDED", "10")),
)
SHADOW_READY_MIN_REMOVED = max(
    1,
    int(os.getenv("SHADOW_READY_MIN_REMOVED", "10")),
)
SHADOW_READY_MAX_ROI_DROP_PT = float(
    os.getenv("SHADOW_READY_MAX_ROI_DROP_PT", "0.0")
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _summary(rows: List[Dict[str, Any]], prefix: str) -> Dict[str, float]:
    investment_key = f"{prefix}_investment_yen"
    return_key = f"{prefix}_return_yen"

    candidates = sum(1 for r in rows if _safe_int(r.get(investment_key)) > 0)
    hits = sum(
        1
        for r in rows
        if _safe_int(r.get(investment_key)) > 0 and bool(r.get("ticket_hit"))
    )
    investment = sum(_safe_int(r.get(investment_key)) for r in rows)
    returns = sum(_safe_int(r.get(return_key)) for r in rows)
    profit = returns - investment
    roi = returns / investment * 100.0 if investment > 0 else 0.0
    hit_rate = hits / candidates * 100.0 if candidates > 0 else 0.0

    return {
        "candidates": candidates,
        "hits": hits,
        "investment": investment,
        "returns": returns,
        "profit": profit,
        "roi": roi,
        "hit_rate": hit_rate,
    }


def _print_summary(label: str, data: Dict[str, float]) -> None:
    print(
        f"{label} "
        f"candidates={int(data['candidates'])} "
        f"hits={int(data['hits'])} "
        f"hit_rate={data['hit_rate']:.2f}% "
        f"investment={int(data['investment'])} "
        f"return={int(data['returns'])} "
        f"profit={int(data['profit'])} "
        f"ROI={data['roi']:.2f}%",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    end_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=SHADOW_REPORT_DAYS - 1)

    print(
        "✅ report_exhibition_shadow_performance_pg.py "
        "VERSION 2026-07-15 cumulative-shadow-report-v2-readiness",
        flush=True,
    )
    print(
        f"PERIOD={start_date}..{end_date} "
        f"SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE}",
        flush=True,
    )
    print(
        "READINESS_THRESHOLDS "
        f"rows>={SHADOW_READY_MIN_ROWS} "
        f"base_candidates>={SHADOW_READY_MIN_BASE_CANDIDATES} "
        f"shadow_candidates>={SHADOW_READY_MIN_SHADOW_CANDIDATES} "
        f"added>={SHADOW_READY_MIN_ADDED} "
        f"removed>={SHADOW_READY_MIN_REMOVED} "
        f"max_roi_drop={SHADOW_READY_MAX_ROI_DROP_PT:.2f}pt",
        flush=True,
    )
    print("読み取り専用です。本番判定・LINE通知は変更しません。", flush=True)

    rows = fetch_all(
        """
        select *
        from v2_exhibition_shadow_results
        where race_date >= %s
          and race_date <= %s
          and snapshot_label = %s
          and selector_mode = %s
        order by race_date, race_id, ticket;
        """,
        (str(start_date), str(end_date), SNAPSHOT_LABEL, SELECTOR_MODE),
    )

    baseline = _summary(rows, "baseline")
    shadow = _summary(rows, "shadow")

    print("\n=== cumulative exhibition shadow performance ===", flush=True)
    print(f"evaluated_rows={len(rows)}", flush=True)
    _print_summary("BASELINE", baseline)
    _print_summary("SHADOW", shadow)

    print(
        f"DIFF candidates={int(shadow['candidates'] - baseline['candidates']):+d} "
        f"hits={int(shadow['hits'] - baseline['hits']):+d} "
        f"profit={int(shadow['profit'] - baseline['profit']):+d} "
        f"ROI={shadow['roi'] - baseline['roi']:+.2f}pt",
        flush=True,
    )

    print("CANDIDATE CHANGES", flush=True)
    change_counts: Dict[str, int] = {}
    change_hits: Dict[str, int] = {}
    for change in ("added", "removed", "kept", "none"):
        part = [
            r
            for r in rows
            if str(r.get("candidate_change") or "none") == change
        ]
        hits = sum(1 for r in part if bool(r.get("ticket_hit")))
        payout_sum = sum(
            _safe_int(r.get("trifecta_payout_yen"))
            for r in part
            if bool(r.get("ticket_hit"))
        )
        change_counts[change] = len(part)
        change_hits[change] = hits
        print(
            f"  {change}: rows={len(part)} "
            f"ticket_hits={hits} hit_payout_sum={payout_sum}",
            flush=True,
        )

    print("RANK MOVEMENT", flush=True)
    improved = [r for r in rows if _safe_int(r.get("rank_delta")) > 0]
    worsened = [r for r in rows if _safe_int(r.get("rank_delta")) < 0]
    same = [r for r in rows if _safe_int(r.get("rank_delta")) == 0]

    for label, part in (
        ("improved", improved),
        ("worsened", worsened),
        ("same", same),
    ):
        hits = sum(1 for r in part if bool(r.get("ticket_hit")))
        print(
            f"  {label}: rows={len(part)} ticket_hits={hits}",
            flush=True,
        )

    print("DAILY BREAKDOWN", flush=True)
    dates = sorted({str(r.get("race_date"))[:10] for r in rows if r.get("race_date")})
    for d in dates:
        part = [r for r in rows if str(r.get("race_date"))[:10] == d]
        b = _summary(part, "baseline")
        s = _summary(part, "shadow")
        print(
            f"  {d}: rows={len(part)} "
            f"base_candidates={int(b['candidates'])} base_profit={int(b['profit'])} "
            f"shadow_candidates={int(s['candidates'])} shadow_profit={int(s['profit'])}",
            flush=True,
        )

    roi_diff = shadow["roi"] - baseline["roi"]

    readiness_checks = {
        "evaluated_rows": len(rows) >= SHADOW_READY_MIN_ROWS,
        "baseline_candidates": (
            baseline["candidates"] >= SHADOW_READY_MIN_BASE_CANDIDATES
        ),
        "shadow_candidates": (
            shadow["candidates"] >= SHADOW_READY_MIN_SHADOW_CANDIDATES
        ),
        "added_samples": (
            change_counts.get("added", 0) >= SHADOW_READY_MIN_ADDED
        ),
        "removed_samples": (
            change_counts.get("removed", 0) >= SHADOW_READY_MIN_REMOVED
        ),
        "roi_not_worse": roi_diff >= -SHADOW_READY_MAX_ROI_DROP_PT,
    }

    ready = all(readiness_checks.values())

    print("READINESS ASSESSMENT", flush=True)
    for name, passed in readiness_checks.items():
        print(
            f"  {name}: {'PASS' if passed else 'WAIT'}",
            flush=True,
        )

    if ready:
        print(
            "READINESS=READY_FOR_MANUAL_REVIEW "
            "展示補正の本番採用可否を手動検討できる水準です。"
            "自動反映はしません。",
            flush=True,
        )
    else:
        waiting = [
            name
            for name, passed in readiness_checks.items()
            if not passed
        ]
        print(
            "READINESS=COLLECTING "
            f"未達項目={','.join(waiting)}",
            flush=True,
        )

    print("=== cumulative exhibition shadow report finished ===", flush=True)


if __name__ == "__main__":
    main()