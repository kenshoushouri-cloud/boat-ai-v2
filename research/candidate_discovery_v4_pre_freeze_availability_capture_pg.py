# -*- coding: utf-8 -*-
"""Read-only Production shadow capture for V4 official availability raw.

This adapter is intentionally collection-only. It reads the same-day scheduled
race universe from PostgreSQL under an explicit read-only transaction, derives
the capture request from that universe, and preserves BOAT RACE official raw
availability pages before the earliest scheduled race deadline.

It does not evaluate candidate eligibility, does not read outcomes/payouts,
does not write PostgreSQL, does not send LINE, and does not authorize purchase.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.candidate_discovery_v4_pre_freeze_availability_capture import (
    build_capture_request_from_universe,
    capture_to_directory,
)

JST = timezone(timedelta(hours=9))
TARGET_DATE = date.fromisoformat(
    os.getenv("CANDIDATE_V4_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
)
OUTPUT_DIR = Path(
    os.getenv(
        "CANDIDATE_V4_AVAILABILITY_OUTPUT_DIR",
        "candidate-discovery-v4-availability-raw",
    )
).resolve()
REQUEST_OUTPUT = Path(
    os.getenv(
        "CANDIDATE_V4_AVAILABILITY_REQUEST_OUTPUT",
        "candidate-discovery-v4-availability-capture-request.json",
    )
).resolve()


def _aware_jst(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError("scheduled race deadline must be a datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def _load_race_universe(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date=%s
             order by venue_id,race_no,race_id
            """,
            (TARGET_DATE,),
        )
        rows = [dict(row) for row in cur.fetchall()]

    if not rows:
        raise RuntimeError("same-day scheduled race universe is empty")

    universe: list[dict[str, Any]] = []
    for row in rows:
        race_id = str(row.get("race_id") or "")
        venue_id = str(
            row.get("venue_id") or row.get("venue_code") or ""
        ).zfill(2)
        race_no = row.get("race_no")
        deadline = _aware_jst(row.get("deadline_at"))
        universe.append(
            {
                "race_id": race_id,
                "venue_id": venue_id,
                "race_no": int(race_no),
                "deadline_at": deadline.isoformat(),
            }
        )
    return universe


def main() -> int:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    now = datetime.now(JST)
    if now.date() != TARGET_DATE:
        raise RuntimeError(
            f"capture target must equal current JST date: "
            f"target={TARGET_DATE} now={now.date()}"
        )

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        universe = _load_race_universe(conn)
        conn.rollback()

    request = build_capture_request_from_universe(
        universe,
        target_date=TARGET_DATE.isoformat(),
    )
    REQUEST_OUTPUT.write_text(
        json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "CANDIDATE_V4_AVAILABILITY_CAPTURE_REQUEST="
        + json.dumps(
            {
                "target_date": request["target_date"],
                "scheduled_race_count": request["scheduled_race_count"],
                "venue_count": len(request["venue_ids"]),
                "hard_stop_at_jst": request["hard_stop_at_jst"],
                "race_universe_sha256": request["race_universe_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print(
        "CANDIDATE_V4_AVAILABILITY_CAPTURE_RESULT_READ=0 "
        "PAYOUT_READ=0 DB_WRITE=0 LINE=0 BUY=0 PROD_DECISION_CHANGE=0",
        flush=True,
    )

    manifest = capture_to_directory(request, OUTPUT_DIR)
    print(
        "CANDIDATE_V4_AVAILABILITY_CAPTURE_MANIFEST="
        + json.dumps(
            {
                "source_count": len(manifest["sources"]),
                "capture_started_at_jst": manifest["capture_started_at_jst"],
                "capture_completed_at_jst": manifest[
                    "capture_completed_at_jst"
                ],
                "all_sources_pre_hard_stop": manifest[
                    "all_sources_pre_hard_stop"
                ],
                "purchase_action": manifest["purchase_action"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print("CANDIDATE_V4_AVAILABILITY_CAPTURE_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_V4_AVAILABILITY_CAPTURE_RESULT=PASS_PRE_FREEZE_RAW_CAPTURE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
