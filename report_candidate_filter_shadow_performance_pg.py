# -*- coding: utf-8 -*-
"""
report_candidate_filter_shadow_performance_pg.py

候補フィルターShadow（S01～S05）の累積成績を集計する読み取り専用レポートです。

重要:
- LINE通知しません。
- DB更新しません。
- 本番判定・購入処理を変更しません。
- rule_id別、日別、重複除外後の全体成績を表示します。

通常は run_nightly_results_pg.py の候補フィルターShadow結果評価後に実行します。

Start Command（単体テスト用）:
    python -u report_candidate_filter_shadow_performance_pg.py

Variables:
    DATABASE_URL

任意:
    TARGET_DATE=YYYY-MM-DD
    CANDIDATE_SHADOW_REPORT_DAYS=30
    CANDIDATE_SHADOW_READY_MIN_EVALUATED=30
    CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED=20
    CANDIDATE_SHADOW_READY_MIN_ROI=100
    CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT=60
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
REPORT_DAYS = max(1, int(os.getenv("CANDIDATE_SHADOW_REPORT_DAYS", "30")))
READY_MIN_EVALUATED = max(
    1,
    int(os.getenv("CANDIDATE_SHADOW_READY_MIN_EVALUATED", "30")),
)
READY_MIN_RULE_EVALUATED = max(
    1,
    int(os.getenv("CANDIDATE_SHADOW_READY_MIN_RULE_EVALUATED", "20")),
)
READY_MIN_ROI = float(
    os.getenv("CANDIDATE_SHADOW_READY_MIN_ROI", "100")
)
READY_MAX_SINGLE_HIT_SHARE_PCT = float(
    os.getenv(
        "CANDIDATE_SHADOW_READY_MAX_SINGLE_HIT_SHARE_PCT",
        "60",
    )
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _date_shift(date_str: str, days: int) -> str:
    return (
        datetime.strptime(date_str, "%Y-%m-%d")
        + timedelta(days=days)
    ).strftime("%Y-%m-%d")


def _new_stat() -> Dict[str, Any]:
    return {
        "rows": 0,
        "evaluated": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
    }


def _add_row(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    stat["rows"] += 1

    if str(row.get("evaluation_status") or "") != "evaluated":
        return

    stat["evaluated"] += 1
    investment = _safe_int(row.get("investment_yen"), 100)
    returned = _safe_int(row.get("return_yen"), 0)

    stat["investment"] += investment
    stat["return"] += returned

    if bool(row.get("hit")):
        stat["hits"] += 1
        if returned > 0:
            stat["hit_returns"].append(returned)


def _metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    evaluated = int(stat["evaluated"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    profit = returned - investment

    hit_rate = (
        hits / evaluated * 100.0
        if evaluated > 0
        else 0.0
    )
    roi = (
        returned / investment * 100.0
        if investment > 0
        else 0.0
    )
    max_hit = max(stat["hit_returns"]) if stat["hit_returns"] else 0
    single_hit_share = (
        max_hit / returned * 100.0
        if returned > 0
        else 0.0
    )

    return {
        "evaluated": float(evaluated),
        "hits": float(hits),
        "investment": float(investment),
        "return": float(returned),
        "profit": float(profit),
        "hit_rate": hit_rate,
        "roi": roi,
        "max_hit": float(max_hit),
        "single_hit_share": single_hit_share,
    }


def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    print(
        f"{label}: rows={stat['rows']} "
        f"evaluated={int(m['evaluated'])} "
        f"hits={int(m['hits'])} "
        f"hit_rate={m['hit_rate']:.2f}% "
        f"investment={int(m['investment'])} "
        f"return={int(m['return'])} "
        f"profit={int(m['profit'])} "
        f"ROI={m['roi']:.2f}% "
        f"max_hit={int(m['max_hit'])} "
        f"single_hit_share={m['single_hit_share']:.2f}%",
        flush=True,
    )


def _fetch_rows(start_date: str) -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select *
        from v2_candidate_filter_shadow
        where race_date >= %s
          and race_date <= %s
          and rule_id in ('S01','S02','S03','S04','S05')
        order by race_date, race_id, rule_id, ticket;
        """,
        (start_date, TARGET_DATE),
    )


def _dedup_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (
        str(row.get("race_id") or ""),
        str(row.get("ticket") or ""),
    )


def main() -> None:
    print(
        "✅ report_candidate_filter_shadow_performance_pg.py "
        "VERSION 2026-08-21 cumulative-readiness-v2-rule-isolation",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    start_date = _date_shift(TARGET_DATE, -(REPORT_DAYS - 1))

    print(
        f"PERIOD={start_date}..{TARGET_DATE} "
        f"REPORT_DAYS={REPORT_DAYS}",
        flush=True,
    )
    print(
        "読み取り専用です。LINE通知・DB更新・本番判定変更はありません。",
        flush=True,
    )

    rows = _fetch_rows(start_date)

    overall = _new_stat()
    by_rule: Dict[str, Dict[str, Any]] = defaultdict(_new_stat)
    by_day: Dict[str, Dict[str, Any]] = defaultdict(_new_stat)

    dedup_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in rows:
        _add_row(overall, row)

        rule_id = str(row.get("rule_id") or "UNKNOWN")
        race_date = str(row.get("race_date") or "")[:10]

        _add_row(by_rule[rule_id], row)
        _add_row(by_day[race_date], row)

        key = _dedup_key(row)
        current = dedup_rows.get(key)
        if current is None:
            dedup_rows[key] = row
            continue

        # 同じrace_id・ticketが複数ルールに一致した場合は、
        # 評価済み行を優先し、払戻情報が多い方を保持する。
        current_eval = str(current.get("evaluation_status") or "") == "evaluated"
        new_eval = str(row.get("evaluation_status") or "") == "evaluated"
        if new_eval and not current_eval:
            dedup_rows[key] = row
        elif new_eval == current_eval:
            if _safe_int(row.get("return_yen"), 0) > _safe_int(
                current.get("return_yen"),
                0,
            ):
                dedup_rows[key] = row

    dedup_stat = _new_stat()
    for row in dedup_rows.values():
        _add_row(dedup_stat, row)

    print("\n=== candidate filter shadow cumulative summary ===", flush=True)
    _print_stat("RULE_ROWS_TOTAL", overall)
    _print_stat("DEDUP_RACE_TICKET", dedup_stat)

    print("\n=== rule breakdown ===", flush=True)
    for rule_id in sorted(by_rule):
        _print_stat(rule_id, by_rule[rule_id])

    print("\n=== daily breakdown ===", flush=True)
    for race_date in sorted(by_day):
        _print_stat(race_date, by_day[race_date])

    print("\n=== readiness assessment ===", flush=True)

    dedup_metrics = _metrics(dedup_stat)

    overall_ready = int(dedup_metrics["evaluated"]) >= READY_MIN_EVALUATED
    roi_ready = dedup_metrics["roi"] >= READY_MIN_ROI
    concentration_ready = (
        dedup_metrics["single_hit_share"]
        <= READY_MAX_SINGLE_HIT_SHARE_PCT
        if dedup_metrics["return"] > 0
        else False
    )

    print(
        f"dedup_evaluated: "
        f"{'PASS' if overall_ready else 'WAIT'} "
        f"({int(dedup_metrics['evaluated'])}/"
        f"{READY_MIN_EVALUATED})",
        flush=True,
    )
    print(
        f"dedup_roi: "
        f"{'PASS' if roi_ready else 'WAIT'} "
        f"({dedup_metrics['roi']:.2f}%/"
        f"{READY_MIN_ROI:.2f}%)",
        flush=True,
    )
    print(
        f"single_hit_concentration: "
        f"{'PASS' if concentration_ready else 'WAIT'} "
        f"({dedup_metrics['single_hit_share']:.2f}%/"
        f"max {READY_MAX_SINGLE_HIT_SHARE_PCT:.2f}%)",
        flush=True,
    )

    qualified_rules: List[str] = []

    for rule_id in sorted(by_rule):
        metrics = _metrics(by_rule[rule_id])
        enough = int(metrics["evaluated"]) >= READY_MIN_RULE_EVALUATED
        profitable = metrics["roi"] >= READY_MIN_ROI
        concentrated_ok = (
            metrics["single_hit_share"]
            <= READY_MAX_SINGLE_HIT_SHARE_PCT
            if metrics["return"] > 0
            else False
        )

        status = (
            "PASS"
            if enough and profitable and concentrated_ok
            else "WAIT"
        )

        print(
            f"{rule_id}: {status} "
            f"evaluated={int(metrics['evaluated'])}/"
            f"{READY_MIN_RULE_EVALUATED} "
            f"ROI={metrics['roi']:.2f}% "
            f"single_hit_share="
            f"{metrics['single_hit_share']:.2f}%",
            flush=True,
        )

        if status == "PASS":
            qualified_rules.append(rule_id)

    if overall_ready and roi_ready and concentration_ready and qualified_rules:
        print(
            "READINESS=REVIEW "
            f"qualified_rules={','.join(qualified_rules)}",
            flush=True,
        )
        print(
            "本番採用ではなく、追加の期間分割確認・直前情報検証へ進めます。",
            flush=True,
        )
    else:
        waits = []
        if not overall_ready:
            waits.append("dedup_evaluated")
        if not roi_ready:
            waits.append("dedup_roi")
        if not concentration_ready:
            waits.append("single_hit_concentration")
        if not qualified_rules:
            waits.append("qualified_rules")

        print(
            "READINESS=COLLECTING "
            f"未達項目={','.join(waits)}",
            flush=True,
        )

    print(
        "=== candidate filter shadow cumulative report finished ===",
        flush=True,
    )


if __name__ == "__main__":
    main()