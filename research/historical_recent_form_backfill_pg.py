# -*- coding: utf-8 -*-
"""Leakage-safe historical recent_form reconstruction from prior-day official K results.

Contract
--------
- target rows: existing v2_race_entries only;
- source history: v2_result_entries rows whose source is official_k_file;
- chronology: when a target date is constructed, history contains only races from
  strictly earlier calendar dates;
- same-day earlier races are intentionally excluded;
- fill empty recent_form only; never overwrite non-empty values;
- no v2_results / odds / payout reads;
- no selector/model/LINE/stake/purchase change;
- writes require CONFIRM_HISTORICAL_RECENT_FORM_DB_WRITE=YES.

This is historical reconstruction, not prospective evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict, deque
from datetime import date, timedelta
from typing import Any, Deque, Dict, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


SOURCE_CONTRACT = "BOATRACE_OFFICIAL_K_PRIOR_DAY_RECENT_FORM_V1"
WRITE_CONFIRM = "YES"
MAX_HISTORY = 5

HistoryMap = Dict[int, Deque[dict[str, Any]]]


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end date must be >= start date")
    if (end - start).days + 1 > 500:
        raise ValueError("maximum range is 500 days")
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _history_item(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "race_date": str(row.get("race_date") or ""),
        "race_id": str(row.get("race_id") or ""),
        "venue_id": str(row.get("venue_id") or row.get("venue_code") or "").zfill(2),
        "race_no": int(row.get("race_no") or 0),
        "lane": int(row.get("lane") or 0),
        "start_course": row.get("start_course"),
        "start_timing": row.get("start_timing"),
        "finish_position": row.get("finish_position"),
        "finish_status": row.get("finish_status"),
        "motor_no": row.get("motor_no"),
        "boat_no": row.get("boat_no"),
        "source": "official_k_file",
    }


def append_result_rows(
    histories: HistoryMap,
    rows: Iterable[Mapping[str, Any]],
    *,
    max_history: int = MAX_HISTORY,
) -> None:
    for row in rows:
        racer = int(row.get("racer_number") or 0)
        if racer <= 0:
            continue
        if racer not in histories:
            histories[racer] = deque(maxlen=max_history)
        histories[racer].append(_history_item(row))


def recent_form_for(
    histories: Mapping[int, Deque[dict[str, Any]]],
    racer_number: int,
) -> list[dict[str, Any]]:
    """Return newest-first prior history."""
    history = histories.get(int(racer_number))
    if not history:
        return []
    return [dict(x) for x in reversed(history)]


def build_target_patches(
    target_rows: Iterable[Mapping[str, Any]],
    histories: Mapping[int, Deque[dict[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in target_rows:
        racer = int(row.get("racer_number") or 0)
        if racer <= 0:
            continue
        form = recent_form_for(histories, racer)
        if not form:
            continue
        out.append(
            {
                "race_id": str(row["race_id"]),
                "lane": int(row["lane"]),
                "racer_number": racer,
                "recent_form": form,
            }
        )
    return out


def _load_prior_history(
    conn: psycopg.Connection,
    start_date: str,
) -> HistoryMap:
    histories: HistoryMap = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            with ranked as (
                select re.race_id,
                       r.race_date,
                       coalesce(r.venue_id,r.venue_code) as venue_id,
                       r.race_no,
                       r.deadline_at,
                       re.lane,
                       re.racer_number,
                       re.start_course,
                       re.start_timing,
                       re.finish_position,
                       re.finish_status,
                       re.motor_no,
                       re.boat_no,
                       row_number() over (
                           partition by re.racer_number
                           order by r.race_date desc,
                                    r.deadline_at desc nulls last,
                                    r.race_no desc,
                                    re.lane desc
                       ) as rn
                  from v2_result_entries re
                  join v2_races r on r.race_id=re.race_id
                 where r.race_date < %s
                   and re.source='official_k_file'
                   and re.racer_number is not null
            )
            select race_id,race_date,venue_id,race_no,lane,racer_number,
                   start_course,start_timing,finish_position,finish_status,
                   motor_no,boat_no
              from ranked
             where rn <= %s
             order by racer_number asc,
                      race_date asc,
                      deadline_at asc nulls last,
                      race_no asc,
                      lane asc
            """,
            (start_date, MAX_HISTORY),
        )
        append_result_rows(histories, cur.fetchall())
    return histories


def _target_rows(
    conn: psycopg.Connection,
    target_date: str,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select e.race_id,e.lane,e.racer_number
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date=%s
               and e.racer_number is not null
               and (
                    e.recent_form is null
                    or e.recent_form='[]'::jsonb
                    or e.recent_form='{}'::jsonb
                    or e.recent_form='null'::jsonb
               )
             order by e.race_id,e.lane
            """,
            (target_date,),
        )
        return [dict(x) for x in cur.fetchall()]


def _official_results_for_day(
    conn: psycopg.Connection,
    target_date: str,
) -> list[dict[str, Any]]:
    """Read target-day results only AFTER target features have been built.

    These rows become eligible history for the next calendar day, never for the
    current target date.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            select re.race_id,
                   r.race_date,
                   coalesce(r.venue_id,r.venue_code) as venue_id,
                   r.race_no,
                   re.lane,
                   re.racer_number,
                   re.start_course,
                   re.start_timing,
                   re.finish_position,
                   re.finish_status,
                   re.motor_no,
                   re.boat_no
              from v2_result_entries re
              join v2_races r on r.race_id=re.race_id
             where r.race_date=%s
               and re.source='official_k_file'
               and re.racer_number is not null
             order by r.deadline_at asc nulls last,
                      r.race_no asc,
                      re.lane asc
            """,
            (target_date,),
        )
        return [dict(x) for x in cur.fetchall()]


def _write_patches(
    conn: psycopg.Connection,
    patches: Iterable[Mapping[str, Any]],
) -> int:
    updated = 0
    with conn.cursor() as cur:
        for patch in patches:
            cur.execute(
                """
                update v2_race_entries
                   set recent_form=%s,
                       updated_at=now()
                 where race_id=%s
                   and lane=%s
                   and (
                        recent_form is null
                        or recent_form='[]'::jsonb
                        or recent_form='{}'::jsonb
                        or recent_form='null'::jsonb
                   )
                """,
                (
                    Jsonb(patch["recent_form"]),
                    patch["race_id"],
                    patch["lane"],
                ),
            )
            updated += int(cur.rowcount or 0)
    return updated


def process_range(
    conn: psycopg.Connection,
    start_date: str,
    end_date: str,
    *,
    write_enabled: bool,
) -> dict[str, Any]:
    histories = _load_prior_history(conn, start_date)
    days = []
    totals: Counter[str] = Counter()

    for target_date in _date_range(start_date, end_date):
        target_rows = _target_rows(conn, target_date)
        patches = build_target_patches(target_rows, histories)

        summary = Counter()
        summary["target_empty_rows"] = len(target_rows)
        summary["fillable_rows"] = len(patches)
        summary["history_racers_before_day"] = len(histories)

        if write_enabled:
            summary["db_rows_updated"] = _write_patches(conn, patches)
            conn.commit()
        else:
            conn.rollback()

        # Critical chronology boundary:
        # current-day K results are loaded only AFTER target patches were built.
        day_results = _official_results_for_day(conn, target_date)
        summary["official_k_rows_added_after_build"] = len(day_results)
        append_result_rows(histories, day_results)

        day_payload = {
            "target_date": target_date,
            "summary": dict(sorted(summary.items())),
        }
        days.append(day_payload)
        totals.update(summary)
        print(
            "HIST_RECENT_FORM_DAY="
            f"date:{target_date} "
            f"empty:{summary['target_empty_rows']} "
            f"fillable:{summary['fillable_rows']} "
            f"updated:{summary.get('db_rows_updated',0)} "
            f"k_after_build:{summary['official_k_rows_added_after_build']}",
            flush=True,
        )

    return {
        "contract": "HISTORICAL_RECENT_FORM_PRIOR_DAY_V1",
        "source_contract": SOURCE_CONTRACT,
        "start_date": start_date,
        "end_date": end_date,
        "max_history": MAX_HISTORY,
        "strictly_prior_calendar_day": True,
        "same_day_prior_race_used": False,
        "target_day_outcome_used": False,
        "future_outcome_used": False,
        "fill_missing_only": True,
        "overwrite_existing_nonempty": False,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "write_enabled": write_enabled,
        "totals": dict(sorted(totals.items())),
        "days": days,
        "production_model_change": False,
        "line": False,
        "buy": False,
        "purchase_action": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_START_DATE"))
    ap.add_argument("--end-date", default=os.getenv("HIST_END_DATE"))
    ap.add_argument(
        "--output",
        default=os.getenv(
            "HIST_RECENT_FORM_OUTPUT",
            "historical-recent-form-manifest.json",
        ),
    )
    args = ap.parse_args()
    if not args.start_date or not args.end_date:
        raise SystemExit("start/end date required")

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_RECENT_FORM_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )

    print(f"HIST_RECENT_FORM_SOURCE_CONTRACT={SOURCE_CONTRACT}", flush=True)
    print(
        "HIST_RECENT_FORM_TIMING_POLICY=strict_prior_calendar_day_only",
        flush=True,
    )
    print("HIST_RECENT_FORM_SAME_DAY_RESULT_USED=0", flush=True)
    print("HIST_RECENT_FORM_FUTURE_RESULT_USED=0", flush=True)
    print("HIST_RECENT_FORM_ODDS_PAYOUT_READ=0", flush=True)
    print("HIST_RECENT_FORM_FILL_MISSING_ONLY=1", flush=True)
    print(f"HIST_RECENT_FORM_WRITE_ENABLED={int(write_enabled)}", flush=True)
    print("HIST_RECENT_FORM_LINE=0 BUY=0 PROD_MODEL_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        if not write_enabled:
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
        report = process_range(
            conn,
            args.start_date,
            args.end_date,
            write_enabled=write_enabled,
        )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        f.write("\n")

    print(
        "HIST_RECENT_FORM_TOTALS="
        + json.dumps(report["totals"], sort_keys=True),
        flush=True,
    )
    print("HIST_RECENT_FORM_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
