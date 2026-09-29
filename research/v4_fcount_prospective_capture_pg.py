# -*- coding: utf-8 -*-
"""Approved future-only F-count companion capture for formal V4.

This is an isolated evidence collector. It MUST NOT modify the formal V4
artifact or any Production decision.

Reads:
  select race_id,lane,f_count
  from v2_race_entries
  where race_id=any(%s)
  order by race_id,lane

Writes:
- local companion JSON artifact only;
- local SHA256 files only.

Never reads results, payout, odds, finish order, or outcome fields.
Never writes PostgreSQL.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from research.candidate_discovery_v4_capture_arbiter import (
    canonical_core_payload_sha256,
)
from research.v4_fcount_companion_adapter import (
    FUTURE_APPROVED_SELECT,
    build_companion_from_entry_rows,
)

JST = ZoneInfo("Asia/Tokyo")
FORMAL_PATH = Path(
    os.getenv(
        "V4_FCOUNT_FORMAL_ARTIFACT",
        "candidate-discovery-v4-prospective-freeze.json",
    )
)
FORMAL_CORE_SHA_PATH = Path(
    os.getenv(
        "V4_FCOUNT_FORMAL_CORE_SHA256",
        "candidate-discovery-v4-prospective-freeze.json.core.sha256",
    )
)
OUTPUT_PATH = Path(
    os.getenv(
        "V4_FCOUNT_COMPANION_OUTPUT",
        "candidate-discovery-v4-fcount-companion.json",
    )
)


def _formal_core_ids(formal: Mapping[str, Any]) -> list[str]:
    feed = formal.get("feed")
    if not isinstance(feed, list):
        raise ValueError("formal V4 feed required")
    rows = [
        row
        for row in feed
        if isinstance(row, Mapping)
        and row.get("daily_rank") is not None
        and row.get("legacy_carryover") is False
    ]
    if len(rows) != 6:
        raise ValueError("exact six formal V4 core races required")
    rows.sort(key=lambda row: int(row["daily_rank"]))
    if [int(row["daily_rank"]) for row in rows] != [1, 2, 3, 4, 5, 6]:
        raise ValueError("formal V4 daily ranks must be 1..6")
    ids = [str(row.get("race_id") or "") for row in rows]
    if any(not rid for rid in ids) or len(set(ids)) != 6:
        raise ValueError("six unique formal V4 race IDs required")
    return ids


def _read_sha256_file(path: Path) -> str:
    line = path.read_text(encoding="utf-8").strip()
    parts = line.split()
    if not parts or len(parts[0]) != 64:
        raise ValueError("invalid formal core SHA256 file")
    int(parts[0], 16)
    return parts[0].lower()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    formal = json.loads(FORMAL_PATH.read_text(encoding="utf-8"))
    expected_core_sha = _read_sha256_file(FORMAL_CORE_SHA_PATH)
    actual_core_sha = canonical_core_payload_sha256(formal)
    if actual_core_sha != expected_core_sha:
        raise RuntimeError("formal V4 canonical core SHA256 mismatch before F-count read")

    race_ids = _formal_core_ids(formal)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            captured_at_jst = datetime.now(JST)
            cur.execute(FUTURE_APPROVED_SELECT, (race_ids,))
            entry_rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()

    companion, canonical_sha = build_companion_from_entry_rows(
        formal,
        entry_rows,
        captured_at_jst=captured_at_jst,
    )

    if canonical_core_payload_sha256(formal) != expected_core_sha:
        raise RuntimeError("formal V4 canonical core changed during F-count capture")

    OUTPUT_PATH.write_text(
        json.dumps(
            companion,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    file_sha = _file_sha256(OUTPUT_PATH)
    Path(str(OUTPUT_PATH) + ".canonical.sha256").write_text(
        f"{canonical_sha}  {OUTPUT_PATH.name}\n",
        encoding="utf-8",
    )
    Path(str(OUTPUT_PATH) + ".sha256").write_text(
        f"{file_sha}  {OUTPUT_PATH.name}\n",
        encoding="utf-8",
    )

    print("V4_FCOUNT_CAPTURE_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    print(f"V4_FCOUNT_CAPTURE_TARGET_DATE={companion['target_date']}", flush=True)
    print(f"V4_FCOUNT_CAPTURE_ROWS={len(entry_rows)}", flush=True)
    print(f"V4_FCOUNT_CAPTURE_FORMAL_CORE_SHA256={expected_core_sha}", flush=True)
    print(f"V4_FCOUNT_CAPTURE_CANONICAL_SHA256={canonical_sha}", flush=True)
    print(f"V4_FCOUNT_CAPTURE_FILE_SHA256={file_sha}", flush=True)
    print("V4_FCOUNT_CAPTURE_RESULT=PASS_SEPARATE_COMPANION", flush=True)


if __name__ == "__main__":
    main()
