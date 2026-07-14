# -*- coding: utf-8 -*-
"""
debug_parse_entries_pg.py

repair_month_all_pg.py の parse_entries が、
公式racelistのどの数値を拾っているか確認する診断用スクリプト。

読み取り専用。DB更新・LINE送信なし。

Railway Start Command:
    python -u debug_parse_entries_pg.py

任意Variables:
    DEBUG_DATE=2026-06-06
    DEBUG_VENUE=01
    DEBUG_RACE_NO=7
    DEBUG_LANES=5,6
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

DEBUG_DATE = os.getenv("DEBUG_DATE", "2026-06-06")
DEBUG_VENUE = os.getenv("DEBUG_VENUE", "01").zfill(2)
DEBUG_RACE_NO = int(os.getenv("DEBUG_RACE_NO", "7"))
DEBUG_LANES = {
    int(x.strip())
    for x in os.getenv("DEBUG_LANES", "1,2,3,4,5,6").split(",")
    if x.strip()
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-entry-parser-debug/1.0)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def zen_to_han(s: str) -> str:
    return str(s or "").translate(str.maketrans({
        "０":"0","１":"1","２":"2","３":"3","４":"4","５":"5",
        "６":"6","７":"7","８":"8","９":"9","．":".","／":"/",
        "－":"-","　":" ","：":":",
    }))


def official_url() -> str:
    hd = DEBUG_DATE.replace("-", "")
    return (
        "https://www.boatrace.jp/owpc/pc/race/racelist"
        f"?rno={DEBUG_RACE_NO}&jcd={DEBUG_VENUE}&hd={hd}"
    )


def num(v: str) -> Optional[float]:
    try:
        return float(v.replace(",", ""))
    except Exception:
        return None


def main() -> None:
    url = official_url()
    print("✅ debug_parse_entries_pg.py VERSION 2026-07-14", flush=True)
    print(f"URL={url}", flush=True)

    r = SESSION.get(url, timeout=35)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    raw_lines = []
    for line in soup.get_text("\n", strip=True).splitlines():
        line = clean(zen_to_han(line))
        if line:
            raw_lines.append(line)

    body_start = 0
    for i, line in enumerate(raw_lines):
        if "登録番号/級別" in line:
            body_start = i
            break

    body_end = len(raw_lines)
    for i in range(body_start + 1, len(raw_lines)):
        if raw_lines[i] in (
            "今節成績",
            "モーター・ボート変更時は赤で表示されます。",
            "PAGE TOP",
        ):
            body_end = i
            break

    lines = raw_lines[body_start:body_end]

    print("\n=== HEADER / TABLE LABELS ===", flush=True)
    for i, line in enumerate(lines[:45]):
        print(f"{i:03d}: {line}", flush=True)

    lane_positions = []
    for i, line in enumerate(lines):
        if not re.fullmatch(r"[1-6]", line):
            continue
        look = " ".join(lines[i:i+8])
        if re.search(r"\b\d{4}\s*/\s*(A1|A2|B1|B2)\b", look):
            lane_positions.append((int(line), i))

    print("\n=== LANE SEGMENTS ===", flush=True)
    for idx, (lane, pos) in enumerate(lane_positions):
        if lane not in DEBUG_LANES:
            continue

        next_pos = lane_positions[idx + 1][1] if idx + 1 < len(lane_positions) else len(lines)
        seg_lines = lines[pos:next_pos]
        seg = " ".join(seg_lines)

        print("\n" + "=" * 80, flush=True)
        print(f"LANE={lane}", flush=True)

        for j, line in enumerate(seg_lines):
            print(f"  line[{j:02d}] = {line}", flush=True)

        nums = re.findall(r"\d+\.\d+|\d+", seg)
        print("\n  ALL NUM TOKENS", flush=True)
        for j, token in enumerate(nums):
            print(f"    nums[{j:02d}]={token}", flush=True)

        avg_idx = None
        for j, token in enumerate(nums):
            if re.fullmatch(r"0\.\d{2}", token):
                avg_idx = j
                break

        print(f"\n  avg_idx={avg_idx}", flush=True)
        if avg_idx is not None:
            seq = nums[avg_idx:]
            print("  CURRENT PARSER SEQUENCE", flush=True)
            names = [
                "avg_st",
                "national_win_rate",
                "national_place2_rate",
                "national_place3_rate",
                "local_win_rate",
                "local_place2_rate",
                "local_place3_rate",
                "motor_no",
                "motor_place2_rate",
                "motor_place3_rate",
                "boat_no",
                "boat_place2_rate",
                "boat_place3_rate",
            ]
            for j, name in enumerate(names):
                val = seq[j] if j < len(seq) else None
                print(f"    seq[{j:02d}] {name:24s} = {val}", flush=True)

        print("\n  HTML TABLE ROWS CONTAINING RACER", flush=True)
        racer_match = re.search(r"\b(\d{4})\s*/\s*(A1|A2|B1|B2)\b", seg)
        racer_no = racer_match.group(1) if racer_match else ""
        for tr in soup.find_all("tr"):
            cells = [
                clean(zen_to_han(td.get_text(" ", strip=True)))
                for td in tr.find_all(["td", "th"])
            ]
            if racer_no and any(racer_no in c for c in cells):
                for j, c in enumerate(cells):
                    print(f"    cell[{j:02d}]={c}", flush=True)

    print("\n=== debug finished ===", flush=True)


if __name__ == "__main__":
    main()