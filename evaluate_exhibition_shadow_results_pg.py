# -*- coding: utf-8 -*-
"""
evaluate_exhibition_shadow_results_pg.py

展示補正shadow判定と確定結果を突合し、1レース単位の成績を保存します。
本番BUY/WATCH/SKIP判定およびLINE通知には影響しません。

保存先:
    v2_exhibition_shadow_results

Start Command:
    python -u evaluate_exhibition_shadow_results_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    TARGET_DATE=YYYY-MM-DD
    SNAPSHOT_LABEL=final_ab
    SELECTOR_MODE=ab
    UNIT_YEN=100
"""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import execute, fetch_all, upsert_rows

JST = timezone(timedelta(hours=9))

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
SNAPSHOT_LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab").strip() or "final_ab"
SELECTOR_MODE = os.getenv("SELECTOR_MODE", "ab").strip().lower() or "ab"
UNIT_YEN = int(os.getenv("UNIT_YEN", "100"))


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


def _norm_ticket(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    nums = re.findall(r"[1-6]", text)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return ""


def _result_ticket(row: Dict[str, Any]) -> str:
    for key in ("trifecta_ticket", "ticket"):
        ticket = _norm_ticket(row.get(key))
        if ticket:
            return ticket

    first = _safe_int(row.get("first_lane"))
    second = _safe_int(row.get("second_lane"))
    third = _safe_int(row.get("third_lane"))
    if all(1 <= lane <= 6 for lane in (first, second, third)):
        return f"{first}-{second}-{third}"

    finish_order = row.get("finish_order")
    if isinstance(finish_order, (list, tuple)) and len(finish_order) >= 3:
        lanes = [_safe_int(x) for x in finish_order[:3]]
        if all(1 <= lane <= 6 for lane in lanes):
            return f"{lanes[0]}-{lanes[1]}-{lanes[2]}"

    return ""


def _result_payout(row: Dict[str, Any]) -> int:
    return max(
        0,
        _safe_int(
            row.get("trifecta_payout_yen")
            or row.get("trifecta_payout")
            or row.get("payout")
        ),
    )


def _ensure_schema() -> None:
    ddl = [
        "create table if not exists v2_exhibition_shadow_results (id bigserial primary key);",
        "alter table v2_exhibition_shadow_results add column if not exists race_id text;",
        "alter table v2_exhibition_shadow_results add column if not exists race_date date;",
        "alter table v2_exhibition_shadow_results add column if not exists venue_id text;",
        "alter table v2_exhibition_shadow_results add column if not exists race_no integer;",
        "alter table v2_exhibition_shadow_results add column if not exists snapshot_label text;",
        "alter table v2_exhibition_shadow_results add column if not exists selector_mode text;",
        "alter table v2_exhibition_shadow_results add column if not exists ticket text;",
        "alter table v2_exhibition_shadow_results add column if not exists result_ticket text;",
        "alter table v2_exhibition_shadow_results add column if not exists trifecta_payout_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists baseline_prob_rank integer;",
        "alter table v2_exhibition_shadow_results add column if not exists shadow_prob_rank integer;",
        "alter table v2_exhibition_shadow_results add column if not exists rank_delta integer;",
        "alter table v2_exhibition_shadow_results add column if not exists baseline_candidate boolean;",
        "alter table v2_exhibition_shadow_results add column if not exists shadow_candidate boolean;",
        "alter table v2_exhibition_shadow_results add column if not exists candidate_change text;",
        "alter table v2_exhibition_shadow_results add column if not exists ticket_hit boolean;",
        "alter table v2_exhibition_shadow_results add column if not exists baseline_investment_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists baseline_return_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists baseline_profit_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists shadow_investment_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists shadow_return_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists shadow_profit_yen integer;",
        "alter table v2_exhibition_shadow_results add column if not exists evaluated_at timestamptz;",
        "alter table v2_exhibition_shadow_results add column if not exists updated_at timestamptz;",
        """
        create unique index if not exists uq_v2_exhibition_shadow_results_main
        on v2_exhibition_shadow_results
        (race_id, snapshot_label, selector_mode, ticket);
        """,
        "create index if not exists idx_v2_exhibition_shadow_results_date on v2_exhibition_shadow_results (race_date);",
        "create index if not exists idx_v2_exhibition_shadow_results_change on v2_exhibition_shadow_results (candidate_change);",
    ]
    for sql in ddl:
        execute(sql)


def _summary(rows: List[Dict[str, Any]], prefix: str) -> Dict[str, float]:
    investment_key = f"{prefix}_investment_yen"
    return_key = f"{prefix}_return_yen"

    candidates = sum(1 for row in rows if _safe_int(row.get(investment_key)) > 0)
    hits = sum(
        1
        for row in rows
        if _safe_int(row.get(investment_key)) > 0 and bool(row.get("ticket_hit"))
    )
    investment = sum(_safe_int(row.get(investment_key)) for row in rows)
    returns = sum(_safe_int(row.get(return_key)) for row in rows)
    profit = returns - investment
    roi = (returns / investment * 100.0) if investment > 0 else 0.0
    hit_rate = (hits / candidates * 100.0) if candidates > 0 else 0.0

    return {
        "candidates": candidates,
        "hits": hits,
        "hit_rate": hit_rate,
        "investment": investment,
        "returns": returns,
        "profit": profit,
        "roi": roi,
    }


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    _ensure_schema()

    print(
        "✅ evaluate_exhibition_shadow_results_pg.py "
        "VERSION 2026-07-15 nightly-shadow-eval-v2-race-id-prefix",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} SNAPSHOT_LABEL={SNAPSHOT_LABEL} "
        f"SELECTOR_MODE={SELECTOR_MODE} UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print("本番判定・LINE通知・購入処理には影響しません。", flush=True)

    shadow_rows = fetch_all(
        """
        select *
        from v2_exhibition_shadow_decisions
        where race_date=%s
          and snapshot_label=%s
          and selector_mode=%s
        order by race_id, ticket;
        """,
        (TARGET_DATE, SNAPSHOT_LABEL, SELECTOR_MODE),
    )

    day_prefix = TARGET_DATE.replace("-", "")
    next_prefix = (
        datetime.strptime(TARGET_DATE, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y%m%d")

    result_rows = fetch_all(
        """
        select *
        from v2_results
        where race_id >= %s
          and race_id < %s
        order by race_id;
        """,
        (day_prefix, next_prefix),
    )
    results_by_race = {
        str(row.get("race_id")): row
        for row in result_rows
        if row.get("race_id")
    }

    result_race_date_null = sum(
        1 for row in result_rows if row.get("race_date") is None
    )

    save_rows: List[Dict[str, Any]] = []
    skipped_no_result = 0
    skipped_bad_result = 0

    for shadow in shadow_rows:
        race_id = str(shadow.get("race_id") or "")
        result = results_by_race.get(race_id)
        if not result:
            skipped_no_result += 1
            continue

        result_ticket = _result_ticket(result)
        if not result_ticket:
            skipped_bad_result += 1
            continue

        ticket = _norm_ticket(shadow.get("ticket"))
        payout = _result_payout(result)
        hit = bool(ticket and ticket == result_ticket)

        baseline_candidate = bool(shadow.get("baseline_candidate"))
        shadow_candidate = bool(shadow.get("shadow_candidate"))

        baseline_investment = UNIT_YEN if baseline_candidate else 0
        shadow_investment = UNIT_YEN if shadow_candidate else 0

        baseline_return = payout if baseline_candidate and hit else 0
        shadow_return = payout if shadow_candidate and hit else 0

        save_rows.append({
            "race_id": race_id,
            "race_date": TARGET_DATE,
            "venue_id": str(shadow.get("venue_id") or "").zfill(2),
            "race_no": _safe_int(shadow.get("race_no")),
            "snapshot_label": SNAPSHOT_LABEL,
            "selector_mode": SELECTOR_MODE,
            "ticket": ticket,
            "result_ticket": result_ticket,
            "trifecta_payout_yen": payout,
            "baseline_prob_rank": _safe_int(shadow.get("baseline_prob_rank"), 999),
            "shadow_prob_rank": _safe_int(shadow.get("shadow_prob_rank"), 999),
            "rank_delta": _safe_int(shadow.get("rank_delta")),
            "baseline_candidate": baseline_candidate,
            "shadow_candidate": shadow_candidate,
            "candidate_change": str(shadow.get("candidate_change") or "none"),
            "ticket_hit": hit,
            "baseline_investment_yen": baseline_investment,
            "baseline_return_yen": baseline_return,
            "baseline_profit_yen": baseline_return - baseline_investment,
            "shadow_investment_yen": shadow_investment,
            "shadow_return_yen": shadow_return,
            "shadow_profit_yen": shadow_return - shadow_investment,
            "evaluated_at": datetime.now(JST).isoformat(),
            "updated_at": datetime.now(JST).isoformat(),
        })

    saved = (
        upsert_rows(
            "v2_exhibition_shadow_results",
            save_rows,
            ["race_id", "snapshot_label", "selector_mode", "ticket"],
        )
        if save_rows
        else 0
    )

    baseline = _summary(save_rows, "baseline")
    shadow = _summary(save_rows, "shadow")

    changes: Dict[str, int] = {}
    changed_hits: Dict[str, int] = {}
    for row in save_rows:
        change = str(row.get("candidate_change") or "none")
        changes[change] = changes.get(change, 0) + 1
        if row.get("ticket_hit"):
            changed_hits[change] = changed_hits.get(change, 0) + 1

    print("\n=== exhibition shadow nightly result summary ===", flush=True)
    print(
        f"shadow_rows={len(shadow_rows)} results={len(result_rows)} "
        f"evaluated={len(save_rows)} saved={saved}",
        flush=True,
    )
    print(
        f"result_race_date_null={result_race_date_null}/{len(result_rows)} "
        "(race_id prefixで取得)",
        flush=True,
    )
    print(
        f"skipped_no_result={skipped_no_result} "
        f"skipped_bad_result={skipped_bad_result}",
        flush=True,
    )

    print(
        "BASELINE "
        f"candidates={int(baseline['candidates'])} "
        f"hits={int(baseline['hits'])} "
        f"hit_rate={baseline['hit_rate']:.2f}% "
        f"investment={int(baseline['investment'])} "
        f"return={int(baseline['returns'])} "
        f"profit={int(baseline['profit'])} "
        f"ROI={baseline['roi']:.2f}%",
        flush=True,
    )
    print(
        "SHADOW "
        f"candidates={int(shadow['candidates'])} "
        f"hits={int(shadow['hits'])} "
        f"hit_rate={shadow['hit_rate']:.2f}% "
        f"investment={int(shadow['investment'])} "
        f"return={int(shadow['returns'])} "
        f"profit={int(shadow['profit'])} "
        f"ROI={shadow['roi']:.2f}%",
        flush=True,
    )

    print(
        f"DIFF candidates={int(shadow['candidates'] - baseline['candidates']):+d} "
        f"profit={int(shadow['profit'] - baseline['profit']):+d} "
        f"ROI={shadow['roi'] - baseline['roi']:+.2f}pt",
        flush=True,
    )

    print("CANDIDATE CHANGES", flush=True)
    for change in ("added", "removed", "kept", "none"):
        print(
            f"  {change}: rows={changes.get(change, 0)} "
            f"ticket_hits={changed_hits.get(change, 0)}",
            flush=True,
        )

    print("=== exhibition shadow nightly evaluation finished ===", flush=True)


if __name__ == "__main__":
    main()