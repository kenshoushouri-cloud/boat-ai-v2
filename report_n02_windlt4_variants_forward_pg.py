# -*- coding: utf-8 -*-
"""
report_n02_windlt4_variants_forward_pg.py

N02_WIND_LT4 と、2026-08-18 に固定した3つの追加Shadow条件を
同一のForward期間で比較する読み取り専用レポートです。

比較 rule_id:
- N02_WIND_LT4
- N02_WIND_LT4_ST15
- N02_WIND_LT4_MOTOR2
- N02_WIND_LT4_MOTOR2_GAP

重要:
- DB更新なし
- LINE通知なし
- 本番判定変更なし
- バックテスト結果を加算しない
- v2_results の official 結果だけを評価
- 未確定レースは pending として除外
- 各ruleを100円1点購入した仮定で比較

Start Command:
    python -u report_n02_windlt4_variants_forward_pg.py

Variables:
    DATABASE_URL

任意:
    TARGET_DATE=YYYY-MM-DD
    N02_VARIANT_FORWARD_START_DATE=2026-08-19
    N02_VARIANT_UNIT_YEN=100
    N02_VARIANT_REVIEW_TARGETS=10,30,50,100
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-18 n02-windlt4-variant-forward-report-v1"

TARGET_DATE = (
    os.getenv("TARGET_DATE")
    or datetime.now(JST).strftime("%Y-%m-%d")
)
START_DATE = os.getenv(
    "N02_VARIANT_FORWARD_START_DATE",
    "2026-08-19",
).strip()

UNIT_YEN = max(
    1,
    int(os.getenv("N02_VARIANT_UNIT_YEN", "100")),
)

RULE_IDS = (
    "N02_WIND_LT4",
    "N02_WIND_LT4_ST15",
    "N02_WIND_LT4_MOTOR2",
    "N02_WIND_LT4_MOTOR2_GAP",
)

REVIEW_TARGETS = sorted(
    {
        int(x)
        for x in os.getenv(
            "N02_VARIANT_REVIEW_TARGETS",
            "10,30,50,100",
        ).replace(" ", "").split(",")
        if x and int(x) > 0
    }
)


def _si(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _norm_ticket(value: Any) -> str:
    import re
    import unicodedata

    text = unicodedata.normalize("NFKC", str(value or ""))
    nums = re.findall(r"[1-6]", text)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    return text.strip()


def _new_stat() -> Dict[str, Any]:
    return {
        "rows": 0,
        "evaluated": 0,
        "pending": 0,
        "invalid": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "returns": [],
        "sequence": [],
    }


def _risk(sequence: List[int]) -> Tuple[int, int, int]:
    """
    sequence: 各betの損益（円）
    returns max_losing_streak, max_drawdown_yen, max_drawdown_bets
    """
    losing = 0
    max_losing = 0

    equity = 0
    peak = 0
    peak_index = 0
    max_dd = 0
    max_dd_bets = 0

    for i, profit in enumerate(sequence, start=1):
        if profit < 0:
            losing += 1
            max_losing = max(max_losing, losing)
        else:
            losing = 0

        equity += profit
        if equity >= peak:
            peak = equity
            peak_index = i

        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_bets = i - peak_index

    return max_losing, max_dd, max_dd_bets


def _metrics(stat: Dict[str, Any]) -> Dict[str, Any]:
    evaluated = stat["evaluated"]
    hits = stat["hits"]
    inv = stat["investment"]
    ret = stat["return"]

    hit_rate = hits / evaluated * 100.0 if evaluated else 0.0
    roi = ret / inv * 100.0 if inv else 0.0
    profit = ret - inv

    max_hit = max(stat["returns"]) if stat["returns"] else 0
    single_share = max_hit / ret * 100.0 if ret else 0.0
    max_ls, max_dd, max_dd_bets = _risk(stat["sequence"])

    return {
        "hit_rate": hit_rate,
        "roi": roi,
        "profit": profit,
        "max_hit": max_hit,
        "single_hit_share": single_share,
        "max_losing_streak": max_ls,
        "max_drawdown_yen": max_dd,
        "max_drawdown_bets": max_dd_bets,
    }


def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    print(
        f"{label}: "
        f"rows={stat['rows']} "
        f"evaluated={stat['evaluated']} "
        f"pending={stat['pending']} "
        f"invalid={stat['invalid']} "
        f"hits={stat['hits']} "
        f"hit_rate={m['hit_rate']:.2f}% "
        f"investment={stat['investment']} "
        f"return={stat['return']} "
        f"profit={m['profit']} "
        f"ROI={m['roi']:.2f}% "
        f"max_hit={m['max_hit']} "
        f"single_hit_share={m['single_hit_share']:.2f}% "
        f"max_losing_streak={m['max_losing_streak']} "
        f"max_drawdown_yen={m['max_drawdown_yen']} "
        f"max_drawdown_bets={m['max_drawdown_bets']}",
        flush=True,
    )


def _fetch_rows() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select
            s.id,
            s.race_id,
            s.race_date,
            s.venue_code,
            s.race_no,
            s.snapshot_label,
            s.rule_id,
            s.ticket,
            s.odds,
            s.prob,
            s.prob_rank,
            s.market_rank,
            s.raw_ev,
            s.wind_speed_m,
            s.head_avg_st,
            s.head_motor2,
            s.motor2_vs_field,
            s.snapshot_at,
            r.trifecta_ticket as result_ticket,
            r.trifecta_payout_yen as payout_yen,
            r.result_status,
            r.race_status
        from v2_n02_windlt4_final_shadow s
        left join v2_results r
          on r.race_id = s.race_id
        where s.race_date >= %s
          and s.race_date <= %s
          and s.rule_id = any(%s)
        order by
            s.race_date,
            s.snapshot_at,
            s.race_id,
            s.rule_id;
        """,
        (START_DATE, TARGET_DATE, list(RULE_IDS)),
    )


def _add_row(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    stat["rows"] += 1

    result_ticket = _norm_ticket(row.get("result_ticket"))
    payout = _si(row.get("payout_yen"), 0)
    result_status = str(row.get("result_status") or "")
    race_status = str(row.get("race_status") or "")

    if not result_ticket and payout <= 0:
        stat["pending"] += 1
        return

    valid = (
        bool(result_ticket)
        and payout > 0
        and result_status == "official"
        and race_status == "official"
    )

    if not valid:
        stat["invalid"] += 1
        return

    ticket = _norm_ticket(row.get("ticket"))
    hit = ticket == result_ticket
    returned = payout if hit else 0
    profit = returned - UNIT_YEN

    stat["evaluated"] += 1
    stat["investment"] += UNIT_YEN
    stat["return"] += returned
    stat["sequence"].append(profit)

    if hit:
        stat["hits"] += 1
        stat["returns"].append(returned)


def _next_target(evaluated: int) -> Tuple[int, int]:
    for target in REVIEW_TARGETS:
        if evaluated < target:
            return target, target - evaluated
    return REVIEW_TARGETS[-1], 0


def main() -> None:
    print(
        f"✅ report_n02_windlt4_variants_forward_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"PERIOD={START_DATE}..{TARGET_DATE} UNIT_YEN={UNIT_YEN}",
        flush=True,
    )
    print(
        "読み取り専用。DB更新・LINE通知・本番判定変更なし。",
        flush=True,
    )
    print(
        "バックテストは加算せず、Forward Shadowだけを比較します。",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    rows = _fetch_rows()

    by_rule: Dict[str, Dict[str, Any]] = {
        rule_id: _new_stat()
        for rule_id in RULE_IDS
    }
    by_rule_day: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        _new_stat
    )

    for row in rows:
        rule_id = str(row.get("rule_id") or "")
        if rule_id not in by_rule:
            continue

        _add_row(by_rule[rule_id], row)
        day = str(row.get("race_date") or "")[:10]
        _add_row(by_rule_day[(rule_id, day)], row)

    print("\n=== FORWARD VARIANT OVERALL ===", flush=True)
    for rule_id in RULE_IDS:
        _print_stat(rule_id, by_rule[rule_id])

    print("\n=== REVIEW PROGRESS ===", flush=True)
    for rule_id in RULE_IDS:
        stat = by_rule[rule_id]
        target, remain = _next_target(stat["evaluated"])
        print(
            f"{rule_id}: evaluated={stat['evaluated']} "
            f"next_review_target={target} "
            f"remaining={remain}",
            flush=True,
        )

    print("\n=== RELATIVE TO BASELINE ===", flush=True)
    base = by_rule["N02_WIND_LT4"]
    base_m = _metrics(base)

    for rule_id in RULE_IDS[1:]:
        stat = by_rule[rule_id]
        m = _metrics(stat)

        coverage = (
            stat["evaluated"] / base["evaluated"] * 100.0
            if base["evaluated"] > 0
            else 0.0
        )

        print(
            f"{rule_id}: "
            f"coverage_vs_base={coverage:.2f}% "
            f"ROI_delta={m['roi'] - base_m['roi']:+.2f}pt "
            f"hit_rate_delta="
            f"{m['hit_rate'] - base_m['hit_rate']:+.2f}pt "
            f"maxDD_delta="
            f"{m['max_drawdown_yen'] - base_m['max_drawdown_yen']:+d}yen",
            flush=True,
        )

    print("\n=== DAILY BREAKDOWN ===", flush=True)
    days = sorted({day for (_, day) in by_rule_day})
    if not days:
        print("Forward rows=0", flush=True)
    else:
        for day in days:
            print(f"-- {day} --", flush=True)
            for rule_id in RULE_IDS:
                stat = by_rule_day.get((rule_id, day))
                if stat and stat["rows"]:
                    _print_stat(rule_id, stat)

    print("\n=== FIXED CONDITIONS ===", flush=True)
    print(
        "BASE: N02 + wind<4.0",
        flush=True,
    )
    print(
        "ST15: BASE + head_avg_st<=0.1500",
        flush=True,
    )
    print(
        "MOTOR2: BASE + head_motor2>=38.4056",
        flush=True,
    )
    print(
        "MOTOR2_GAP: BASE + motor2_vs_field>=5.7263",
        flush=True,
    )
    print(
        "閾値は2026-08-18時点で固定。Forward結果を見て変更しません。",
        flush=True,
    )

    print("\n=== IMPORTANT NOTE ===", flush=True)
    print(
        "10件=動作確認、30件=一次評価、50件=中間評価、"
        "100件=本番候補レビューの目安です。",
        flush=True,
    )
    print(
        "少数件の高ROIだけでは採用せず、coverage・期間安定性・"
        "最大DDも同時に確認します。",
        flush=True,
    )
    print("RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()