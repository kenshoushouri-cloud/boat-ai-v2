# -*- coding: utf-8 -*-
"""Read-only 艇国 motor-history batch cross-check for historical targets.

Source role:
- supplemental validation only;
- BOAT RACE official remains the primary historical source.

For one target date this tool:
1. reads the distinct venue/motor pairs actually present in v2_race_entries;
2. fetches only known 艇国 motor-detail URLs;
3. enforces >=3 seconds between automated accesses;
4. summarizes only dated-history structure strictly before the cutoff date;
5. writes a local JSON artifact only.

It never writes PostgreSQL and never treats the page's present-day aggregate
rate as the historical target-day value.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.teikoku_motor_history_probe import (
    AccessLimiter,
    fetch_html,
    summarize_motor_page,
)

MAX_MOTORS = 24
DEFAULT_LIMIT = 12
MIN_ACCESS_INTERVAL_SEC = 3.1


def _motor_int(value: Any) -> int | None:
    m = re.search(r"\d{1,3}", str(value or ""))
    if not m:
        return None
    n = int(m.group(0))
    return n if 0 < n <= 999 else None


def _pid(value: Any) -> str | None:
    m = re.search(r"\d{1,2}", str(value or ""))
    if not m:
        return None
    n = int(m.group(0))
    return f"{n:02d}" if 1 <= n <= 24 else None


def select_target_motors(target_date: str, limit: int) -> list[dict[str, Any]]:
    if not 1 <= limit <= MAX_MOTORS:
        raise ValueError(f"limit must be 1..{MAX_MOTORS}")
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select distinct
                       coalesce(r.venue_id,r.venue_code)::text as venue_id,
                       e.motor_no::text as motor_no
                  from v2_race_entries e
                  join v2_races r on r.race_id=e.race_id
                 where r.race_date=%s
                   and e.motor_no is not null
                 order by 1,2
                """,
                (target_date,),
            )
            raw = [dict(x) for x in cur.fetchall()]
        conn.rollback()

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for row in raw:
        pid = _pid(row.get("venue_id"))
        motor = _motor_int(row.get("motor_no"))
        if pid is None or motor is None:
            continue
        key = (pid, motor)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "pid": pid,
                "motor_no": motor,
                "url": (
                    "https://boatrace-db.net/stadium/mdetail/"
                    f"pid/{pid}/mno/{motor}/"
                ),
            }
        )
        if len(out) >= limit:
            break
    return out


def run_batch(target_date: str, limit: int) -> dict[str, Any]:
    cutoff = date.fromisoformat(target_date)
    pairs = select_target_motors(target_date, limit)
    limiter = AccessLimiter(MIN_ACCESS_INTERVAL_SEC)
    rows: list[dict[str, Any]] = []

    for pair in pairs:
        row = dict(pair)
        try:
            html = fetch_html(pair["url"], limiter)
            summary = summarize_motor_page(html, cutoff=cutoff)
            row.update(
                {
                    "fetch_ok": True,
                    "prior_only_reconstruction_possible": bool(
                        summary.get("prior_only_reconstruction_possible")
                    ),
                    "prior_only_token_count": int(
                        summary.get("prior_only_token_count") or 0
                    ),
                    "prior_only_min_date": summary.get("prior_only_min_date"),
                    "prior_only_max_date": summary.get("prior_only_max_date"),
                    "target_or_future_token_count": int(
                        summary.get("target_or_future_token_count") or 0
                    ),
                    "aggregate_period_text": summary.get(
                        "aggregate_period_text"
                    ),
                    "last_data_update": summary.get("last_data_update"),
                }
            )
        except Exception as exc:
            row.update(
                {
                    "fetch_ok": False,
                    "error_type": type(exc).__name__,
                    "prior_only_reconstruction_possible": False,
                }
            )
        rows.append(row)

    passed = sum(
        1 for row in rows
        if row.get("fetch_ok")
        and row.get("prior_only_reconstruction_possible")
    )
    return {
        "contract": "TEIKOKU_MOTOR_BATCH_CROSSCHECK_V1",
        "source": "TEIKOKU_DATA_BANK",
        "source_role": "supplemental_crosscheck_only",
        "target_date": target_date,
        "cutoff_policy": "strictly_before_target_date",
        "access_interval_sec": MIN_ACCESS_INTERVAL_SEC,
        "known_url_only": True,
        "single_process": True,
        "static_assets_fetched": False,
        "program_result_racer_term_bulk_used": False,
        "present_aggregate_used_as_historical_value": False,
        "future_rows_used": False,
        "db_read_only": True,
        "db_write": False,
        "production_change": False,
        "purchase_action": False,
        "requested_limit": limit,
        "selected_motor_count": len(pairs),
        "prior_only_structure_pass_count": passed,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-date", required=True)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument(
        "--output",
        default="teikoku-motor-batch-crosscheck.json",
    )
    args = ap.parse_args()

    payload = run_batch(args.target_date, args.limit)
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(
        "TEIKOKU_MOTOR_BATCH_SUMMARY="
        + json.dumps(
            {
                "target_date": payload["target_date"],
                "selected_motor_count": payload["selected_motor_count"],
                "prior_only_structure_pass_count": payload[
                    "prior_only_structure_pass_count"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    print("TEIKOKU_MOTOR_BATCH_DB_WRITE=0 PROD_CHANGE=0 PURCHASE=0", flush=True)
    print("TEIKOKU_MOTOR_BATCH_RESULT=PASS_READ_ONLY_CROSSCHECK", flush=True)


if __name__ == "__main__":
    main()
