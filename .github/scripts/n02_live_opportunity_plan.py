# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# Safety before importing the v24 probability/ranking helpers.
os.environ.pop("TARGET_RACE_IDS", None)
os.environ["PRE_SESSION"] = "all"
os.environ["DRY_RUN"] = "1"
os.environ["TEST_MODE"] = "1"

import v24_pre_candidate_notifier_pg as v24  # noqa: E402

VERSION = "2026-08-24 n02-live-opportunity-v1"
JST = timezone(timedelta(hours=9))
N02_RACE_NOS = {7, 8, 9, 10}
SAMPLE_LIMIT = max(1, min(20, int(os.getenv("N02_LIVE_SAMPLE_LIMIT", "10"))))


def _si(value: Any, default: int = 0) -> int:
    return v24._safe_int(value, default)


def _sf(value: Any, default: float = 0.0) -> float:
    return v24._safe_float(value, default)


def _deadline_at(race: Dict[str, Any], target_date: str) -> Optional[datetime]:
    value = race.get("deadline_at")
    if isinstance(value, datetime):
        return value.replace(tzinfo=JST) if value.tzinfo is None else value.astimezone(JST)
    if value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.replace(tzinfo=JST) if dt.tzinfo is None else dt.astimezone(JST)
        except Exception:
            pass

    deadline_time = str(race.get("deadline_time") or "").strip()
    if deadline_time:
        try:
            return datetime.strptime(
                f"{target_date} {deadline_time}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=JST)
        except Exception:
            return None
    return None


def _range_gap_int(value: int, lower: int, upper: int) -> int:
    if value < lower:
        return lower - value
    if value > upper:
        return value - upper
    return 0


def _range_gap_float10(value: float, lower: float, upper_exclusive: float) -> int:
    if value < lower:
        return int(round((lower - value) * 10))
    if value >= upper_exclusive:
        return int(round((value - upper_exclusive) * 10)) + 1
    return 0


def _row_state(row: Dict[str, Any]) -> Tuple[bool, bool, bool, int, int, int]:
    pr = _si(row.get("prob_rank"), 999)
    mr = _si(row.get("market_rank"), 999)
    odds = _sf(row.get("odds"), 0.0)
    pr_gap = _range_gap_int(pr, 11, 20)
    mr_gap = _range_gap_int(mr, 2, 5)
    odds_gap10 = _range_gap_float10(odds, 3.0, 6.0)
    return pr_gap == 0, mr_gap == 0, odds_gap10 == 0, pr_gap, mr_gap, odds_gap10


def _select_ev(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            _sf(row.get("raw_ev"), 0.0),
            _sf(row.get("prob"), 0.0),
        ),
    )


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    now_jst = datetime.now(JST)
    target_date = now_jst.strftime("%Y-%m-%d")
    races, entries_by, odds_by = v24._fetch_live_day_rows(target_date)

    future: List[Dict[str, Any]] = []
    no_deadline = 0
    for race in races:
        deadline = _deadline_at(race, target_date)
        if deadline is None:
            no_deadline += 1
            continue
        if deadline > now_jst:
            future.append(race)

    eligible = [race for race in future if _si(race.get("race_no"), 0) in N02_RACE_NOS]

    stage = Counter()
    exact_selected: List[Dict[str, Any]] = []
    near_per_race: List[Dict[str, Any]] = []
    skipped_entries = 0
    skipped_odds = 0

    for race in eligible:
        race_id = str(race.get("race_id") or "")
        venue_id = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = _si(race.get("race_no"), 0)
        deadline = _deadline_at(race, target_date)
        entries = entries_by.get(race_id, [])
        odds = odds_by.get(race_id, {})

        if len(v24._entry_by_lane(entries)) != 6:
            skipped_entries += 1
            continue
        ready, _reason = v24._validate_odds_snapshot(odds)
        if not ready:
            skipped_odds += 1
            continue

        stage["ready_races"] += 1
        ranked = v24._rank_candidates(entries, venue_id, odds)
        exact_rows: List[Dict[str, Any]] = []
        race_near: List[Dict[str, Any]] = []

        for row in ranked:
            pr_ok, mr_ok, odds_ok, pr_gap, mr_gap, odds_gap10 = _row_state(row)
            if pr_ok:
                stage["pr"] += 1
            if mr_ok:
                stage["mr"] += 1
            if odds_ok:
                stage["odds"] += 1
            if pr_ok and mr_ok:
                stage["pr_mr"] += 1
            if pr_ok and odds_ok:
                stage["pr_odds"] += 1
            if mr_ok and odds_ok:
                stage["mr_odds"] += 1
            if pr_ok and mr_ok and odds_ok:
                stage["exact_tickets"] += 1
                exact_rows.append(row)

            passed = int(pr_ok) + int(mr_ok) + int(odds_ok)
            race_near.append(
                {
                    "race_id": race_id,
                    "venue_id": venue_id,
                    "race_no": race_no,
                    "deadline": deadline.strftime("%H:%M") if deadline else "-",
                    "ticket": str(row.get("ticket") or ""),
                    "prob_rank": _si(row.get("prob_rank"), 999),
                    "market_rank": _si(row.get("market_rank"), 999),
                    "odds": _sf(row.get("odds"), 0.0),
                    "raw_ev": _sf(row.get("raw_ev"), 0.0),
                    "passed": passed,
                    "pr_gap": pr_gap,
                    "mr_gap": mr_gap,
                    "odds_gap10": odds_gap10,
                }
            )

        if exact_rows:
            stage["exact_races"] += 1
            selected = _select_ev(exact_rows)
            if selected:
                exact_selected.append(
                    {
                        "race_id": race_id,
                        "venue_id": venue_id,
                        "race_no": race_no,
                        "deadline": deadline.strftime("%H:%M") if deadline else "-",
                        "ticket": str(selected.get("ticket") or ""),
                        "prob_rank": _si(selected.get("prob_rank"), 999),
                        "market_rank": _si(selected.get("market_rank"), 999),
                        "odds": _sf(selected.get("odds"), 0.0),
                        "raw_ev": _sf(selected.get("raw_ev"), 0.0),
                    }
                )

        non_exact = [row for row in race_near if row["passed"] < 3]
        if non_exact:
            non_exact.sort(
                key=lambda row: (
                    -row["passed"],
                    row["pr_gap"] + row["mr_gap"] + row["odds_gap10"],
                    -row["raw_ev"],
                )
            )
            near_per_race.append(non_exact[0])

    near_per_race.sort(
        key=lambda row: (
            -row["passed"],
            row["pr_gap"] + row["mr_gap"] + row["odds_gap10"],
            -row["raw_ev"],
            row["deadline"],
        )
    )

    print(f"N02_LIVE_MODE=read_only_current_future VERSION={VERSION}", flush=True)
    print(
        "N02_LIVE_POLICY=no_ddl_no_db_write_no_line_no_shadow_save_no_prod_change_no_rule_change_no_promotion",
        flush=True,
    )
    print(
        "N02_LIVE_SOURCE=current_v2_odds_trifecta_not_frozen_exact_PRE_snapshot",
        flush=True,
    )
    print(f"N02_LIVE_NOW_JST={now_jst.isoformat(timespec='seconds')}", flush=True)
    print(
        f"N02_LIVE_SCOPE=day_races:{len(races)} future:{len(future)} "
        f"eligible_R07_R10:{len(eligible)} no_deadline:{no_deadline}",
        flush=True,
    )
    print(
        f"N02_LIVE_READY=ready:{stage['ready_races']} skipped_entries:{skipped_entries} "
        f"skipped_odds:{skipped_odds}",
        flush=True,
    )
    print(
        f"N02_LIVE_STAGE=pr11_20:{stage['pr']} mr2_5:{stage['mr']} odds3_6:{stage['odds']} "
        f"pr_mr:{stage['pr_mr']} pr_odds:{stage['pr_odds']} mr_odds:{stage['mr_odds']} "
        f"exact_tickets:{stage['exact_tickets']} exact_races:{stage['exact_races']}",
        flush=True,
    )

    if exact_selected:
        for row in exact_selected[:SAMPLE_LIMIT]:
            print(
                f"N02_LIVE_EXACT=race:{row['race_id']} deadline:{row['deadline']} "
                f"ticket:{row['ticket']} pr:{row['prob_rank']} mr:{row['market_rank']} "
                f"odds:{row['odds']:.1f} raw_ev:{row['raw_ev']:.6f}",
                flush=True,
            )
    else:
        print("N02_LIVE_EXACT=none", flush=True)

    if near_per_race:
        for row in near_per_race[:SAMPLE_LIMIT]:
            print(
                f"N02_LIVE_NEAR=race:{row['race_id']} deadline:{row['deadline']} "
                f"ticket:{row['ticket']} pr:{row['prob_rank']} mr:{row['market_rank']} "
                f"odds:{row['odds']:.1f} passed:{row['passed']}/3 "
                f"gaps:pr{row['pr_gap']},mr{row['mr_gap']},odds10:{row['odds_gap10']}",
                flush=True,
            )
    else:
        print("N02_LIVE_NEAR=none", flush=True)

    print("N02_LIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
