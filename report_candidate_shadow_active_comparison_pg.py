# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from db_pg import fetch_all

VERSION = "2026-08-24 active-shadow-comparison-v1"
JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
REPORT_DAYS = max(1, int(os.getenv("ACTIVE_SHADOW_REPORT_DAYS", "30")))
UNIT_YEN = max(1, int(os.getenv("ACTIVE_SHADOW_UNIT_YEN", "100")))

# Reviewed production Shadow set. This report does not change or infer Railway Variables.
RULE_IDS = ("S01", "S02", "S03", "S04", "S05", "N02")


def _shift_day(date_str: str, days: int) -> str:
    return (
        datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)
    ).strftime("%Y-%m-%d")


def _si(value: Any, default: int = 0) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except Exception:
        return default


def _new_stat() -> Dict[str, Any]:
    return {
        "rows": 0,
        "evaluated": 0,
        "pending": 0,
        "invalid": 0,
        "hits": 0,
        "investment": 0,
        "return": 0,
        "hit_returns": [],
        "dates": set(),
        "recent7_rows": 0,
        "recent7_evaluated": 0,
    }


def _add(stat: Dict[str, Any], row: Dict[str, Any], recent7_start: str) -> None:
    stat["rows"] += 1
    race_date = str(row.get("race_date") or "")[:10]
    if race_date:
        stat["dates"].add(race_date)
        if race_date >= recent7_start:
            stat["recent7_rows"] += 1

    status = str(row.get("evaluation_status") or "")
    if status == "evaluated":
        stat["evaluated"] += 1
        if race_date and race_date >= recent7_start:
            stat["recent7_evaluated"] += 1

        investment = _si(row.get("investment_yen"), UNIT_YEN)
        if investment <= 0:
            investment = UNIT_YEN
        returned = _si(row.get("return_yen"), 0)
        stat["investment"] += investment
        stat["return"] += returned

        if bool(row.get("hit")):
            stat["hits"] += 1
            payout = _si(row.get("payout_yen"), returned)
            if payout > 0:
                stat["hit_returns"].append(payout)
    elif status == "invalid_result":
        stat["invalid"] += 1
    else:
        stat["pending"] += 1


def _metrics(stat: Dict[str, Any]) -> Dict[str, float]:
    evaluated = int(stat["evaluated"])
    hits = int(stat["hits"])
    investment = int(stat["investment"])
    returned = int(stat["return"])
    payouts = sorted((int(x) for x in stat["hit_returns"]), reverse=True)
    max_payout = payouts[0] if payouts else 0
    return {
        "hit_rate": hits / evaluated * 100.0 if evaluated else 0.0,
        "roi": returned / investment * 100.0 if investment else 0.0,
        "single_hit_share": max_payout / returned * 100.0 if returned else 0.0,
        "row_rate_per_day": int(stat["rows"]) / REPORT_DAYS,
        "evaluated_ratio": evaluated / int(stat["rows"]) * 100.0 if stat["rows"] else 0.0,
    }


def _fetch_rows(start_date: str) -> List[Dict[str, Any]]:
    return fetch_all(
        """
        select race_id,race_date,rule_id,ticket,odds,prob,prob_rank,market_rank,
               raw_ev,snapshot_at,investment_yen,result_ticket,payout_yen,hit,
               return_yen,evaluated_at,evaluation_status,evaluation_note
        from v2_candidate_filter_shadow
        where race_date >= %s
          and race_date <= %s
          and rule_id in ('S01','S02','S03','S04','S05','N02')
        order by race_date,rule_id,race_id;
        """,
        (start_date, TARGET_DATE),
    )


def _print_rule(rule_id: str, stat: Dict[str, Any]) -> None:
    m = _metrics(stat)
    dates = sorted(stat["dates"])
    first_date = dates[0] if dates else "-"
    last_date = dates[-1] if dates else "-"
    print(
        f"ACTIVE_SHADOW_RULE={rule_id} "
        f"rows:{stat['rows']} evaluated:{stat['evaluated']} pending:{stat['pending']} "
        f"invalid:{stat['invalid']} hits:{stat['hits']} hit_rate:{m['hit_rate']:.2f}% "
        f"investment:{stat['investment']} return:{stat['return']} ROI:{m['roi']:.2f}% "
        f"single_hit_share:{m['single_hit_share']:.2f}% "
        f"active_days:{len(dates)} rows_per_calendar_day:{m['row_rate_per_day']:.3f} "
        f"evaluated_ratio:{m['evaluated_ratio']:.2f}% "
        f"recent7_rows:{stat['recent7_rows']} recent7_evaluated:{stat['recent7_evaluated']} "
        f"first:{first_date} last:{last_date}",
        flush=True,
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    start_date = _shift_day(TARGET_DATE, -(REPORT_DAYS - 1))
    recent7_start = _shift_day(TARGET_DATE, -6)

    print(f"OK report_candidate_shadow_active_comparison_pg.py VERSION {VERSION}", flush=True)
    print(
        f"ACTIVE_SHADOW_PERIOD={start_date}..{TARGET_DATE} days:{REPORT_DAYS} "
        f"recent7_start:{recent7_start}",
        flush=True,
    )
    print(
        "ACTIVE_SHADOW_RULE_SET=S01,S02,S03,S04,S05,N02",
        flush=True,
    )
    print(
        "ACTIVE_SHADOW_POLICY=read_only_no_db_write_no_line_no_prod_change_no_rule_change_no_promotion",
        flush=True,
    )

    rows = _fetch_rows(start_date)
    stats: Dict[str, Dict[str, Any]] = defaultdict(_new_stat)
    for row in rows:
        rule_id = str(row.get("rule_id") or "UNKNOWN").upper()
        if rule_id in RULE_IDS:
            _add(stats[rule_id], row, recent7_start)

    print(f"ACTIVE_SHADOW_TOTAL_ROWS={len(rows)}", flush=True)
    for rule_id in RULE_IDS:
        _print_rule(rule_id, stats[rule_id])

    counts = {rule_id: int(stats[rule_id]["rows"]) for rule_id in RULE_IDS}
    nonzero = [rule_id for rule_id in RULE_IDS if counts[rule_id] > 0]
    zero = [rule_id for rule_id in RULE_IDS if counts[rule_id] == 0]
    print(
        f"ACTIVE_SHADOW_COVERAGE=nonzero:{','.join(nonzero) or 'none'} "
        f"zero:{','.join(zero) or 'none'}",
        flush=True,
    )
    print(
        "ACTIVE_SHADOW_NOTE=observed_PRE_shadow_rows_only_not_a_production_threshold_recommendation",
        flush=True,
    )
    print("ACTIVE_SHADOW_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
