# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

os.environ["DRY_RUN"] = "1"
os.environ["TEST_MODE"] = "1"
os.environ["PRE_SESSION"] = "all"
os.environ.pop("TARGET_RACE_IDS", None)

import n02_live_opportunity_plan as base  # noqa: E402

VERSION = "2026-08-24 phase4-n01-n02-live-v1"
v24 = base.v24
JST = base.JST

RULES = {
    "N01": {
        "race_nos": {7, 8, 9, 10, 11, 12},
        "pr_min": 11,
        "pr_max": 25,
        "mr_min": 2,
        "mr_max": 5,
        "odds_min": 3.0,
        "odds_max": 6.0,
        "status": "hypothetical_not_activated",
    },
    "N02": {
        "race_nos": {7, 8, 9, 10},
        "pr_min": 11,
        "pr_max": 20,
        "mr_min": 2,
        "mr_max": 5,
        "odds_min": 3.0,
        "odds_max": 6.0,
        "status": "reviewed_active_shadow_rule",
    },
}


def _bucket(odds: float) -> str:
    if odds < 3.0:
        return "lt3"
    if odds < 6.0:
        return "3_6"
    if odds < 10.0:
        return "6_10"
    if odds < 15.0:
        return "10_15"
    if odds < 20.0:
        return "15_20"
    if odds < 30.0:
        return "20_30"
    return "30plus"


def _match_rank(row: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    pr = base._si(row.get("prob_rank"), 999)
    mr = base._si(row.get("market_rank"), 999)
    return (
        rule["pr_min"] <= pr <= rule["pr_max"]
        and rule["mr_min"] <= mr <= rule["mr_max"]
    )


def _match_exact(row: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    if not _match_rank(row, rule):
        return False
    odds = base._sf(row.get("odds"), 0.0)
    return rule["odds_min"] <= odds < rule["odds_max"]


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    now_jst = datetime.now(JST)
    target_date = now_jst.strftime("%Y-%m-%d")
    races, entries_by, odds_by = v24._fetch_live_day_rows(target_date)

    future: List[Dict[str, Any]] = []
    for race in races:
        deadline = base._deadline_at(race, target_date)
        if deadline is not None and deadline > now_jst:
            future.append(race)

    print(f"PHASE4_LIVE_MODE=read_only_current_future VERSION={VERSION}", flush=True)
    print(
        "PHASE4_LIVE_POLICY=no_ddl_no_db_write_no_line_no_shadow_save_no_prod_change_no_rule_activation_no_promotion",
        flush=True,
    )
    print(
        "PHASE4_LIVE_SOURCE=current_v2_odds_trifecta_not_frozen_exact_PRE_snapshot",
        flush=True,
    )
    print(f"PHASE4_LIVE_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print(f"PHASE4_LIVE_SCOPE=day_races:{len(races)} future:{len(future)}", flush=True)

    for rule_id, rule in RULES.items():
        eligible = [
            race for race in future
            if base._si(race.get("race_no"), 0) in rule["race_nos"]
        ]
        c = Counter()
        odds_buckets = Counter()
        selected_rows: List[Dict[str, Any]] = []

        for race in eligible:
            race_id = str(race.get("race_id") or "")
            venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            race_no = base._si(race.get("race_no"), 0)
            deadline = base._deadline_at(race, target_date)
            entries = entries_by.get(race_id, [])
            odds = odds_by.get(race_id, {})

            if len(v24._entry_by_lane(entries)) != 6:
                c["skipped_entries"] += 1
                continue
            ready, _reason = v24._validate_odds_snapshot(odds)
            if not ready:
                c["skipped_odds"] += 1
                continue

            c["ready"] += 1
            ranked = v24._rank_candidates(entries, venue_id, odds)
            exact = []
            for row in ranked:
                if _match_rank(row, rule):
                    c["rank_pair_rows"] += 1
                    odds_buckets[_bucket(base._sf(row.get("odds"), 0.0))] += 1
                if _match_exact(row, rule):
                    c["exact_tickets"] += 1
                    exact.append(row)

            selected = base._select_ev(exact)
            if selected:
                c["exact_races"] += 1
                selected_rows.append(
                    {
                        "race_id": race_id,
                        "race_no": race_no,
                        "deadline": deadline.strftime("%H:%M") if deadline else "-",
                        "ticket": str(selected.get("ticket") or ""),
                        "pr": base._si(selected.get("prob_rank"), 999),
                        "mr": base._si(selected.get("market_rank"), 999),
                        "odds": base._sf(selected.get("odds"), 0.0),
                        "raw_ev": base._sf(selected.get("raw_ev"), 0.0),
                    }
                )

        print(
            f"PHASE4_LIVE_RULE={rule_id} status:{rule['status']} eligible:{len(eligible)} "
            f"ready:{c['ready']} skipped_entries:{c['skipped_entries']} skipped_odds:{c['skipped_odds']} "
            f"rank_pair_rows:{c['rank_pair_rows']} exact_tickets:{c['exact_tickets']} "
            f"exact_races:{c['exact_races']}",
            flush=True,
        )
        print(
            f"PHASE4_LIVE_ODDS={rule_id} "
            f"lt3:{odds_buckets['lt3']} 3_6:{odds_buckets['3_6']} "
            f"6_10:{odds_buckets['6_10']} 10_15:{odds_buckets['10_15']} "
            f"15_20:{odds_buckets['15_20']} 20_30:{odds_buckets['20_30']} "
            f"30plus:{odds_buckets['30plus']}",
            flush=True,
        )
        if selected_rows:
            for row in selected_rows[:5]:
                print(
                    f"PHASE4_LIVE_EXACT={rule_id} race:{row['race_id']} deadline:{row['deadline']} "
                    f"ticket:{row['ticket']} pr:{row['pr']} mr:{row['mr']} "
                    f"odds:{row['odds']:.1f} raw_ev:{row['raw_ev']:.6f}",
                    flush=True,
                )
        else:
            print(f"PHASE4_LIVE_EXACT={rule_id} none", flush=True)

    print(
        "PHASE4_LIVE_NOTE=N01_is_hypothetical_only_and_was_not_activated",
        flush=True,
    )
    print("PHASE4_LIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
