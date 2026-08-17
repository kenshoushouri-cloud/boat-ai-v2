# -*- coding: utf-8 -*-
"""
probe_historical_odds_html_pg.py

指定レースのBOAT RACE公式 odds3t HTMLを取得し、
現在のparse_odds3t()が0件になる理由を診断する。

DB書き込みなし。

環境変数:
  TARGET_RACE_ID=20260731_13_10
"""

from __future__ import annotations

import os
import re

from bs4 import BeautifulSoup
import repair_month_all_pg as rp

VERSION = "2026-08-18 historical-odds-html-diagnose-v1"
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "20260731_13_10")

KEYWORDS = (
    "3連単オッズ",
    "3連単",
    "締切",
    "発売",
    "オッズ",
    "データがありません",
    "発売しておりません",
    "レース開始後",
    "締切時オッズ",
)


def main():
    print(f"✅ probe_historical_odds_html_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print("DB書き込みなし。", flush=True)

    parsed = rp._parse_race_id(TARGET_RACE_ID)
    if not parsed:
        raise RuntimeError("TARGET_RACE_ID が不正です")

    date_str, venue_id, race_no = parsed
    url = rp._official_url("odds3t", date_str, venue_id, race_no)
    print(f"URL={url}", flush=True)

    html = rp._fetch(url)
    if not html:
        print("FETCH=NONE", flush=True)
        return

    print(f"html_chars={len(html)}", flush=True)
    print(f"looks_no_race={rp._looks_no_race(html)}", flush=True)

    rows = rp.parse_odds3t(html, TARGET_RACE_ID)
    print(f"parse_odds3t_rows={len(rows)}", flush=True)

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    print("\n=== KEYWORD COUNTS ===", flush=True)
    for kw in KEYWORDS:
        print(f"{kw}: {text.count(kw)}", flush=True)

    print("\n=== KEYWORD CONTEXT ===", flush=True)
    flat = re.sub(r"\s+", " ", text)
    for kw in KEYWORDS:
        pos = 0
        shown = 0
        while True:
            idx = flat.find(kw, pos)
            if idx < 0 or shown >= 5:
                break
            a = max(0, idx - 180)
            b = min(len(flat), idx + 360)
            print(f"[{kw} #{shown+1}] {flat[a:b]}", flush=True)
            pos = idx + len(kw)
            shown += 1

    print("\n=== ODDS-LIKE LINES ===", flush=True)
    shown = 0
    for line in text.splitlines():
        s = re.sub(r"\s+", " ", line).strip()
        if not s:
            continue
        # ticket/oddsらしい行、艇番が連続する行、数値密集行を拾う
        if (
            re.search(r"[1-6]\s*[-－]\s*[1-6]\s*[-－]\s*[1-6]", s)
            or re.search(r"\b[1-6]\s+[1-6]\s+[1-6]\s+\d+(?:\.\d+)?\b", s)
            or ("3連単" in s)
        ):
            print(s, flush=True)
            shown += 1
            if shown >= 120:
                break
    print(f"odds_like_lines_shown={shown}", flush=True)

    print("\n=== TABLE SUMMARY ===", flush=True)
    tables = soup.find_all("table")
    print(f"table_count={len(tables)}", flush=True)
    for i, table in enumerate(tables[:20], start=1):
        rows_html = table.find_all("tr")
        ttext = re.sub(r"\s+", " ", table.get_text(" ", strip=True))
        print(
            f"table#{i} tr_count={len(rows_html)} text_head={ttext[:240]}",
            flush=True,
        )

    print("\n=== RAW HTML MARKER CHECK ===", flush=True)
    raw = html
    markers = [
        "odds3t",
        "3連単オッズ",
        "is-odds",
        "table",
        "odds",
        "締切時オッズ",
        "レース開始後",
    ]
    for m in markers:
        print(f"{m}: {'FOUND' if m in raw else 'NOT_FOUND'}", flush=True)

    print("RESULT=SUCCESS", flush=True)


if __name__ == "__main__":
    main()