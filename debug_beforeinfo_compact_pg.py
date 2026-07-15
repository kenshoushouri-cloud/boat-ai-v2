# -*- coding: utf-8 -*-
"""
debug_beforeinfo_compact_pg.py

BOAT RACE公式 beforeinfo の追加情報を、Railwayのログ上限を超えないよう
必要箇所だけコンパクトに表示します。

DB更新・LINE通知・購入処理は行いません。

Start Command:
    python -u debug_beforeinfo_compact_pg.py

Variables:
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_ID=YYYYMMDD_場コード_レース番号
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

import requests
from bs4 import BeautifulSoup

TARGET_DATE = os.getenv("TARGET_DATE", "").strip()
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "").strip()
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))

OFFICIAL = "https://www.boatrace.jp/owpc/pc/race"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-beforeinfo-compact-debug/1.0)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _parse_target() -> tuple[str, str, int]:
    if not TARGET_DATE:
        raise RuntimeError("TARGET_DATE が必要です。")

    match = re.fullmatch(r"(\d{8})_(\d{2})_(\d{2})", TARGET_RACE_ID)
    if not match:
        raise RuntimeError(
            "TARGET_RACE_ID は YYYYMMDD_場コード_レース番号 形式です。"
        )

    ymd, venue_id, race_no_s = match.groups()
    if ymd != TARGET_DATE.replace("-", ""):
        raise RuntimeError(
            "TARGET_DATE と TARGET_RACE_ID の日付が一致しません。"
        )

    return ymd, venue_id, int(race_no_s)


def _cell_texts(row) -> list[str]:
    return [
        _norm(cell.get_text(" ", strip=True))
        for cell in row.find_all(["th", "td"], recursive=False)
    ]


def _print_relevant_tables(soup: BeautifulSoup) -> None:
    printed = 0

    for table_index, table in enumerate(soup.find_all("table")):
        text = _norm(table.get_text(" ", strip=True))

        relevant = any(
            key in text
            for key in (
                "前走",
                "着順",
                "部品交換",
                "調整重量",
                "体重",
                "スタート展示",
            )
        )
        if not relevant:
            continue

        rows = table.find_all("tr")
        print(
            f"\nTABLE[{table_index}] "
            f"class={' '.join(table.get('class') or []) or '-'} "
            f"rows={len(rows)}",
            flush=True,
        )

        for row_index, row in enumerate(rows):
            cells = _cell_texts(row)
            if not cells:
                continue

            joined = " | ".join(cells)
            if (
                any(
                    key in joined
                    for key in (
                        "前走",
                        "R",
                        "ST",
                        "着順",
                        "体重",
                        "調整",
                        "部品",
                        "交換",
                        "プロペラ",
                    )
                )
                or re.search(r"\b\d{2}(?:\.\d)?\s*kg\b", joined)
                or re.search(r"(^|\| )([1-6])(\||$)", joined)
            ):
                print(
                    f"  row[{row_index:02d}] "
                    f"cells={len(cells)} :: {joined[:1200]}",
                    flush=True,
                )

        printed += 1
        if printed >= 8:
            break

    print(f"\nrelevant_tables_printed={printed}", flush=True)


def _print_tbody_groups(soup: BeautifulSoup) -> None:
    print("\n=== TBODY GROUPS WITH R/ST/着順 ===", flush=True)

    groups_printed = 0
    for index, tbody in enumerate(soup.find_all("tbody")):
        text = _norm(tbody.get_text(" ", strip=True))
        if not all(key in text for key in ("R", "ST", "着順")):
            continue

        print(
            f"\nTBODY[{index}] "
            f"class={' '.join(tbody.get('class') or []) or '-'}",
            flush=True,
        )

        for row_index, row in enumerate(tbody.find_all("tr", recursive=False)):
            cells = _cell_texts(row)
            if cells:
                print(
                    f"  row[{row_index:02d}] "
                    f"cells={len(cells)} :: {' | '.join(cells)[:1000]}",
                    flush=True,
                )

        groups_printed += 1
        if groups_printed >= 12:
            break

    print(f"\ntbody_groups_printed={groups_printed}", flush=True)


def _print_keyword_summary(text: str) -> None:
    print("\n=== KEYWORD COUNTS ===", flush=True)
    for keyword in (
        "体重",
        "調整重量",
        "部品交換",
        "新プロペラ",
        "安定板",
        "進入固定",
        "前走",
        "着順",
        "ST",
    ):
        print(
            f"{keyword}: {len(re.findall(re.escape(keyword), text, flags=re.I))}",
            flush=True,
        )


def main() -> None:
    print(
        "✅ debug_beforeinfo_compact_pg.py "
        "VERSION 2026-07-15 compact-structure-v1",
        flush=True,
    )
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    ymd, venue_id, race_no = _parse_target()
    url = (
        f"{OFFICIAL}/beforeinfo"
        f"?rno={race_no}&jcd={venue_id}&hd={ymd}"
    )

    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print(f"URL={url}", flush=True)

    response = SESSION.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    text = _norm(soup.get_text(" ", strip=True))

    print(f"html_chars={len(response.text)}", flush=True)
    print(f"text_chars={len(text)}", flush=True)

    _print_keyword_summary(text)
    _print_relevant_tables(soup)
    _print_tbody_groups(soup)

    print("\n=== compact beforeinfo debug finished ===", flush=True)


if __name__ == "__main__":
    main()