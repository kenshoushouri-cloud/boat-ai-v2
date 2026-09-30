# -*- coding: utf-8 -*-
"""Read-only structural probe for BOAT RACE official daily B-file data.

Purpose:
- verify the raw daily B archive structure before building a bulk importer;
- detect whether multiple venue sections exist in the extracted official text;
- compare raw structure with the third-party parser output.

No K/result file, odds, payout, DB read/write, LINE, stake, or purchase.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import requests


VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


def _field_names(x: Any) -> list[str]:
    if x is None:
        return []
    if dataclasses.is_dataclass(x):
        return sorted(f.name for f in dataclasses.fields(x))
    if hasattr(x, "__dict__"):
        return sorted(k for k in vars(x) if not k.startswith("_"))
    return []


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("cp932", "shift_jis", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp932", errors="replace")


def official_b_url(target: date) -> str:
    return (
        "https://www1.mbrace.or.jp/od2/B/"
        f"{target:%Y%m}/b{target:%y%m%d}.lzh"
    )


def download_official_b_txt(target: date, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    url = official_b_url(target)
    archive = work_dir / f"b{target:%y%m%d}.lzh"
    response = requests.get(
        url,
        headers={"User-Agent": "boat-ai-v2-historical-research/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    subprocess.run(
        ["7z", "x", "-y", f"-o{work_dir}", str(archive)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wanted = f"B{target:%y%m%d}.TXT".lower()
    matches = [
        p for p in work_dir.rglob("*")
        if p.is_file() and p.name.lower() == wanted
    ]
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected one extracted {wanted}, found {len(matches)}"
        )
    return matches[0]


def raw_structure(files: list[Any]) -> dict[str, Any]:
    per_file = []
    union = set()
    total_race_headers = 0
    total_program_markers = 0
    for item in files:
        path = Path(item)
        text = _read_text(path)
        compact = text.replace("　", "").replace(" ", "")
        venues = []
        for code, name in VENUE_NAMES.items():
            if name in compact:
                venues.append(code)
                union.add(code)
        race_headers = len(re.findall(r"(?m)^\s*(?:0?[1-9]|1[0-2])R\b", text))
        program_markers = text.count("番組")
        total_race_headers += race_headers
        total_program_markers += program_markers
        per_file.append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "venue_codes_detected": venues,
            "venue_count": len(venues),
            "race_header_count": race_headers,
            "program_marker_count": program_markers,
        })
    return {
        "extracted_file_count": len(files),
        "venue_codes_detected": sorted(union),
        "venue_count": len(union),
        "race_header_count": total_race_headers,
        "program_marker_count": total_program_markers,
        "files": per_file,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2025-07-01")
    ap.add_argument("--cache-dir", default=".bfile-probe-cache")
    args = ap.parse_args()
    target = date.fromisoformat(args.date)

    from boatrace_lzh import ScheduleParser

    txt_path = download_official_b_txt(target, Path(args.cache_dir))
    files = [str(txt_path)]
    structure = raw_structure(files)

    parser_files = {txt_path.name: _read_text(txt_path)}
    parsed = ScheduleParser().parse(parser_files)
    parsed_races = list(getattr(parsed, "races", []) or [])
    parsed_racers = list(getattr(parsed, "racers", []) or [])
    parsed_entries = list(getattr(parsed, "entries", []) or [])

    payload = {
        "contract": "OFFICIAL_BFILE_STRUCTURE_PROBE_V2",
        "target_date": target.isoformat(),
        "source": "BOATRACE_OFFICIAL_B_DAILY_LZH",
        "result_file_read": False,
        "odds_read": False,
        "payout_read": False,
        "db_read": False,
        "db_write": False,
        "raw_structure": structure,
        "third_party_parser": {
            "races": len(parsed_races),
            "racers": len(parsed_racers),
            "entries": len(parsed_entries),
            "race_fields": _field_names(parsed_races[0]) if parsed_races else [],
            "racer_fields": _field_names(parsed_racers[0]) if parsed_racers else [],
            "entry_fields": _field_names(parsed_entries[0]) if parsed_entries else [],
            "entry_shape_6_per_race": (
                len(parsed_entries) == len(parsed_races) * 6
                if parsed_entries
                else None
            ),
        },
        "parser_covers_all_detected_venues": (
            len(parsed_races) >= structure["venue_count"] * 12
            if structure["venue_count"]
            else None
        ),
        "production_change": False,
        "purchase_action": False,
    }
    Path("official-bfile-structure-probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OFFICIAL_BFILE_STRUCTURE=" + json.dumps(payload, ensure_ascii=False, sort_keys=True))

    if structure["venue_count"] < 1:
        raise RuntimeError("no known venue marker detected in official B text")
    if payload["third_party_parser"]["entry_shape_6_per_race"] is False:
        raise RuntimeError("third-party parser does not expose six entries per parsed race")

    print("OFFICIAL_BFILE_STRUCTURE_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
