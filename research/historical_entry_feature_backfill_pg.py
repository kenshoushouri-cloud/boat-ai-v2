# -*- coding: utf-8 -*-
"""Fill missing historical pre-race entry features from BOAT RACE official racelist.

Contract:
- source: BOAT RACE official archived racelist pages;
- historical interpretation: values published for the race entry sheet are treated
  as the pre-deadline race-time values for historical research;
- fill NULL/blank fields only; never overwrite an existing non-null value;
- existing race-entry rows only; never create a new entry row;
- no result/odds/payout reads;
- no LINE / no purchase / no model change;
- DB writes require CONFIRM_HISTORICAL_ENTRY_DB_WRITE=YES.

This is historical reconstruction, not prospective evidence. Downstream reports
must keep that distinction explicit.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

import repair_month_all_pg as official

JST = official.JST

TARGET_FIELDS = (
    "f_count",
    "l_count",
    "avg_st",
    "national_win_rate",
    "national_place2_rate",
    "national_place3_rate",
    "local_win_rate",
    "local_place2_rate",
    "local_place3_rate",
    "motor_no",
    "motor_place2_rate",
    "motor_place3_rate",
    "boat_no",
    "boat_place2_rate",
    "boat_place3_rate",
)

SOURCE_FIELDS = (
    "racer_number",
    "racer_name",
    "racer_class",
    "racer_class_text",
    "branch",
    "origin",
) + TARGET_FIELDS

SOURCE_CONTRACT = "BOATRACE_OFFICIAL_RACELIST_ARCHIVE_PREDEADLINE_ASSUMED_V1"
WRITE_CONFIRM = "YES"
DEFAULT_SLEEP_SEC = 0.50


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def build_missing_patch(
    existing: Mapping[str, Any],
    parsed: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return only missing target fields that can be filled from parsed row."""
    patch: Dict[str, Any] = {}
    for field in TARGET_FIELDS:
        if _is_missing(existing.get(field)) and not _is_missing(parsed.get(field)):
            patch[field] = parsed.get(field)
    return patch


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end date must be >= start date")
    days = (end - start).days + 1
    if days > 31 and os.getenv("ALLOW_LONG_HISTORICAL_RANGE") != "YES":
        raise ValueError("range >31 days requires ALLOW_LONG_HISTORICAL_RANGE=YES")
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def _race_rows(conn: psycopg.Connection, target_date: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date=%s
             order by coalesce(venue_id,venue_code),race_no
            """,
            (target_date,),
        )
        return [dict(row) for row in cur.fetchall()]


def _entry_rows(
    conn: psycopg.Connection,
    race_ids: Iterable[str],
) -> dict[str, dict[int, dict[str, Any]]]:
    ids = list(race_ids)
    out: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    if not ids:
        return out

    fields = ",".join(("race_id", "lane") + SOURCE_FIELDS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {fields}
              from v2_race_entries
             where race_id=any(%s)
             order by race_id,lane
            """,
            (ids,),
        )
        for row in cur.fetchall():
            item = dict(row)
            out[str(item["race_id"])][int(item["lane"])] = item
    return out


def _missing_field_count(rows_by_lane: Mapping[int, Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in rows_by_lane.values()
        for field in TARGET_FIELDS
        if _is_missing(row.get(field))
    )


def _update_missing_fields(
    conn: psycopg.Connection,
    *,
    race_id: str,
    lane: int,
    patch: Mapping[str, Any],
) -> int:
    if not patch:
        return 0

    sets = []
    params: list[Any] = []
    guards = []
    for field, value in patch.items():
        sets.append(f"{field}=coalesce({field},%s)")
        params.append(value)
        guards.append(f"{field} is null")
    sets.append("updated_at=%s")
    params.append(datetime.now(JST).isoformat())
    params.extend([race_id, lane])

    sql = f"""
        update v2_race_entries
           set {",".join(sets)}
         where race_id=%s
           and lane=%s
           and ({" or ".join(guards)})
    """
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        return int(cur.rowcount or 0)


def process_day(
    conn: psycopg.Connection,
    target_date: str,
    *,
    write_enabled: bool,
    sleep_sec: float,
) -> dict[str, Any]:
    races = _race_rows(conn, target_date)
    existing = _entry_rows(conn, [str(r["race_id"]) for r in races])

    summary: Counter[str] = Counter()
    per_field: Counter[str] = Counter()
    errors: list[dict[str, str]] = []

    summary["db_races"] = len(races)
    summary["existing_entry_rows"] = sum(len(x) for x in existing.values())
    summary["missing_values_before"] = sum(
        _missing_field_count(x) for x in existing.values()
    )

    for race in races:
        race_id = str(race["race_id"])
        rows_by_lane = existing.get(race_id, {})
        if len(rows_by_lane) != 6:
            summary["skipped_non6_existing_entries"] += 1
            continue
        if _missing_field_count(rows_by_lane) == 0:
            summary["skipped_complete_races"] += 1
            continue

        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        race_no = int(race.get("race_no") or 0)
        url = official._official_url("racelist", target_date, venue, race_no)

        html = official._fetch(url)
        summary["http_requests"] += 1
        if not html:
            summary["fetch_failed"] += 1
            errors.append({"race_id": race_id, "reason": "fetch_failed"})
            time.sleep(sleep_sec)
            continue

        parsed_rows = official.parse_entries(html, race_id)
        parsed = {int(row["lane"]): row for row in parsed_rows}
        if set(parsed) != {1, 2, 3, 4, 5, 6}:
            summary["parse_non6"] += 1
            errors.append(
                {
                    "race_id": race_id,
                    "reason": f"parsed_lanes={sorted(parsed)}",
                }
            )
            time.sleep(sleep_sec)
            continue

        summary["parsed_races"] += 1
        for lane in range(1, 7):
            patch = build_missing_patch(rows_by_lane[lane], parsed[lane])
            if not patch:
                continue
            summary["rows_with_patch"] += 1
            summary["values_fillable"] += len(patch)
            for field in patch:
                per_field[field] += 1
            if write_enabled:
                summary["db_rows_updated"] += _update_missing_fields(
                    conn,
                    race_id=race_id,
                    lane=lane,
                    patch=patch,
                )

        time.sleep(sleep_sec)

    if write_enabled:
        conn.commit()
    else:
        conn.rollback()

    return {
        "target_date": target_date,
        "source_contract": SOURCE_CONTRACT,
        "write_enabled": write_enabled,
        "summary": dict(sorted(summary.items())),
        "fillable_by_field": dict(sorted(per_field.items())),
        "errors": errors[:50],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_START_DATE"))
    ap.add_argument("--end-date", default=os.getenv("HIST_END_DATE"))
    ap.add_argument(
        "--sleep-sec",
        type=float,
        default=float(os.getenv("HIST_OFFICIAL_SLEEP_SEC", str(DEFAULT_SLEEP_SEC))),
    )
    ap.add_argument(
        "--output",
        default=os.getenv("HIST_MANIFEST_OUTPUT", "historical-entry-backfill-manifest.json"),
    )
    args = ap.parse_args()

    if not args.start_date or not args.end_date:
        raise SystemExit("start/end date required")
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_ENTRY_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )
    dates = _date_range(args.start_date, args.end_date)

    print(f"HIST_ENTRY_SOURCE_CONTRACT={SOURCE_CONTRACT}", flush=True)
    print(
        "HIST_ENTRY_TIMING_POLICY=historical_archived_racelist_values_treated_as_predeadline",
        flush=True,
    )
    print(
        "HIST_ENTRY_WRITE_POLICY=fill_missing_only_no_overwrite_no_insert",
        flush=True,
    )
    print("HIST_ENTRY_RESULT_ODDS_PAYOUT_READ=0", flush=True)
    print("HIST_ENTRY_LINE=0 BUY=0 PROD_MODEL_CHANGE=0", flush=True)
    print(f"HIST_ENTRY_WRITE_ENABLED={int(write_enabled)}", flush=True)

    reports: list[dict[str, Any]] = []
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        for target_date in dates:
            report = process_day(
                conn,
                target_date,
                write_enabled=write_enabled,
                sleep_sec=max(0.0, args.sleep_sec),
            )
            reports.append(report)
            s = report["summary"]
            print(
                "HIST_ENTRY_DAY="
                f"date:{target_date} "
                f"races:{s.get('db_races',0)} "
                f"missing_before:{s.get('missing_values_before',0)} "
                f"parsed:{s.get('parsed_races',0)} "
                f"fillable:{s.get('values_fillable',0)} "
                f"rows_updated:{s.get('db_rows_updated',0)} "
                f"fetch_failed:{s.get('fetch_failed',0)} "
                f"parse_non6:{s.get('parse_non6',0)}",
                flush=True,
            )

    totals: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    for report in reports:
        totals.update(report["summary"])
        fields.update(report["fillable_by_field"])

    payload = {
        "contract": "HISTORICAL_ENTRY_PREDEADLINE_BACKFILL_V1",
        "source_contract": SOURCE_CONTRACT,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "predeadline_interpretation": (
            "archived official racelist values are treated as the values "
            "published for the race before deadline"
        ),
        "fill_missing_only": True,
        "overwrite_existing_nonnull": False,
        "insert_missing_entry_rows": False,
        "result_odds_payout_read": False,
        "write_enabled": write_enabled,
        "totals": dict(sorted(totals.items())),
        "fillable_by_field": dict(sorted(fields.items())),
        "days": reports,
        "purchase_action": False,
        "production_model_change": False,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print("HIST_ENTRY_TOTALS=" + json.dumps(payload["totals"], sort_keys=True), flush=True)
    print(
        "HIST_ENTRY_FILLABLE_BY_FIELD="
        + json.dumps(payload["fillable_by_field"], sort_keys=True),
        flush=True,
    )
    print("HIST_ENTRY_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
