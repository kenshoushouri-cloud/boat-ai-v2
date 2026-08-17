# -*- coding: utf-8 -*-
"""
probe_k_month_pg.py

mbrace公式の月別競走成績ページから
TARGET_DATEのKファイルURLを確定して取得確認する。

DB更新なし。
"""

from __future__ import annotations

import os
import re
import requests
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

VERSION = "2026-08-17 k-month-discovery-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}


def fetch(url: str):
    return requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )


def main():
    dt = datetime.strptime(TARGET_DATE, "%Y-%m-%d")

    yyyymm = dt.strftime("%Y%m")
    yymmdd = dt.strftime("%y%m%d")
    day = dt.strftime("%d")

    month_url = (
        f"https://www1.mbrace.or.jp/"
        f"od2/K/{yyyymm}/mday.html"
    )

    print(
        f"✅ probe_k_month_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"MONTH_URL={month_url}", flush=True)
    print("DB書き込みなし。", flush=True)

    r = fetch(month_url)

    print(
        f"month_status={r.status_code} "
        f"bytes={len(r.content)} "
        f"final={r.url}",
        flush=True,
    )

    if r.status_code != 200:
        print("RESULT=MONTH_PAGE_NOT_FOUND", flush=True)
        return

    r.encoding = r.apparent_encoding or "shift_jis"

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    print("\n=== SCRIPT CHECK ===", flush=True)

    # 過去実装で使われていた dir="..." を確認
    dirs = re.findall(
        r'''dir\s*=\s*["']([^"']+)["']''',
        html,
        flags=re.IGNORECASE,
    )

    if dirs:
        for x in sorted(set(dirs)):
            print(f"dir={x}", flush=True)
    else:
        print("dir=NONE", flush=True)

    print("\n=== TARGET DAY LINKS ===", flush=True)

    target_links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        text = " ".join(
            a.get_text(" ", strip=True).split()
        )

        low = href.lower()

        if (
            yymmdd in low
            or f"k{yymmdd}" in low
            or text == f"{int(day)}日"
            or text == str(int(day))
        ):
            absolute = urljoin(r.url, href)
            target_links.append(
                (text, href, absolute)
            )

    if target_links:
        for i, (text, href, absolute) in enumerate(
            target_links,
            1,
        ):
            print(
                f"{i:02d} TEXT={text!r} "
                f"HREF={href!r} "
                f"URL={absolute}",
                flush=True,
            )
    else:
        print("NONE", flush=True)

    print("\n=== BUILD K URL ===", flush=True)

    candidates = []

    # 月別ページURLから最も自然なURL
    candidates.append(
        f"https://www1.mbrace.or.jp/"
        f"od2/K/{yyyymm}/k{yymmdd}.lzh"
    )

    # dirがHTML内にある場合も候補化
    for d in dirs:
        base = urljoin(r.url, d)
        candidates.append(
            urljoin(base, f"k{yymmdd}.lzh")
        )

    # href直リンクも候補
    for _, _, absolute in target_links:
        if ".lzh" in absolute.lower():
            candidates.append(absolute)

    # 重複除去
    unique = []
    seen = set()

    for x in candidates:
        if x not in seen:
            seen.add(x)
            unique.append(x)

    for i, url in enumerate(unique, 1):
        print(f"{i:02d} {url}", flush=True)

    print("\n=== DOWNLOAD TEST ===", flush=True)

    success = False

    for url in unique:
        rr = fetch(url)

        print(
            f"TRY={url} "
            f"status={rr.status_code} "
            f"bytes={len(rr.content)} "
            f"ctype={rr.headers.get('Content-Type')}",
            flush=True,
        )

        if rr.status_code != 200:
            continue

        if len(rr.content) < 100:
            continue

        first64 = rr.content[:64]

        print(
            f"first32={rr.content[:32].hex()}",
            flush=True,
        )

        if b"-lh" in first64:
            print(
                "archive_signature=LZH/LHA likely",
                flush=True,
            )
        else:
            print(
                "archive_signature=UNKNOWN",
                flush=True,
            )

        out = "/tmp/boatrace_k_target.lzh"

        with open(out, "wb") as f:
            f.write(rr.content)

        print(f"saved={out}", flush=True)

        success = True
        break

    print(
        f"RESULT={'SUCCESS' if success else 'DOWNLOAD_FAILED'}",
        flush=True,
    )


if __name__ == "__main__":
    main()