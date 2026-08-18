# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-18 n02-forward-performance-v1"

TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("N02_FORWARD_START_DATE", "2026-08-18")
UNIT_YEN = max(1, int(os.getenv("N02_FORWARD_UNIT_YEN", "100")))

BACKTEST_REFERENCE = {
    "bets": 154,
    "hits": 45,
    "hit_rate": 29.221,
    "roi": 159.42,
    "max_losing_streak": 8,
    "max_drawdown_yen": 920,
}

def _safe_int(v: Any, d: int = 0) -> int:
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def _new_stat() -> Dict[str, Any]:
    return {"rows": 0, "evaluated": 0, "hits": 0, "investment": 0, "return": 0}

def _add(stat: Dict[str, Any], row: Dict[str, Any]) -> None:
    stat["rows"] += 1
    if str(row.get("evaluation_status") or "") != "evaluated":
        return
    stat["evaluated"] += 1
    inv = _safe_int(row.get("investment_yen"), UNIT_YEN)
    if inv <= 0:
        inv = UNIT_YEN
    ret = _safe_int(row.get("return_yen"), 0)
    stat["investment"] += inv
    stat["return"] += ret
    if bool(row.get("hit")):
        stat["hits"] += 1

def _metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    e = int(stat["evaluated"])
    h = int(stat["hits"])
    inv = int(stat["investment"])
    ret = int(stat["return"])
    return {
        "evaluated": e,
        "hits": h,
        "investment": inv,
        "return": ret,
        "profit": ret - inv,
        "hit_rate": h / e * 100.0 if e else 0.0,
        "roi": ret / inv * 100.0 if inv else 0.0,
    }

def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    print(
        f"{label}: rows={stat['rows']} evaluated={int(m['evaluated'])} "
        f"hits={int(m['hits'])} hit_rate={m['hit_rate']:.2f}% "
        f"investment={int(m['investment'])} return={int(m['return'])} "
        f"profit={int(m['profit'])} ROI={m['roi']:.2f}%",
        flush=True,
    )

def _status(evaluated: int) -> str:
    if evaluated < 10:
        return "COLLECTING"
    if evaluated < 30:
        return "EARLY"
    if evaluated < 50:
        return "FIRST_REVIEW"
    if evaluated < 100:
        return "MID_REVIEW"
    return "FULL_REVIEW"

def _fetch_rows() -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select id,race_id,race_date,venue_id,race_no,window_name,rule_id,ticket,odds,
               prob,prob_rank,market_rank,raw_ev,snapshot_at,investment_yen,
               result_ticket,payout_yen,hit,return_yen,evaluated_at,
               evaluation_status,evaluation_note
        from v2_candidate_filter_shadow
        where rule_id = 'N02'
          and race_date >= %s
          and race_date <= %s
        order by race_date,snapshot_at,race_id,id;
        """,
        (START_DATE, TARGET_DATE),
    )

def _risk(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    eval_rows = [r for r in rows if str(r.get("evaluation_status") or "") == "evaluated"]
    streak = max_streak = 0
    equity = peak = 0
    peak_idx = 0
    max_dd = 0
    max_dd_bets = 0

    for i, row in enumerate(eval_rows, 1):
        hit = bool(row.get("hit"))
        if hit:
            streak = 0
        else:
            streak += 1
            max_streak = max(max_streak, streak)

        inv = _safe_int(row.get("investment_yen"), UNIT_YEN)
        if inv <= 0:
            inv = UNIT_YEN
        ret = _safe_int(row.get("return_yen"), 0)
        equity += ret - inv

        if equity > peak:
            peak = equity
            peak_idx = i

        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_bets = i - peak_idx

    return {
        "max_losing_streak": max_streak,
        "max_drawdown_yen": max_dd,
        "max_drawdown_bets": max_dd_bets,
    }

def main() -> None:
    print(f"â report_n02_forward_performance_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{TARGET_DATE}", flush=True)
    print("N02å°ç¨ãã©ã¯ã¼ãéè¨ãããã¯ãã¹ãçµæã»ä»ã«ã¼ã«ã¯æ··ãã¾ããã", flush=True)
    print("èª­ã¿åãå°ç¨ã§ããDBæ´æ°ã»LINEéç¥ã»æ¬çªå¤å®å¤æ´ã¯ããã¾ããã", flush=True)

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ãã")

    rows = _fetch_rows()
    overall = _new_stat()
    by_day = defaultdict(_new_stat)
    by_month = defaultdict(_new_stat)

    pending = 0
    invalid = 0

    for row in rows:
        _add(overall, row)
        day = str(row.get("race_date") or "")[:10]
        month = day[:7]
        _add(by_day[day], row)
        _add(by_month[month], row)

        status = str(row.get("evaluation_status") or "")
        if status == "invalid_result":
            invalid += 1
        elif status != "evaluated":
            pending += 1

    m = _metrics(overall)
    risk = _risk(rows)
    evaluated = int(m["evaluated"])

    print("\n=== N02 FORWARD OVERALL ===", flush=True)
    _print_stat("N02 FORWARD", overall)
    print(f"pending_rows={pending}", flush=True)
    print(f"invalid_result_rows={invalid}", flush=True)

    print("\n=== N02 FORWARD RISK ===", flush=True)
    print(f"max_losing_streak={risk['max_losing_streak']}", flush=True)
    print(f"max_drawdown_yen={risk['max_drawdown_yen']}", flush=True)
    print(f"max_drawdown_bets={risk['max_drawdown_bets']}", flush=True)

    print("\n=== N02 FORWARD DAILY ===", flush=True)
    if by_day:
        for day in sorted(by_day):
            _print_stat(day, by_day[day])
    else:
        print("N02 forward rows=0", flush=True)

    print("\n=== N02 FORWARD MONTHLY ===", flush=True)
    if by_month:
        for month in sorted(by_month):
            _print_stat(month, by_month[month])
    else:
        print("N02 forward rows=0", flush=True)

    print("\n=== N02 FORWARD STATUS ===", flush=True)
    print(f"STATUS={_status(evaluated)}", flush=True)
    print(f"evaluated={evaluated}", flush=True)

    if evaluated < 10:
        target = 10
    elif evaluated < 30:
        target = 30
    elif evaluated < 50:
        target = 50
    elif evaluated < 100:
        target = 100
    else:
        target = None

    if target is None:
        print("next_review_target=FULL_REVIEW", flush=True)
    else:
        print(f"next_review_target={target}", flush=True)
        print(f"remaining_to_next_review={target - evaluated}", flush=True)

    print("\n=== BACKTEST REFERENCE ONLY ===", flush=True)
    print("â»åèå¤ã®ã¿ããã©ã¯ã¼ãæç¸¾ã«ã¯å ç®ãã¾ããã", flush=True)
    print(
        f"bets={BACKTEST_REFERENCE['bets']} hits={BACKTEST_REFERENCE['hits']} "
        f"hit_rate={BACKTEST_REFERENCE['hit_rate']:.3f}% ROI={BACKTEST_REFERENCE['roi']:.2f}% "
        f"max_losing_streak={BACKTEST_REFERENCE['max_losing_streak']} "
        f"max_drawdown_yen={BACKTEST_REFERENCE['max_drawdown_yen']}",
        flush=True,
    )

    print("\n=== IMPORTANT NOTE ===", flush=True)
    print("N02æ¡ä»¶ã¯åºå®ããã¾ã¾è©ä¾¡ãã¦ãã ããã", flush=True)
    print("10ä»¶=åä½ç¢ºèªã30ä»¶=ä¸æ¬¡è©ä¾¡ã50ä»¶=ä¸­éè©ä¾¡ã100ä»¶=æ¬çªæ¡ç¨å¤æ­åè£ã§ãã", flush=True)
    print("RESULT=PASS", flush=True)

if __name__ == "__main__":
    main()