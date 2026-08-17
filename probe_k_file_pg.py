# -*- coding: utf-8 -*-
"""
probe_k_file_pg.py

BOAT RACE公式 download.html 内の
mbrace / od2 / dindex 周辺だけを抜き出す。
DB更新なし。
"""

from __future__ import annotations

import re
import html as html_lib
import requests

VERSION = "2026-08-17 k-file-url-context-v5"

URL = "https://www.boatrace.jp/owpc/pc/extra/data/download.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

KEYWORDS = [
    "mbrace",
    "od2",
    "dindex",
    "競走成績",
    "番組表",
]

TIMEOUT = 30


def compact(s: str) -> str:
    s = html_lib.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def main():
    print(f"✅ probe_k_file_pg.py VERSION {VERSION}", flush=True)
    print("DB書き込みなし。", flush=True)

    r = requests.get(
        URL,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print(
        f"status={r.status_code} bytes={len(r.content)} final={r.url}",
        flush=True,
    )

    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"

    src = r.text

    print("\n=== KEYWORD CONTEXT ===", flush=True)

    for key in KEYWORDS:
        matches = list(
            re.finditer(
                re.escape(key),
                src,
                flags=re.IGNORECASE,
            )
        )

        print(
            f"\nKEY={key!r} count={len(matches)}",
            flush=True,
        )

        for i, m in enumerate(matches[:10], start=1):
            start = max(0, m.start() - 350)
            end = min(len(src), m.end() + 350)

            context = compact(src[start:end])

            print(
                f"[{i}] {context}",
                flush=True,
            )

    print("\n=== ABSOLUTE URL CANDIDATES ===", flush=True)

    urls = set(
        re.findall(
            r'https?://[^"\'<>\s]+',
            html_lib.unescape(src),
            flags=re.IGNORECASE,
        )
    )

    selected = [
        u
        for u in urls
        if any(
            k in u.lower()
            for k in (
                "mbrace",
                "od2",
                "dindex",
                ".lzh",
            )
        )
    ]

    if selected:
        for u in sorted(selected):
            print(u, flush=True)
    else:
        print("NONE", flush=True)

    print("\n=== HREF CANDIDATES ===", flush=True)

    hrefs = re.findall(
        r'''href\s*=\s*["']([^"']+)["']''',
        src,
        flags=re.IGNORECASE,
    )

    selected_hrefs = []

    for h in hrefs:
        low = h.lower()

        if (
            "mbrace" in low
            or "od2" in low
            or "dindex" in low
            or "/k/" in low
            or "/b/" in low
        ):
            selected_hrefs.append(h)

    if selected_hrefs:
        for h in sorted(set(selected_hrefs)):
            print(h, flush=True)
    else:
        print("NONE", flush=True)

    print("\n=== probe finished ===", flush=True)


if __name__ == "__main__":
    main()