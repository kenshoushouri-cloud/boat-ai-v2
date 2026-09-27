# -*- coding: utf-8 -*-
"""Build the 2026-09-28 day-strength seed from seven immutable formal artifacts.

Input-only. No results, payouts, odds, DB, network, persistence, or Production.
"""
from __future__ import annotations

import json
import statistics
import zipfile
from pathlib import Path

from research.v4_formal_day_strength_shadow import extract_formal_day

EXPECTED_DATES = [
    "2026-09-21",
    "2026-09-22",
    "2026-09-23",
    "2026-09-24",
    "2026-09-25",
    "2026-09-26",
    "2026-09-27",
]


def load_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        return json.loads(zf.read("candidate-discovery-v4-prospective-freeze.json"))


def build_seed(directory: str | Path) -> dict:
    root = Path(directory)
    days = []
    for day in EXPECTED_DATES:
        payload = load_zip(root / f"{day}.zip")
        x = extract_formal_day(payload)
        if x.target_date.isoformat() != day:
            raise ValueError(f"target date mismatch: {day}")
        days.append(x)
    strengths = [x.day_strength for x in days]
    reference = float(statistics.median(strengths))
    return {
        "contract": "V4_FORMAL_DAY_STRENGTH_SEED_20260928_V1",
        "target_date": "2026-09-28",
        "lookback_dates": EXPECTED_DATES,
        "lookback_strengths": [round(x, 8) for x in strengths],
        "reference_strength": round(reference, 8),
        "selection_rule": "KEEP_SHADOW iff target_day_strength >= reference_strength",
        "result_read": False,
        "payout_read": False,
        "odds_read": False,
        "db_read": False,
        "production_change": False,
        "promotion_allowed": False,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: v4_formal_day_strength_seed.py ARTIFACT_DIR")
    print("V4_DAY_STRENGTH_SEED_RESULT=" + json.dumps(build_seed(sys.argv[1]), sort_keys=True))
    print("V4_DAY_STRENGTH_SEED_PASS_INPUT_ONLY")
