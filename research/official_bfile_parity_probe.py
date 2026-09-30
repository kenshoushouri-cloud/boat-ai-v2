# -*- coding: utf-8 -*-
"""Read-only parity probe for BOAT RACE official daily B-file schedule data.

This is intentionally a probe, not an importer.
It downloads one official daily schedule archive, parses it with the isolated
boatrace-lzh research dependency, and compares row counts against Production DB
in a READ ONLY transaction.

No result K file, odds, payout, LINE, stake, or DB write.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _field_names(x: Any) -> list[str]:
    if x is None:
        return []
    if dataclasses.is_dataclass(x):
        return sorted(f.name for f in dataclasses.fields(x))
    if hasattr(x, "__dict__"):
        return sorted(k for k in vars(x) if not k.startswith("_"))
    return []


def _value(x: Any, name: str) -> Any:
    if isinstance(x, dict):
        return x.get(name)
    return getattr(x, name, None)


def _race_id(target: date, race: Any) -> str:
    venue = str(_value(race, "venue_code") or "").zfill(2)
    race_no = int(_value(race, "race_number") or 0)
    if len(venue) != 2 or not venue.isdigit() or not (1 <= race_no <= 12):
        raise ValueError(
            "B-file race identity fields unavailable: "
            f"fields={_field_names(race)} venue={venue!r} race_no={race_no!r}"
        )
    return f"{target:%Y%m%d}_{venue}_{race_no:02d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2025-07-01")
    ap.add_argument("--cache-dir", default=".bfile-probe-cache")
    args = ap.parse_args()
    target = date.fromisoformat(args.date)

    from boatrace_lzh import LzhDownloader, ScheduleParser

    dl = LzhDownloader(cache_dir=args.cache_dir, max_workers=1)
    files = dl.download(target, "schedule")
    if not files:
        raise RuntimeError(f"official B file unavailable: {target}")

    parsed = ScheduleParser().parse(files)
    parsed_races = list(getattr(parsed, "races", []) or [])
    parsed_racers = list(getattr(parsed, "racers", []) or [])
    parsed_entries = list(getattr(parsed, "entries", []) or [])

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    parsed_race_ids = [_race_id(target, race) for race in parsed_races]
    if len(parsed_race_ids) != len(set(parsed_race_ids)):
        raise RuntimeError("duplicate B-file race identities")

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            # Probe only exact B-file race IDs. This avoids date/range scans on
            # large Production tables while historical backfills are writing.
            cur.execute(
                """
                select count(*)::int n
                  from v2_races
                 where race_id=any(%s)
                """,
                (parsed_race_ids,),
            )
            db_races = int(cur.fetchone()["n"])
            cur.execute(
                """
                select count(*)::int n
                  from v2_race_entries
                 where race_id=any(%s)
                """,
                (parsed_race_ids,),
            )
            db_entries = int(cur.fetchone()["n"])
        conn.rollback()

    payload = {
        "contract": "OFFICIAL_BFILE_PARITY_PROBE_V1",
        "target_date": target.isoformat(),
        "source": "BOATRACE_OFFICIAL_B_DAILY_LZH",
        "result_file_read": False,
        "odds_read": False,
        "payout_read": False,
        "db_write": False,
        "parsed": {
            "races": len(parsed_races),
            "racers": len(parsed_racers),
            "entries": len(parsed_entries),
            "race_fields": _field_names(parsed_races[0]) if parsed_races else [],
            "racer_fields": _field_names(parsed_racers[0]) if parsed_racers else [],
            "entry_fields": _field_names(parsed_entries[0]) if parsed_entries else [],
        },
        "database": {
            "races": db_races,
            "entries": db_entries,
        },
        "race_count_match": len(parsed_races) == db_races,
        "entry_count_match_if_exposed": (
            len(parsed_entries) == db_entries if parsed_entries else None
        ),
        "production_change": False,
        "purchase_action": False,
    }
    Path("official-bfile-parity-probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OFFICIAL_BFILE_PARITY=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not payload["race_count_match"]:
        raise RuntimeError("B-file race count does not match DB; do not promote importer")
    print("OFFICIAL_BFILE_PARITY_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
