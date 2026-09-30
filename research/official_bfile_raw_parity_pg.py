# -*- coding: utf-8 -*-
"""Official-to-official parity audit for raw daily B-file byte layout.

Downloads one BOAT RACE official daily B archive, parses it with the isolated
raw parser, and compares selected races against BOAT RACE official archived
racelist pages for the same target date.

No PostgreSQL access. No results, odds, or payout data.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import requests

import repair_month_all_pg as official
from research.official_bfile_raw_parser import group_complete_races, parse_b_bytes


FIELDS = (
    "racer_number",
    "racer_name",
    "branch",
    "racer_class",
    "national_win_rate",
    "national_place2_rate",
    "local_win_rate",
    "local_place2_rate",
    "motor_no",
    "motor_place2_rate",
    "boat_no",
    "boat_place2_rate",
)

SAMPLE_RACES = (
    ("24", 1),
    ("24", 6),
    ("24", 12),
    ("05", 1),
    ("20", 6),
    ("23", 12),
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
    if field in {"racer_name", "branch"}:
        return "".join(str(value).split())
    if field in {"motor_no", "boat_no"}:
        try:
            return str(int(value))
        except Exception:
            return str(value).strip()
    if field in {"racer_number", "racer_class"}:
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
    target_iso = target.isoformat()

    path = download_txt(target, Path(args.work_dir))
    parsed_rows = parse_b_bytes(path.read_bytes(), target)
    complete = group_complete_races(parsed_rows)
    if not complete:
        raise RuntimeError("raw B parser produced no complete races")

    compared = Counter()
    exact = Counter()
    b_nonnull = Counter()
    mismatch_samples: dict[str, list[dict[str, Any]]] = {field: [] for field in FIELDS}
    sampled_races = 0
    sampled_rows = 0

    for venue, race_no in SAMPLE_RACES:
        race_id = f"{target:%Y%m%d}_{venue}_{race_no:02d}"
        brows = complete.get(race_id)
        if brows is None:
            # A venue may not be racing on the target day.
            continue

        url = official._official_url("racelist", target_iso, venue, race_no)
        html = official._fetch(url)
        if not html:
            raise RuntimeError(f"official racelist unavailable: {race_id}")
        rrows = official.parse_entries(html, race_id)
        rmap = {int(row["lane"]): row for row in rrows}
        if set(rmap) != {1, 2, 3, 4, 5, 6}:
            raise RuntimeError(f"official racelist parse non6: {race_id}")

        sampled_races += 1
        sampled_rows += 6
        for b in brows:
            arow = b.to_dict()
            rrow = rmap[b.lane]
            for field in FIELDS:
                a = norm(field, arow.get(field))
                if a is not None:
                    b_nonnull[field] += 1
                c = norm(field, rrow.get(field))
                if a is None or c is None:
                    continue
                compared[field] += 1
                if a == c:
                    exact[field] += 1
                elif len(mismatch_samples[field]) < 8:
                    mismatch_samples[field].append(
                        {
                            "race_id": race_id,
                            "lane": b.lane,
                            "b_file": a,
                            "racelist": c,
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
            "mismatch_samples": mismatch_samples[field],
        }
        for field in FIELDS
    }

    payload = {
        "contract": "OFFICIAL_BFILE_RAW_OFFICIAL_PARITY_V2",
        "target_date": target_iso,
        "source_a": "BOATRACE_OFFICIAL_B_DAILY_LZH",
        "source_b": "BOATRACE_OFFICIAL_ARCHIVED_RACELIST",
        "parsed_entry_rows": len(parsed_rows),
        "complete_races": len(complete),
        "distinct_venues": sorted(
            {row.venue_code for rows in complete.values() for row in rows}
        ),
        "sampled_races": sampled_races,
        "sampled_rows": sampled_rows,
        "parity": parity,
        "b_nonnull_in_sample": dict(sorted(b_nonnull.items())),
        "db_read": False,
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

    if len(complete) < 100 or sampled_races < 3:
        raise RuntimeError("insufficient B-file coverage/parity sample")

    required_exact = (
        "racer_number",
        "racer_class",
        "national_win_rate",
        "national_place2_rate",
        "motor_no",
        "motor_place2_rate",
        "boat_no",
        "boat_place2_rate",
    )
    bad = [
        field
        for field in required_exact
        if compared[field] == 0 or exact[field] != compared[field]
    ]
    if bad:
        raise RuntimeError(f"B-file exact field parity failed: {bad}")

    required_b_present = (
        "racer_name",
        "branch",
        "local_win_rate",
        "local_place2_rate",
    )
    missing = [
        field for field in required_b_present
        if b_nonnull[field] != sampled_rows
    ]
    if missing:
        raise RuntimeError(f"B-file structural fields incomplete: {missing}")

    print(
        "OFFICIAL_BFILE_LOCAL_RATE_POLICY="
        "B_TARGET_DAY_ARCHIVE_PREFERRED_FOR_HISTORICAL_PREDEADLINE",
        flush=True,
    )
    print("OFFICIAL_BFILE_RAW_PARITY_RESULT=PASS_VALIDATED_BULK_FIELDS")


if __name__ == "__main__":
    main()
