# -*- coding: utf-8 -*-
"""Result-blind read-only historical matched-contract input readiness audit.

This audit measures input availability only. It intentionally does not read
outcomes, payouts, odds, predictions, or economic results.

Historical reconstructed Course and Opponent evidence remain separately
labeled and are never treated as prospective evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

COURSE_PROXY_SOURCE = "boatrace_official_k_applied_term_proxy"
HISTORICAL_OPPONENT_MODEL_VERSION = 102


def expected_course_snapshot(race_date: date) -> date | None:
    if date(2025, 7, 1) <= race_date <= date(2025, 12, 31):
        return date(2025, 4, 30)
    if date(2026, 1, 1) <= race_date <= date(2026, 6, 30):
        return date(2025, 10, 31)
    if date(2026, 7, 1) <= race_date <= date(2026, 12, 31):
        return date(2026, 4, 30)
    return None


def _finite(v: Any) -> bool:
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def opponent_valid(row: dict[str, Any]) -> bool:
    if int(row.get("model_version") or 0) != HISTORICAL_OPPONENT_MODEL_VERSION:
        return False
    race_date = row.get("race_date")
    train_end = row.get("train_end")
    if isinstance(race_date, str):
        race_date = date.fromisoformat(race_date)
    if isinstance(train_end, str):
        train_end = date.fromisoformat(train_end)
    if not isinstance(race_date, date) or not isinstance(train_end, date):
        return False
    if train_end >= race_date:
        return False
    matched = row.get("matched_opponents")
    base = row.get("base_win")
    adj = row.get("adj_win")
    if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
        return False
    try:
        if any(int(x) < 4 for x in matched):
            return False
    except Exception:
        return False
    return all(_finite(x) for x in base) and all(_finite(x) for x in adj)


def audit(start_date: str, end_date: str) -> dict[str, Any]:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute(
                """
                with races as (
                  select race_id,race_date
                    from v2_races
                   where race_date between %s and %s
                ),
                ent as (
                  select e.race_id,
                         count(*) as entry_rows,
                         count(distinct e.lane) as lane_count,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.racer_number is not null
                             and nullif(trim(e.racer_class::text),'') is not null
                             and e.national_win_rate between 0 and 100
                             and e.national_place2_rate between 0 and 100
                             and e.local_place2_rate between 0 and 100
                             and e.avg_st is not null
                         ) as base_n,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.motor_place2_rate between 0 and 100
                         ) as motor_n,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.f_count is not null
                             and e.f_count >= 0
                         ) as fcount_n,
                         count(*) filter(
                           where e.lane between 1 and 6
                             and e.recent_form is not null
                             and e.recent_form::text not in ('null','[]','{}','""','')
                         ) as recent_n
                    from v2_race_entries e
                    join races r using(race_id)
                   group by e.race_id
                ),
                course_proxy as (
                  select e.race_id,
                         count(distinct e.lane) filter(
                           where c.top3_rate between 0 and 100
                         ) as course_n
                    from v2_race_entries e
                    join races r using(race_id)
                    left join v2_racer_course_stats_snapshots c
                      on c.racer_number=e.racer_number
                     and c.course=e.lane
                     and c.source=%s
                     and c.snapshot_date=case
                         when r.race_date between date '2025-07-01' and date '2025-12-31'
                           then date '2025-04-30'
                         when r.race_date between date '2026-01-01' and date '2026-06-30'
                           then date '2025-10-31'
                         when r.race_date between date '2026-07-01' and date '2026-12-31'
                           then date '2026-04-30'
                         else null
                       end
                   where e.lane between 1 and 6
                   group by e.race_id
                ),
                ex as (
                  select e.race_id,
                         count(*) filter(
                           where e.snapshot_label='historical'
                             and e.exhibition_time is not null
                         ) as time_n,
                         count(*) filter(
                           where e.snapshot_label='historical'
                             and e.start_timing is not null
                         ) as st_n
                    from v2_realtime_exhibition_snapshots e
                    join races r using(race_id)
                   group by e.race_id
                ),
                wx as (
                  select w.race_id,
                         max((w.snapshot_label='historical'
                              and w.temperature_c is not null)::int) as temp_ok,
                         max((w.snapshot_label='historical'
                              and w.water_temperature_c is not null)::int) as water_ok,
                         max((w.snapshot_label='historical'
                              and w.wind_speed_m is not null)::int) as wind_ok,
                         max((w.snapshot_label='historical'
                              and w.wave_height_cm is not null)::int) as wave_ok
                    from v2_realtime_weather_snapshots w
                    join races r using(race_id)
                   group by w.race_id
                )
                select r.race_id,r.race_date,
                       coalesce(ent.entry_rows,0) as entry_rows,
                       coalesce(ent.lane_count,0) as lane_count,
                       coalesce(ent.base_n,0) as base_n,
                       coalesce(ent.motor_n,0) as motor_n,
                       coalesce(ent.fcount_n,0) as fcount_n,
                       coalesce(ent.recent_n,0) as recent_n,
                       coalesce(course_proxy.course_n,0) as course_n,
                       coalesce(ex.time_n,0) as exhibition_time_n,
                       coalesce(ex.st_n,0) as exhibition_st_n,
                       coalesce(wx.temp_ok,0) as temp_ok,
                       coalesce(wx.water_ok,0) as water_ok,
                       coalesce(wx.wind_ok,0) as wind_ok,
                       coalesce(wx.wave_ok,0) as wave_ok
                  from races r
                  left join ent using(race_id)
                  left join course_proxy using(race_id)
                  left join ex using(race_id)
                  left join wx using(race_id)
                 order by r.race_date,r.race_id
                """,
                (start_date, end_date, COURSE_PROXY_SOURCE),
            )
            race_rows = [dict(x) for x in cur.fetchall()]

            cur.execute(
                """
                select race_id,race_date,model_version,train_end,
                       matched_opponents,base_win,adj_win
                  from v2_opponent_pressure_shadow_v2
                 where race_date between %s and %s
                   and model_version=%s
                 order by race_date,race_id
                """,
                (start_date, end_date, HISTORICAL_OPPONENT_MODEL_VERSION),
            )
            opponent_rows = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    valid_opp = {str(x["race_id"]) for x in opponent_rows if opponent_valid(x)}
    monthly: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "races": 0,
            "exact6_entries": 0,
            "v4_base6": 0,
            "motor6": 0,
            "v4_base_motor6": 0,
            "fcount6": 0,
            "course_proxy6": 0,
            "opponent_replay": 0,
            "v4_full_reconstructed_core": 0,
            "complete_beforeinfo": 0,
            "core_plus_beforeinfo": 0,
            "recent_form_nonempty_rows": 0,
            "recent_form6": 0,
            "core_plus_recent_form": 0,
            "all_optional_inputs": 0,
        }
    )

    for row in race_rows:
        race_id = str(row["race_id"])
        race_date = row["race_date"]
        if isinstance(race_date, str):
            race_date = date.fromisoformat(race_date)
        month = race_date.strftime("%Y-%m")
        m = monthly[month]
        m["races"] += 1

        exact6 = int(row["entry_rows"]) == 6 and int(row["lane_count"]) == 6
        base6 = exact6 and int(row["base_n"]) == 6
        motor6 = exact6 and int(row["motor_n"]) == 6
        fcount6 = exact6 and int(row["fcount_n"]) == 6
        recent6 = exact6 and int(row["recent_n"]) == 6
        course6 = exact6 and int(row["course_n"]) == 6 and expected_course_snapshot(race_date) is not None
        opp = race_id in valid_opp
        beforeinfo = (
            int(row["exhibition_time_n"]) == 6
            and int(row["exhibition_st_n"]) == 6
            and int(row["temp_ok"]) == 1
            and int(row["water_ok"]) == 1
            and int(row["wind_ok"]) == 1
            and int(row["wave_ok"]) == 1
        )
        base_motor = base6 and motor6
        full_core = base_motor and course6 and opp

        m["exact6_entries"] += int(exact6)
        m["v4_base6"] += int(base6)
        m["motor6"] += int(motor6)
        m["v4_base_motor6"] += int(base_motor)
        m["fcount6"] += int(fcount6)
        m["course_proxy6"] += int(course6)
        m["opponent_replay"] += int(opp)
        m["v4_full_reconstructed_core"] += int(full_core)
        m["complete_beforeinfo"] += int(beforeinfo)
        m["core_plus_beforeinfo"] += int(full_core and beforeinfo)
        m["recent_form_nonempty_rows"] += int(row["recent_n"])
        m["recent_form6"] += int(recent6)
        m["core_plus_recent_form"] += int(full_core and recent6)
        m["all_optional_inputs"] += int(full_core and beforeinfo and fcount6 and recent6)

    months = []
    totals: dict[str, int] = defaultdict(int)
    for month in sorted(monthly):
        row = {"month": month, **monthly[month]}
        races = max(1, row["races"])
        row["v4_full_reconstructed_core_pct"] = round(
            100.0 * row["v4_full_reconstructed_core"] / races, 2
        )
        row["core_plus_beforeinfo_pct"] = round(
            100.0 * row["core_plus_beforeinfo"] / races, 2
        )
        months.append(row)
        for key, value in monthly[month].items():
            totals[key] += int(value)

    total_races = max(1, totals["races"])
    summary = dict(totals)
    summary["v4_full_reconstructed_core_pct"] = round(
        100.0 * totals["v4_full_reconstructed_core"] / total_races, 2
    )
    summary["core_plus_beforeinfo_pct"] = round(
        100.0 * totals["core_plus_beforeinfo"] / total_races, 2
    )

    return {
        "contract": "HISTORICAL_MATCHED_CONTRACT_READINESS_V1",
        "period": [start_date, end_date],
        "labels": {
            "course": "historical_reconstruction",
            "opponent": "historical_reconstruction",
            "beforeinfo": "historical",
            "fcount": "historical_pre_race_input",
            "prospective_gate_credit": False,
        },
        "safety": {
            "transaction_read_only": True,
            "outcome_tables_read": False,
            "odds_read": False,
            "payout_read": False,
            "db_write": False,
            "production_change": False,
            "purchase_action": False,
        },
        "months": months,
        "totals": summary,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default="2025-07-01")
    ap.add_argument("--end-date", default="2026-09-29")
    ap.add_argument("--output", default="historical-matched-contract-readiness.json")
    args = ap.parse_args()
    payload = audit(args.start_date, args.end_date)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    for row in payload["months"]:
        print(
            "HIST_MATCHED_READINESS_MONTH="
            + json.dumps(row, sort_keys=True),
            flush=True,
        )
    print(
        "HIST_MATCHED_READINESS_TOTAL="
        + json.dumps(payload["totals"], sort_keys=True),
        flush=True,
    )
    print("HIST_MATCHED_READINESS_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
