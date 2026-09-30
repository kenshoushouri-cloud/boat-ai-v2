# -*- coding: utf-8 -*-
"""Historical fill-missing backfill from BOAT RACE official daily B files.

This bulk path complements the archived-racelist backfill:
- one official B archive per date instead of one HTTP request per race;
- fill missing values only on existing v2_race_entries rows;
- never overwrite existing non-null values;
- never insert missing race/entry rows;
- never read results, odds, or payouts.

The B table does not contain F/L, average ST, place3 rates, or origin. Those
fields remain on the archived-racelist/prior-only acquisition paths.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import lhafile
import psycopg
import requests
from psycopg.rows import dict_row

from research.official_bfile_raw_parser import group_complete_races, parse_b_bytes


JST = ZoneInfo("Asia/Tokyo")
WRITE_CONFIRM = "YES"
SOURCE_CONTRACT = "BOATRACE_OFFICIAL_DAILY_B_PREDEADLINE_BY_NATURE_V1"
TARGET_FIELDS = (
    "racer_name",
    "branch",
    "national_win_rate",
    "national_place2_rate",
    "local_win_rate",
    "local_place2_rate",
    "motor_no",
    "motor_place2_rate",
    "boat_no",
    "boat_place2_rate",
)
TEXT_FIELDS = {"racer_name", "branch", "motor_no", "boat_no"}


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def build_missing_patch(
    existing: Mapping[str, Any],
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        field: parsed[field]
        for field in TARGET_FIELDS
        if _is_missing(existing.get(field))
        and not _is_missing(parsed.get(field))
    }


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end date must be >= start date")
    days = (end - start).days + 1
    if days > 31 and os.getenv("ALLOW_LONG_HISTORICAL_RANGE") != "YES":
        raise ValueError("range >31 days requires ALLOW_LONG_HISTORICAL_RANGE=YES")
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def official_b_url(target: date) -> str:
    return (
        "https://www1.mbrace.or.jp/od2/B/"
        f"{target:%Y%m}/b{target:%y%m%d}.lzh"
    )


def fetch_b_txt(target: date) -> bytes:
    response = requests.get(
        official_b_url(target),
        headers={"User-Agent": "boat-ai-v2-historical-backfill/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    with tempfile.TemporaryDirectory(prefix="boat-bfile-") as tmp:
        archive = Path(tmp) / f"b{target:%y%m%d}.lzh"
        archive.write_bytes(response.content)
        lha = lhafile.Lhafile(str(archive))
        names = list(lha.namelist())
        wanted = f"B{target:%y%m%d}.TXT".upper()
        matches = [name for name in names if Path(name).name.upper() == wanted]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected exactly one {wanted} in archive; found {len(matches)}"
            )
        return lha.read(matches[0])


def _existing_rows(
    conn: psycopg.Connection,
    race_ids: list[str],
) -> dict[tuple[str, int], dict[str, Any]]:
    if not race_ids:
        return {}
    fields = ",".join(("race_id", "lane") + TARGET_FIELDS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            select {fields}
              from v2_race_entries
             where race_id=any(%s)
             order by race_id,lane
            """,
            (race_ids,),
        )
        return {
            (str(row["race_id"]), int(row["lane"])): dict(row)
            for row in cur.fetchall()
        }


def _update_missing(
    conn: psycopg.Connection,
    *,
    race_id: str,
    lane: int,
    patch: Mapping[str, Any],
) -> int:
    if not patch:
        return 0
    sets: list[str] = []
    params: list[Any] = []
    guards: list[str] = []
    for field, value in patch.items():
        if field in TEXT_FIELDS:
            sets.append(f"{field}=coalesce({field},%s::text)")
            params.append(str(value))
        else:
            sets.append(f"{field}=coalesce({field},%s)")
            params.append(value)
        guards.append(f"{field} is null")
    sets.append("updated_at=%s")
    params.append(datetime.now(JST).isoformat())
    params.extend([race_id, lane])
    with conn.cursor() as cur:
        cur.execute(
            f"""
            update v2_race_entries
               set {",".join(sets)}
             where race_id=%s
               and lane=%s
               and ({" or ".join(guards)})
            """,
            tuple(params),
        )
        return int(cur.rowcount or 0)


def process_day(
    conn: psycopg.Connection,
    target_date: str,
    *,
    write_enabled: bool,
) -> dict[str, Any]:
    target = date.fromisoformat(target_date)
    raw = fetch_b_txt(target)
    parsed = parse_b_bytes(raw, target)
    complete = group_complete_races(parsed)
    ids = sorted(complete)
    existing = _existing_rows(conn, ids)

    counts: Counter[str] = Counter()
    per_field: Counter[str] = Counter()
    counts["parsed_rows"] = len(parsed)
    counts["complete_races"] = len(complete)
    counts["existing_rows"] = len(existing)

    for race_id in ids:
        for row in complete[race_id]:
            key = (race_id, row.lane)
            old = existing.get(key)
            if old is None:
                counts["skipped_missing_existing_row"] += 1
                continue
            patch = build_missing_patch(old, row.to_dict())
            if not patch:
                counts["rows_no_patch"] += 1
                continue
            counts["rows_with_patch"] += 1
            counts["values_fillable"] += len(patch)
            for field in patch:
                per_field[field] += 1
            if write_enabled:
                counts["db_rows_updated"] += _update_missing(
                    conn,
                    race_id=race_id,
                    lane=row.lane,
                    patch=patch,
                )

    if write_enabled:
        conn.commit()
    else:
        conn.rollback()

    return {
        "target_date": target_date,
        "summary": dict(sorted(counts.items())),
        "fillable_by_field": dict(sorted(per_field.items())),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", default=os.getenv("HIST_START_DATE"))
    ap.add_argument("--end-date", default=os.getenv("HIST_END_DATE"))
    ap.add_argument(
        "--output",
        default=os.getenv(
            "HIST_BFILE_MANIFEST_OUTPUT",
            "historical-bfile-entry-backfill-manifest.json",
        ),
    )
    args = ap.parse_args()
    if not args.start_date or not args.end_date:
        raise SystemExit("start/end date required")
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    write_enabled = (
        os.getenv("CONFIRM_HISTORICAL_BFILE_DB_WRITE", "").strip().upper()
        == WRITE_CONFIRM
    )
    reports: list[dict[str, Any]] = []

    print(f"HIST_BFILE_SOURCE_CONTRACT={SOURCE_CONTRACT}", flush=True)
    print("HIST_BFILE_PREDEADLINE_BY_NATURE=1", flush=True)
    print("HIST_BFILE_WRITE_POLICY=fill_missing_only_no_overwrite_no_insert", flush=True)
    print("HIST_BFILE_RESULT_ODDS_PAYOUT_READ=0", flush=True)
    print("HIST_BFILE_LINE=0 BUY=0 PROD_MODEL_CHANGE=0", flush=True)
    print(f"HIST_BFILE_WRITE_ENABLED={int(write_enabled)}", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        for day in _date_range(args.start_date, args.end_date):
            report = process_day(conn, day, write_enabled=write_enabled)
            reports.append(report)
            print(
                "HIST_BFILE_DAY="
                f"date:{day} "
                f"parsed:{report['summary'].get('parsed_rows',0)} "
                f"complete_races:{report['summary'].get('complete_races',0)} "
                f"fillable:{report['summary'].get('values_fillable',0)} "
                f"updated:{report['summary'].get('db_rows_updated',0)}",
                flush=True,
            )

    totals: Counter[str] = Counter()
    fields: Counter[str] = Counter()
    for report in reports:
        totals.update(report["summary"])
        fields.update(report["fillable_by_field"])

    payload = {
        "contract": "HISTORICAL_OFFICIAL_BFILE_FILL_MISSING_V1",
        "source_contract": SOURCE_CONTRACT,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "historical_reconstruction": True,
        "prospective_evidence": False,
        "predeadline_by_nature": True,
        "fill_missing_only": True,
        "overwrite_existing_nonnull": False,
        "insert_missing_entry_rows": False,
        "result_odds_payout_read": False,
        "write_enabled": write_enabled,
        "totals": dict(sorted(totals.items())),
        "fillable_by_field": dict(sorted(fields.items())),
        "days": reports,
        "production_model_change": False,
        "purchase_action": False,
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("HIST_BFILE_TOTALS=" + json.dumps(payload["totals"], sort_keys=True), flush=True)
    print("HIST_BFILE_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
