# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))

from db.client import select_where


TARGET_VENUES = ["01", "06", "12", "18", "24"]


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _safe_int(v, default=0):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _count_rows(table, filters):
    try:
        rows = select_where(table, filters)
        return len(rows)
    except Exception as e:
        print(f"COUNT ERROR table={table} filters={filters} error={e}")
        return -1


def _sum_related_rows(races, table, race_id_key="race_id"):
    total = 0
    missing_race_ids = []

    for race in races:
        race_id = race.get("race_id")
        if not race_id:
            continue

        cnt = _count_rows(table, {race_id_key: race_id})
        if cnt < 0:
            continue

        total += cnt
        if cnt == 0:
            missing_race_ids.append(race_id)

    return total, missing_race_ids


def _judge_day_status(race_count, entry_count, result_count, exhibition_count, odds_count):
    if race_count <= 0:
        return "NO_RACES"

    problems = []

    if entry_count <= 0:
        problems.append("entries不足")

    if result_count <= 0:
        problems.append("results不足")

    if exhibition_count <= 0:
        problems.append("exhibition不足")

    if odds_count <= 0:
        problems.append("odds不足")

    if not problems:
        return "OK"

    return " / ".join(problems)


def run_data_coverage_check(start_date_str, end_date_str):
    print("=== データ充足率チェック開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("対象場:", TARGET_VENUES)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    day_logs = []

    total_days = 0
    ok_days = 0
    no_race_days = 0
    problem_days = 0

    for d in daterange(start_date, end_date):
        target_date = d.strftime("%Y-%m-%d")
        total_days += 1

        races = []
        for venue_id in TARGET_VENUES:
            venue_races = select_where(
                "v2_races",
                {
                    "race_date": target_date,
                    "venue_id": venue_id,
                }
            )
            races.extend(venue_races)

        race_count = len(races)

        if race_count == 0:
            status = "NO_RACES"
            no_race_days += 1

            log = {
                "date": target_date,
                "race_count": 0,
                "entry_count": 0,
                "result_count": 0,
                "exhibition_count": 0,
                "odds_count": 0,
                "status": status,
            }
            day_logs.append(log)
            print(log)
            continue

        entry_count, missing_entries = _sum_related_rows(races, "v2_race_entries")
        result_count, missing_results = _sum_related_rows(races, "v2_results")
        exhibition_count, missing_exhibition = _sum_related_rows(races, "v2_exhibition")
        odds_count, missing_odds = _sum_related_rows(races, "v2_odds_trifecta")

        status = _judge_day_status(
            race_count=race_count,
            entry_count=entry_count,
            result_count=result_count,
            exhibition_count=exhibition_count,
            odds_count=odds_count,
        )

        if status == "OK":
            ok_days += 1
        else:
            problem_days += 1

        log = {
            "date": target_date,
            "race_count": race_count,
            "entry_count": entry_count,
            "result_count": result_count,
            "exhibition_count": exhibition_count,
            "odds_count": odds_count,
            "status": status,
            "missing_entries_races": missing_entries[:5],
            "missing_results_races": missing_results[:5],
            "missing_exhibition_races": missing_exhibition[:5],
            "missing_odds_races": missing_odds[:5],
        }
        day_logs.append(log)
        print(log)

    print("\n=== 集計 ===")
    print({
        "total_days": total_days,
        "ok_days": ok_days,
        "no_race_days": no_race_days,
        "problem_days": problem_days,
    })

    print("\n=== 問題日だけ再表示 ===")
    for row in day_logs:
        if row["status"] != "OK":
            print(row)

    return day_logs


if __name__ == "__main__":
    run_data_coverage_check("2026-01-01", "2026-04-20")
