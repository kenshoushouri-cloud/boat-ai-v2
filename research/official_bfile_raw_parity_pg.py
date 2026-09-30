# -*- coding: utf-8 -*-
"""Read-only live parity audit for raw official B-file byte offsets.

Downloads exactly one BOAT RACE official daily B archive, parses all entry
records with our isolated raw parser, then compares those pre-race fields with
existing official-racelist-backed Production entry rows by exact race_id.

No DB writes. No results/odds/payout reads. No Production behavior change.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import requests
from psycopg.rows import dict_row

from research.official_bfile_raw_parser import group_complete_races, parse_b_bytes


FIELDS = (
    "racer_number",
    "f_count",
    "l_count",
    "avg_st",
    "national_win_rate",
    "national_place2_rate",
    "local_win_rate",
    "local_place2_rate",
    "motor_no",
    "motor_place2_rate",
    "boat_no",
    "boat_place2_rate",
)


def official_b_url(target: date) -> str:
    return (
        "https://www1.mbrace.or.jp/od2/B/"
        f"{target:%Y%m}/b{target:%y%m%d}.lzh"
    )


def download_txt(target: date, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    archive = work / f"b{target:%y%m%d}.lzh"
    response = requests.get(
        official_b_url(target),
        headers={"User-Agent": "boat-ai-v2-historical-research/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    subprocess.run(
        ["7z", "x", "-y", f"-o{work}", str(archive)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    wanted = f"B{target:%y%m%d}.TXT".lower()
    matches = [p for p in work.rglob("*") if p.is_file() and p.name.lower() == wanted]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {wanted}; found {len(matches)}")
    return matches[0]


def norm(field: str, value: Any) -> Any:
    if value in (None, ""):
        return None
    if field in {"motor_no", "boat_no"}:
        try:
            return str(int(value))
        except Exception:
            return str(value).strip()
    if field in {"racer_number", "f_count", "l_count"}:
        try:
            return int(value)
        except Exception:
            return None
    try:
        return round(float(value), 2)
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2025-07-01")
    ap.add_argument("--work-dir", default=".bfile-raw-parity")
    args = ap.parse_args()
    target = date.fromisoformat(args.date)

    path = download_txt(target, Path(args.work_dir))
    raw_bytes = path.read_bytes()
    raw_lines = [x.rstrip(b"\r") for x in raw_bytes.splitlines() if x.strip()]
    sig = Counter()
    samples = []
    for raw in raw_lines:
        prefix = raw[:2].hex()
        sig[f"{prefix}:{len(raw)}"] += 1
        if len(samples) < 24:
            samples.append({
                "length": len(raw),
                "prefix_hex": raw[:12].hex(),
                "ascii_head": "".join(
                    chr(b) if 32 <= b <= 126 else "."
                    for b in raw[:24]
                ),
            })
    print(
        "OFFICIAL_BFILE_RAW_SIGNATURE="
        + json.dumps({
            "line_count": len(raw_lines),
            "top_signatures": sig.most_common(30),
            "samples": samples,
        }, ensure_ascii=False, sort_keys=True),
        flush=True,
    )
    parsed_rows = parse_b_bytes(raw_bytes, target)
    complete = group_complete_races(parsed_rows)
    candidate_rows = [
        row
        for race_id in sorted(complete)
        for row in complete[race_id]
    ]
    ids = sorted(complete)

    if not ids:
        print(
            "OFFICIAL_BFILE_RAW_PARITY_RESULT=FORMAT_DISCOVERY_REQUIRED",
            flush=True,
        )
        return

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    db_rows: dict[tuple[str, int], dict[str, Any]] = {}
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select race_id,lane,
                       racer_number,f_count,l_count,avg_st,
                       national_win_rate,national_place2_rate,
                       local_win_rate,local_place2_rate,
                       motor_no,motor_place2_rate,
                       boat_no,boat_place2_rate
                  from v2_race_entries
                 where race_id=any(%s)
                 order by race_id,lane
                """,
                (ids,),
            )
            for row in cur.fetchall():
                item = dict(row)
                db_rows[(str(item["race_id"]), int(item["lane"]))] = item
        conn.rollback()

    compared = Counter()
    exact = Counter()
    mismatches: dict[str, list[dict[str, Any]]] = {f: [] for f in FIELDS}
    rows_with_db = 0

    for parsed in candidate_rows:
        key = (parsed.race_id, parsed.lane)
        dbrow = db_rows.get(key)
        if dbrow is None:
            continue
        rows_with_db += 1
        pd = parsed.to_dict()
        for field in FIELDS:
            a = norm(field, pd.get(field))
            b = norm(field, dbrow.get(field))
            if a is None or b is None:
                continue
            compared[field] += 1
            if a == b:
                exact[field] += 1
            elif len(mismatches[field]) < 8:
                mismatches[field].append(
                    {
                        "race_id": parsed.race_id,
                        "lane": parsed.lane,
                        "b_file": a,
                        "db_official_racelist": b,
                    }
                )

    parity = {
        field: {
            "compared": compared[field],
            "exact": exact[field],
            "exact_pct": (
                round(100.0 * exact[field] / compared[field], 2)
                if compared[field]
                else None
            ),
            "mismatch_samples": mismatches[field],
        }
        for field in FIELDS
    }

    payload = {
        "contract": "OFFICIAL_BFILE_RAW_LAYOUT_PARITY_V1",
        "target_date": target.isoformat(),
        "source": "BOATRACE_OFFICIAL_B_DAILY_LZH",
        "parsed_entry_rows": len(parsed_rows),
        "complete_races": len(complete),
        "complete_race_entry_rows": len(candidate_rows),
        "rows_with_db_reference": rows_with_db,
        "distinct_venues": sorted({row.venue_code for row in candidate_rows}),
        "parity": parity,
        "db_read_only": True,
        "db_write": False,
        "result_odds_payout_read": False,
        "production_change": False,
        "purchase_action": False,
    }
    Path("official-bfile-raw-layout-parity.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OFFICIAL_BFILE_RAW_PARITY=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print("OFFICIAL_BFILE_RAW_PARITY_RESULT=PASS_DIAGNOSTIC_ONLY")


if __name__ == "__main__":
    main()
