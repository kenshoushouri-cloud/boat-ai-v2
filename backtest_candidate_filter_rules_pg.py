# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24
import collect_candidate_filter_shadow_pg as shadow

VERSION = "2026-08-18 phase5-historical-rule-backtest-v1"

START_DATE = os.getenv("BACKTEST_START_DATE", "2025-07-01")
END_DATE = os.getenv("BACKTEST_END_DATE", "2026-08-16")
UNIT_YEN = max(1, int(os.getenv("BACKTEST_UNIT_YEN", "100")))
PROGRESS_EVERY_DAYS = max(1, int(os.getenv("BACKTEST_PROGRESS_EVERY_DAYS", "10")))
REQUIRE_ODDS120 = os.getenv("BACKTEST_REQUIRE_ODDS120", "1").strip().lower() in {"1","true","yes","on"}
REQUIRE_K6 = os.getenv("BACKTEST_REQUIRE_K6", "1").strip().lower() in {"1","true","yes","on"}

DEFAULT_RULES = "S01,S02,S03,S04,S05,N01,N02"

def _parse_rule_ids(raw: str) -> set[str]:
    import re
    return {x.strip().upper() for x in re.split(r"[,\\s]+", raw or "") if x.strip()}

REQUESTED_RULE_IDS = _parse_rule_ids(os.getenv("BACKTEST_RULES", DEFAULT_RULES))
RULES_BY_ID = {str(r["rule_id"]).upper(): r for r in shadow.RULES}
ACTIVE_RULES = [RULES_BY_ID[rid] for rid in sorted(REQUESTED_RULE_IDS) if rid in RULES_BY_ID]

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

def _daterange(start_date: str, end_date: str) -> Iterable[str]:
    cur = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)

def _new_stat() -> Dict[str, Any]:
    return {"bets":0,"hits":0,"investment":0,"return":0,"hit_returns":[]}

def _add(stat: Dict[str, Any], hit: bool, payout: int) -> None:
    stat["bets"] += 1
    stat["investment"] += UNIT_YEN
    if hit:
        stat["hits"] += 1
        stat["return"] += payout
        if payout > 0:
            stat["hit_returns"].append(payout)

def _print_stat(label: str, stat: Dict[str, Any]) -> None:
    bets = stat["bets"]
    hits = stat["hits"]
    inv = stat["investment"]
    ret = stat["return"]
    hit_rate = hits / bets * 100.0 if bets else 0.0
    roi = ret / inv * 100.0 if inv else 0.0
    max_hit = max(stat["hit_returns"]) if stat["hit_returns"] else 0
    share = max_hit / ret * 100.0 if ret else 0.0
    print(
        f"{label}: bets={bets} hits={hits} hit_rate={hit_rate:.3f}% "
        f"investment={inv} return={ret} profit={ret-inv} ROI={roi:.2f}% "
        f"max_hit={max_hit} single_hit_share={share:.2f}%",
        flush=True,
    )

def _race_group(race_no: int) -> str:
    if race_no <= 3: return "R01_03"
    if race_no <= 6: return "R04_06"
    if race_no <= 9: return "R07_09"
    return "R10_12"

def _fetch_day(date_str: str):
    day_prefix = date_str.replace("-", "")
    next_prefix = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")

    results = fetch_all(
        """
        select race_id,race_date,trifecta_ticket,trifecta_payout_yen,
               result_status,race_status,finish_order,winning_method
        from v2_results
        where race_date=%s
          and trifecta_ticket is not null
          and trifecta_payout_yen is not null
          and trifecta_payout_yen > 0
          and finish_order is not null
          and winning_method is not null
          and coalesce(result_status,'')='official'
          and coalesce(race_status,'')='official'
        order by race_id;
        """,
        (date_str,),
    )
    result_by = {str(r["race_id"]): r for r in results if r.get("race_id")}
    valid_ids = set(result_by)
    if not valid_ids:
        return [], {}, {}, {}, {}

    races = fetch_all(
        "select * from v2_races where race_date=%s order by venue_id,race_no;",
        (date_str,),
    )
    races = [r for r in races if str(r.get("race_id") or "") in valid_ids]

    entries = fetch_all(
        """
        select race_id,lane,racer_number,racer_class,racer_name,
               national_win_rate,national_place2_rate,
               local_win_rate,local_place2_rate,
               motor_no,boat_no,avg_st
        from v2_race_entries
        where race_id >= %s and race_id < %s
        order by race_id,lane;
        """,
        (day_prefix,next_prefix),
    )
    entries_by = defaultdict(list)
    for r in entries:
        rid = str(r.get("race_id") or "")
        if rid in valid_ids:
            entries_by[rid].append(r)

    odds_rows = fetch_all(
        """
        select race_id,ticket,odds
        from v2_odds_trifecta
        where race_id >= %s and race_id < %s
        order by race_id,ticket;
        """,
        (day_prefix,next_prefix),
    )
    odds_by = defaultdict(dict)
    for r in odds_rows:
        rid = str(r.get("race_id") or "")
        if rid not in valid_ids:
            continue
        t = v24._norm_ticket(r.get("ticket"))
        odd = _safe_float(r.get("odds"), 0.0)
        if t and odd > 0:
            odds_by[rid][t] = odd

    k_counts = {}
    if REQUIRE_K6:
        rows = fetch_all(
            """
            select race_id,count(*)::int as n
            from v2_result_entries
            where race_id >= %s and race_id < %s
            group by race_id;
            """,
            (day_prefix,next_prefix),
        )
        k_counts = {str(r.get("race_id")):_safe_int(r.get("n"),0) for r in rows}

    return races, entries_by, odds_by, result_by, k_counts

def main() -> None:
    print(f"â backtest_candidate_filter_rules_pg.py VERSION {VERSION}", flush=True)
    print(
        f"PERIOD={START_DATE}..{END_DATE} UNIT_YEN={UNIT_YEN} "
        f"REQUIRE_ODDS120={REQUIRE_ODDS120} REQUIRE_K6={REQUIRE_K6}",
        flush=True,
    )
    print("ACTIVE_RULES=" + ",".join(str(r["rule_id"]) for r in ACTIVE_RULES), flush=True)
    print("DBæ¸ãè¾¼ã¿ãªããLINEéç¥ãªãã", flush=True)

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL ãå¿è¦ã§ã")
    if not ACTIVE_RULES:
        raise RuntimeError("æå¹ãªBACKTEST_RULESãããã¾ãã")

    overall = _new_stat()
    by_rule = defaultdict(_new_stat)
    by_rule_month = defaultdict(_new_stat)
    by_rule_venue = defaultdict(_new_stat)
    by_rule_racegrp = defaultdict(_new_stat)
    dedup = {}

    audit = {
        "result_candidate_races":0,
        "ready_races":0,
        "skipped_entries":0,
        "skipped_k":0,
        "skipped_odds":0,
        "rule_selections":0,
    }

    dates = list(_daterange(START_DATE, END_DATE))

    for i, date_str in enumerate(dates, start=1):
        races, entries_by, odds_by, result_by, k_counts = _fetch_day(date_str)
        audit["result_candidate_races"] += len(races)
        event_day_by_venue = v24._compute_event_day_by_venue(date_str) if races else {}

        for race in races:
            rid = str(race.get("race_id") or "")
            venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            race_no = _safe_int(race.get("race_no"), 0)
            entries = entries_by.get(rid, [])

            if len(v24._entry_by_lane(entries)) != 6:
                audit["skipped_entries"] += 1
                continue
            if REQUIRE_K6 and k_counts.get(rid,0) != 6:
                audit["skipped_k"] += 1
                continue

            odds = odds_by.get(rid,{})
            if REQUIRE_ODDS120:
                ready, _ = v24._validate_odds_snapshot(odds)
                if len(odds) != 120 or not ready:
                    audit["skipped_odds"] += 1
                    continue
            elif not odds:
                audit["skipped_odds"] += 1
                continue

            audit["ready_races"] += 1
            result = result_by[rid]
            result_ticket = v24._norm_ticket(result.get("trifecta_ticket"))
            payout = _safe_int(result.get("trifecta_payout_yen"),0)

            meta_text = v24._metadata_text(race)
            venue_style = v24._infer_venue_style(venue_id)
            event_category = v24._infer_event_category(meta_text)
            ranked = v24._rank_candidates(entries, venue_id, odds)

            for rule in ACTIVE_RULES:
                rule_id = str(rule["rule_id"])
                if race_no not in rule["race_nos"]:
                    continue
                if rule["venue_style"] != "ALL" and venue_style != rule["venue_style"]:
                    continue
                if rule["event_category"] != "ALL" and event_category != rule["event_category"]:
                    continue

                matches = [row for row in ranked if shadow._match_rule(row, rule)]
                selected = shadow._select_one(matches, str(rule["select_mode"]))
                if not selected:
                    continue

                ticket = str(selected.get("ticket") or "")
                if not ticket:
                    continue

                hit = ticket == result_ticket
                audit["rule_selections"] += 1
                _add(overall, hit, payout)
                _add(by_rule[rule_id], hit, payout)
                _add(by_rule_month[(rule_id,date_str[:7])], hit, payout)
                _add(by_rule_venue[(rule_id,venue_id)], hit, payout)
                _add(by_rule_racegrp[(rule_id,_race_group(race_no))], hit, payout)
                dedup.setdefault((rid,ticket), {"hit":hit,"payout":payout})

        if i % PROGRESS_EVERY_DAYS == 0 or i == len(dates):
            print(
                f"PROGRESS {i}/{len(dates)} date={date_str} "
                f"ready={audit['ready_races']} selections={audit['rule_selections']} "
                f"skip_entries={audit['skipped_entries']} "
                f"skip_k={audit['skipped_k']} skip_odds={audit['skipped_odds']}",
                flush=True,
            )

    dedup_stat = _new_stat()
    for rec in dedup.values():
        _add(dedup_stat, bool(rec["hit"]), _safe_int(rec["payout"],0))

    print("\n=== AUDIT SUMMARY ===", flush=True)
    for k,v in audit.items():
        print(f"{k}={v}", flush=True)

    print("\n=== OVERALL ===", flush=True)
    _print_stat("RULE_ROWS_TOTAL", overall)
    _print_stat("DEDUP_RACE_TICKET", dedup_stat)

    print("\n=== RULE BREAKDOWN ===", flush=True)
    for rule in ACTIVE_RULES:
        rid = str(rule["rule_id"])
        _print_stat(rid, by_rule[rid])

    print("\n=== RULE x MONTH ===", flush=True)
    for rule in ACTIVE_RULES:
        rid = str(rule["rule_id"])
        months = sorted(m for (r,m) in by_rule_month if r == rid)
        for month in months:
            _print_stat(f"{rid} {month}", by_rule_month[(rid,month)])

    print("\n=== RULE x VENUE ===", flush=True)
    for rule in ACTIVE_RULES:
        rid = str(rule["rule_id"])
        venues = sorted(v for (r,v) in by_rule_venue if r == rid)
        for venue in venues:
            _print_stat(f"{rid} venue={venue}", by_rule_venue[(rid,venue)])

    print("\n=== RULE x RACE_GROUP ===", flush=True)
    for rule in ACTIVE_RULES:
        rid = str(rule["rule_id"])
        for grp in ("R01_03","R04_06","R07_09","R10_12"):
            stat = by_rule_racegrp.get((rid,grp))
            if stat and stat["bets"] > 0:
                _print_stat(f"{rid} {grp}", stat)

    print("\n=== IMPORTANT NOTE ===", flush=True)
    print(
        "ç¾å¨DBã«ä¿å­ããã¦ããv2_odds_trifectaãä½¿ç¨ããããã"
        "éå»è£ä¿®ã§æçµãªããºãä¿å­ãããæéã¯ä»®åè£éç¥æç¹ãªããºãå®å¨åç¾ãã¾ããã"
        "é·æã«ã¼ã«æ§é ã®è©ä¾¡ã¨ãã¦è§£éãã¦ãã ããã",
        flush=True,
    )
    print("RESULT=PASS", flush=True)

if __name__ == "__main__":
    main()