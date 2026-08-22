# -*- coding: utf-8 -*-
"""Read-only HTTP probe for official BOAT RACE motor use-start dates.

No DB writes. No prediction/Shadow/LINE changes.
"""
from __future__ import annotations

import re
from datetime import date

import requests
from bs4 import BeautifulSoup

PROBES = [
    ("06", "20260526", date(2026, 4, 9)),
    ("13", "20260609", date(2026, 4, 17)),
    ("24", "20260617", date(2026, 5, 24)),
    ("13", "20220724", date(2022, 4, 10)),
]

PATTERNS = [
    re.compile(r"(?:現行の)?モーター(?:は|の)?[^。]{0,50}?使用開始(?:が|は)?\s*(\d{1,2})月(\d{1,2})日"),
    re.compile(r"モーター(?:は|の)?[^。]{0,40}?(\d{1,2})月(\d{1,2})日から使用"),
    re.compile(r"(?:使用開始|使用開始日)[^0-9]{0,15}(\d{1,2})月(\d{1,2})日"),
]


def resolve_year(hd: str, month: int, day: int) -> date:
    event = date(int(hd[:4]), int(hd[4:6]), int(hd[6:8]))
    candidate = date(event.year, month, day)
    if candidate > event:
        candidate = date(event.year - 1, month, day)
    return candidate


def parse_start(text: str, hd: str):
    normalized = re.sub(r"\s+", "", text)
    for idx, pat in enumerate(PATTERNS, start=1):
        m = pat.search(normalized)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                try:
                    return resolve_year(hd, month, day), idx
                except ValueError:
                    pass
    return None, None


def main() -> None:
    print("MOTOR_START_PROBE_MODE=http_read_only", flush=True)
    print("MOTOR_START_PROBE_POLICY=official_rankingmotor_no_db_writes", flush=True)
    ok = 0
    for venue, hd, expected in PROBES:
        url = f"https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={venue}"
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        print(f"MOTOR_START_HTTP=venue:{venue} hd:{hd} status:{r.status_code}", flush=True)
        r.raise_for_status()
        text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
        parsed, pattern = parse_start(text, hd)
        passed = parsed == expected
        print(f"MOTOR_START_PARSE=venue:{venue} hd:{hd} parsed:{parsed} expected:{expected} pattern:{pattern} pass:{int(passed)}", flush=True)
        ok += int(passed)
    print(f"MOTOR_START_PROBE_PASS={ok}/{len(PROBES)}", flush=True)
    if ok != len(PROBES):
        raise SystemExit(2)
    print("MOTOR_START_PROBE_RESULT=PASS_HTTP_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
