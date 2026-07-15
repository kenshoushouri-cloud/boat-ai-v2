# -*- coding: utf-8 -*-
"""
debug_beforeinfo_extra_pg.py

BOAT RACE公式 beforeinfo ページの追加特徴量構造を確認する診断用スクリプト。
DB更新・LINE通知・購入処理は行いません。

確認対象:
- 当日体重 / 調整重量
- 部品交換 / 新プロペラ
- 前走R / 前走進入 / 前走ST / 前走着順
- 安定板 / 進入固定 / 距離

Start Command:
    python -u debug_beforeinfo_extra_pg.py

必須Variables:
    TARGET_DATE=YYYY-MM-DD
    TARGET_RACE_ID=YYYYMMDD_場コード_レース番号

例:
    TARGET_DATE=2026-07-15
    TARGET_RACE_ID=20260715_24_09
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, List

import requests
from bs4 import BeautifulSoup

TARGET_DATE = os.getenv("TARGET_DATE", "").strip()
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "").strip()
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))

OFFICIAL = "https://www.boatrace.jp/owpc/pc/race"

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; boat-ai-beforeinfo-debug/1.0)"
        ),
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    }
)

KEYWORDS = [
    "体重",
    "調整",
    "部品",
    "交換",
    "新プロペラ",
    "新ペラ",
    "安定板",
    "進入固定",
    "前走",
    "着順",
    "ST",
    "スタート",
    "進入",
    "コース",
    "R",
]


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _parse_target() -> tuple[str, str, int]:
    if not TARGET_DATE:
        raise RuntimeError("TARGET_DATE が必要です。")
    m = re.fullmatch(r"(\d{8})_(\d{2})_(\d{2})", TARGET_RACE_ID)
    if not m:
        raise RuntimeError(
            "TARGET_RACE_ID は YYYYMMDD_場コード_レース番号 形式です。"
        )
    ymd, venue_id, race_no_s = m.groups()
    if ymd != TARGET_DATE.replace("-", ""):
        raise RuntimeError(
            "TARGET_DATE と TARGET_RACE_ID の日付が一致しません。"
        )
    return ymd, venue_id, int(race_no_s)


def _official_url(
    kind: str,
    ymd: str,
    venue_id: str,
    race_no: int,
) -> str:
    return (
        f"{OFFICIAL}/{kind}"
        f"?rno={race_no}&jcd={venue_id}&hd={ymd}"
    )


def _print_keyword_context(text: str) -> None:
    print("\n=== KEYWORD CONTEXT ===", flush=True)
    for keyword in KEYWORDS:
        positions = [
            m.start()
            for m in re.finditer(re.escape(keyword), text, flags=re.I)
        ]
        if not positions:
            continue
        print(f"\n[{keyword}] hits={len(positions)}", flush=True)
        for pos in positions[:10]:
            start = max(0, pos - 120)
            end = min(len(text), pos + 260)
            print(text[start:end], flush=True)


def _print_tables(soup: BeautifulSoup) -> None:
    print("\n=== TABLE STRUCTURE ===", flush=True)
    tables = soup.find_all("table")
    print(f"tables={len(tables)}", flush=True)

    for table_index, table in enumerate(tables):
        attrs = {
            "class": table.get("class"),
            "id": table.get("id"),
        }
        rows = table.find_all("tr")
        table_text = _norm(table.get_text(" ", strip=True))

        if not any(keyword in table_text for keyword in KEYWORDS):
            # 選手6艇の表も念のため表示
            if not re.search(r"\b[1-6]\b", table_text):
                continue

        print("\n" + "=" * 80, flush=True)
        print(
            f"TABLE[{table_index}] attrs={attrs} rows={len(rows)}",
            flush=True,
        )
        print(f"TEXT_HEAD={table_text[:1200]}", flush=True)

        for row_index, tr in enumerate(rows):
            cells = [
                _norm(cell.get_text(" ", strip=True))
                for cell in tr.find_all(["th", "td"])
            ]
            if not cells:
                continue
            joined = " | ".join(cells)
            if (
                any(keyword in joined for keyword in KEYWORDS)
                or re.search(r"(^|\| )([1-6])(\||$)", joined)
                or re.search(r"\d{2}(?:\.\d)?\s*kg", joined, flags=re.I)
            ):
                print(
                    f"  row[{row_index:02d}] cells={len(cells)} "
                    f"{joined[:1800]}",
                    flush=True,
                )


def _print_candidate_elements(soup: BeautifulSoup) -> None:
    print("\n=== CANDIDATE ELEMENTS ===", flush=True)

    for index, tag in enumerate(
        soup.find_all(
            ["div", "section", "ul", "ol", "dl", "p", "span"]
        )
    ):
        text = _norm(tag.get_text(" ", strip=True))
        if not text or len(text) > 2500:
            continue
        if not any(keyword in text for keyword in KEYWORDS):
            continue

        classes = " ".join(tag.get("class") or [])
        tag_id = tag.get("id")
        print(
            f"[{index:04d}] <{tag.name}> "
            f"class={classes or '-'} id={tag_id or '-'} "
            f"text={text[:1200]}",
            flush=True,
        )


def main() -> None:
    print(
        "✅ debug_beforeinfo_extra_pg.py "
        "VERSION 2026-07-15 structure-diagnostic-v1",
        flush=True,
    )
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    ymd, venue_id, race_no = _parse_target()
    url = _official_url("beforeinfo", ymd, venue_id, race_no)

    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print(f"URL={url}", flush=True)

    response = SESSION.get(url, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    text = _norm(soup.get_text(" ", strip=True))

    print(f"html_bytes={len(html.encode('utf-8'))}", flush=True)
    print(f"text_chars={len(text)}", flush=True)
    print("\n=== PAGE TEXT HEAD ===", flush=True)
    print(text[:5000], flush=True)

    _print_keyword_context(text)
    _print_tables(soup)
    _print_candidate_elements(soup)

    print("\n=== RAW HTML KEYWORD SNIPPETS ===", flush=True)
    normalized_html = unicodedata.normalize("NFKC", html)
    for keyword in KEYWORDS:
        positions = [
            m.start()
            for m in re.finditer(
                re.escape(keyword),
                normalized_html,
                flags=re.I,
            )
        ]
        if not positions:
            continue
        print(f"\n[{keyword}] hits={len(positions)}", flush=True)
        for pos in positions[:5]:
            start = max(0, pos - 350)
            end = min(len(normalized_html), pos + 800)
            snippet = normalized_html[start:end]
            print(snippet, flush=True)

    print("\n=== debug beforeinfo extra finished ===", flush=True)


if __name__ == "__main__":
    main()