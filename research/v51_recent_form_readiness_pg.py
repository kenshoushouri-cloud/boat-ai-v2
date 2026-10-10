# -*- coding: utf-8 -*-
"""Read-only readiness audit for V51_RECENT_FORM_LAST5_TOP3_V1.

This audit reads only race/entry rows and the already-stored recent_form JSON.
It never reads outcomes, payouts, odds, or post-race settlement tables.

Candidate readiness contract:
- recent_form must be a JSON array with 1..5 prior records;
- every record source must be official_k_file;
- every record race_date must be a valid ISO-like YYYY-MM-DD string strictly
  earlier than the target race_date;
- at least 3 records with numeric finish_position 1..6 are required for a lane;
- lane feature = count(finish 1..3) / count(valid finish 1..6);
- a race can express a non-neutral Recent Form effect when at least two lanes
  have a valid lane feature and their values have non-zero population stddev.

Motor2 completeness is reported separately so the audit can also identify the
population shared with the already-frozen V4/V5 matched comparison.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

CONTRACT = "V51_RECENT_FORM_LAST5_TOP3_READINESS_V1"
START_DEFAULT = "2025-07-01"
END_DEFAULT = "2026-09-30"
EPS = 1e-12

SPLITS = (
    ("TRAIN_REFERENCE", date(2025, 7, 1), date(2025, 12, 31)),
    ("VALIDATION", date(2026, 1, 1), date(2026, 6, 30)),
    ("OOS", date(2026, 7, 1), date(2026, 9, 30)),
)


def split_name(d: date) -> str:
    for name, start, end in SPLITS:
        if start <= d <= end:
            return name
    return "OUTSIDE"


RACE_SQL = r"""
with per_entry as (
    select
        r.race_id,
        r.race_date,
        e.lane,
        e.motor_place2_rate,
        case
          when jsonb_typeof(e.recent_form)='array'
          then jsonb_array_length(e.recent_form)
          else 0
        end as history_len,
        case
          when jsonb_typeof(e.recent_form)='array'
               and jsonb_array_length(e.recent_form)>0
          then true else false
        end as recent_nonempty,
        h.history_items,
        h.bad_source_items,
        h.bad_date_items,
        h.same_day_items,
        h.future_items,
        h.bad_race_id_items,
        h.valid_finish_items,
        h.top3_items,
        case
          when jsonb_typeof(e.recent_form)='array'
               and jsonb_array_length(e.recent_form) between 1 and 5
               and h.bad_source_items=0
               and h.bad_date_items=0
               and h.same_day_items=0
               and h.future_items=0
               and h.bad_race_id_items=0
          then true else false
        end as provenance_valid,
        case
          when jsonb_typeof(e.recent_form)='array'
               and jsonb_array_length(e.recent_form) between 1 and 5
               and h.bad_source_items=0
               and h.bad_date_items=0
               and h.same_day_items=0
               and h.future_items=0
               and h.bad_race_id_items=0
               and h.valid_finish_items>=3
          then (h.top3_items::double precision / h.valid_finish_items::double precision)
          else null
        end as recent_top3_rate_5
    from v2_race_entries e
    join v2_races r on r.race_id=e.race_id
    left join lateral (
        select
            count(*)::int as history_items,
            count(*) filter (
                where coalesce(item->>'source','') <> 'official_k_file'
            )::int as bad_source_items,
            count(*) filter (
                where coalesce(item->>'race_date','') !~ '^\d{4}-\d{2}-\d{2}$'
            )::int as bad_date_items,
            count(*) filter (
                where coalesce(item->>'race_date','') ~ '^\d{4}-\d{2}-\d{2}$'
                  and (item->>'race_date') = r.race_date::text
            )::int as same_day_items,
            count(*) filter (
                where coalesce(item->>'race_date','') ~ '^\d{4}-\d{2}-\d{2}$'
                  and (item->>'race_date') > r.race_date::text
            )::int as future_items,
            count(*) filter (
                where coalesce(item->>'race_id','')=''
            )::int as bad_race_id_items,
            count(*) filter (
                where coalesce(item->>'finish_position','') ~ '^[1-6]$'
            )::int as valid_finish_items,
            count(*) filter (
                where coalesce(item->>'finish_position','') ~ '^[1-3]$'
            )::int as top3_items
        from jsonb_array_elements(
            case
              when jsonb_typeof(e.recent_form)='array'
              then e.recent_form
              else '[]'::jsonb
            end
        ) as j(item)
    ) h on true
    where r.race_date between %s and %s
),
per_race as (
    select
        race_id,
        race_date,
        count(*)::int as entry_rows,
        count(distinct lane)::int as distinct_lanes,
        count(*) filter (
            where lane between 1 and 6
        )::int as lane_1_6_rows,
        count(*) filter (
            where motor_place2_rate is not null
              and motor_place2_rate between 0 and 100
        )::int as motor2_valid_entries,
        count(*) filter (where recent_nonempty)::int as recent_nonempty_entries,
        count(*) filter (where provenance_valid)::int as provenance_valid_entries,
        count(*) filter (where recent_top3_rate_5 is not null)::int as feature_entries,
        count(*) filter (where history_len > 5)::int as history_gt5_entries,
        sum(coalesce(history_items,0))::int as history_items,
        sum(coalesce(bad_source_items,0))::int as bad_source_items,
        sum(coalesce(bad_date_items,0))::int as bad_date_items,
        sum(coalesce(same_day_items,0))::int as same_day_items,
        sum(coalesce(future_items,0))::int as future_items,
        sum(coalesce(bad_race_id_items,0))::int as bad_race_id_items,
        sum(coalesce(valid_finish_items,0))::int as valid_finish_items,
        stddev_pop(recent_top3_rate_5) filter (
            where recent_top3_rate_5 is not null
        ) as feature_stddev
    from per_entry
    group by race_id,race_date
)
select *
from per_race
order by race_date,race_id
"""


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counters = defaultdict(int)
    feature_lane_sum = 0
    for r in rows:
        exact6 = (
            int(r["entry_rows"]) == 6
            and int(r["distinct_lanes"]) == 6
            and int(r["lane_1_6_rows"]) == 6
        )
        motor6 = exact6 and int(r["motor2_valid_entries"]) == 6
        feature_entries = int(r["feature_entries"])
        std = r.get("feature_stddev")
        recent_evaluable = (
            exact6
            and feature_entries >= 2
            and std is not None
            and float(std) > EPS
        )
        shared_recent_evaluable = motor6 and recent_evaluable

        counters["races"] += 1
        counters["exact6_races"] += int(exact6)
        counters["motor2_complete_races"] += int(motor6)
        counters["recent_evaluable_races"] += int(recent_evaluable)
        counters["shared_recent_evaluable_races"] += int(shared_recent_evaluable)
        counters["recent_neutral_races"] += int(exact6 and not recent_evaluable)
        counters["recent_nonempty_entries"] += int(r["recent_nonempty_entries"])
        counters["provenance_valid_entries"] += int(r["provenance_valid_entries"])
        counters["feature_entries"] += feature_entries
        counters["history_gt5_entries"] += int(r["history_gt5_entries"])
        counters["history_items"] += int(r["history_items"])
        counters["bad_source_items"] += int(r["bad_source_items"])
        counters["bad_date_items"] += int(r["bad_date_items"])
        counters["same_day_items"] += int(r["same_day_items"])
        counters["future_items"] += int(r["future_items"])
        counters["bad_race_id_items"] += int(r["bad_race_id_items"])
        counters["valid_finish_items"] += int(r["valid_finish_items"])
        feature_lane_sum += feature_entries

    races = counters["races"]
    exact6 = counters["exact6_races"]
    motor6 = counters["motor2_complete_races"]
    out = dict(sorted(counters.items()))
    out["recent_evaluable_pct_of_exact6"] = (
        round(100.0 * counters["recent_evaluable_races"] / exact6, 4)
        if exact6 else None
    )
    out["shared_recent_evaluable_pct_of_motor2_complete"] = (
        round(100.0 * counters["shared_recent_evaluable_races"] / motor6, 4)
        if motor6 else None
    )
    out["avg_feature_lanes_per_race"] = (
        round(feature_lane_sum / races, 4) if races else None
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=START_DEFAULT)
    ap.add_argument("--end-date", default=END_DEFAULT)
    ap.add_argument("--output", default="v51-recent-form-readiness.json")
    args = ap.parse_args()

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V51_RF_READINESS_CONTRACT={CONTRACT}", flush=True)
    print("V51_RF_READINESS_RESULT_READ=0", flush=True)
    print("V51_RF_READINESS_ODDS_READ=0", flush=True)
    print("V51_RF_READINESS_PAYOUT_READ=0", flush=True)
    print("V51_RF_READINESS_DB_WRITE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute(RACE_SQL, (args.start_date, args.end_date))
            rows = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        d = row["race_date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        by_split[split_name(d)].append(row)
        by_month[d.strftime("%Y-%m")].append(row)

    overall = summarize(rows)
    split_report = {
        name: summarize(by_split.get(name, []))
        for name, _, _ in SPLITS
    }
    month_report = {
        month: summarize(month_rows)
        for month, month_rows in sorted(by_month.items())
    }

    leakage_clean = all(
        overall[k] == 0
        for k in (
            "history_gt5_entries",
            "bad_source_items",
            "bad_date_items",
            "same_day_items",
            "future_items",
            "bad_race_id_items",
        )
    )

    payload = {
        "contract": CONTRACT,
        "candidate_id": "V51_RECENT_FORM_LAST5_TOP3_V1",
        "period": [args.start_date, args.end_date],
        "source_required": "official_k_file",
        "max_history": 5,
        "minimum_valid_finishes_per_lane": 3,
        "race_feature_rule": "at_least_2_valid_lanes_and_nonzero_stddev",
        "same_day_history_allowed": False,
        "outcome_read": False,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
        "prospective_evidence": False,
        "provenance_leakage_clean": leakage_clean,
        "overall": overall,
        "by_split": split_report,
        "by_month": month_report,
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("V51_RF_READINESS_OVERALL=" + json.dumps(overall, sort_keys=True), flush=True)
    for name, report in split_report.items():
        print(
            "V51_RF_READINESS_SPLIT="
            + json.dumps({"split": name, **report}, sort_keys=True),
            flush=True,
        )
    print(f"V51_RF_READINESS_PROVENANCE_CLEAN={str(leakage_clean).lower()}", flush=True)
    print(
        "V51_RF_READINESS_RESULT="
        + ("PASS_PRE_OUTCOME_READY" if leakage_clean else "BLOCK_PROVENANCE"),
        flush=True,
    )


if __name__ == "__main__":
    main()
