# -*- coding: utf-8 -*-
"""
probe_k_file_pg.py

BOAT RACE公式ダウンロードページ構造調査。
全a / iframe / form / script src を表示する。
DB更新なし。
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

VERSION = "2026-08-17 k-file-page-structure-v3"

URL = "https://www.boatrace.jp/owpc/pc/extra/data/download.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

TIMEOUT = 30


def main():
    print(f"✅ probe_k_file_pg.py VERSION {VERSION}", flush=True)
    print("DB書き込みなし。", flush=True)

    r = requests.get(
        URL,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    print(f"status={r.status_code}", flush=True)
    print(f"final_url={r.url}", flush=True)
    print(f"bytes={len(r.content)}", flush=True)
    print(f"content_type={r.headers.get('Content-Type')}", flush=True)

    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"

    soup = BeautifulSoup(r.text, "html.parser")

    print("\n=== PAGE TITLE ===")
    print(soup.title.get_text(" ", strip=True) if soup.title else "NONE")

    print("\n=== TEXT AROUND DOWNLOAD WORDS ===")
    text = soup.get_text("\n", strip=True)
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    for i, line in enumerate(lines):
        if any(
            key in line
            for key in [
                "競走成績",
                "番組表",
                "ダウンロード",
                "成績",
            ]
        ):
            print("-" * 80)
            for x in lines[max(0, i - 3): min(len(lines), i + 4)]:
                print(x)

    print("\n=== ALL A LINKS ===")

    count = 0
    for a in soup.find_all("a"):
        href = a.get("href")
        text = " ".join(a.get_text(" ", strip=True).split())

        if not href:
            continue

        absolute = urljoin(r.url, href)

        print(
            f"{count:03d} TEXT={text!r}\n"
            f"    HREF={href!r}\n"
            f"    URL={absolute}",
            flush=True,
        )
        count += 1

    print(f"a_count={count}", flush=True)

    print("\n=== IFRAMES ===")
    for iframe in soup.find_all("iframe"):
        print(
            f"src={iframe.get('src')!r} "
            f"url={urljoin(r.url, iframe.get('src') or '')}",
            flush=True,
        )

    print("\n=== FORMS ===")
    for form in soup.find_all("form"):
        print(
            f"method={form.get('method')!r} "
            f"action={form.get('action')!r} "
            f"url={urljoin(r.url, form.get('action') or '')}",
            flush=True,
        )

    print("\n=== SCRIPT SRC ===")
    for script in soup.find_all("script"):
        src = script.get("src")
        if src:
            print(
                f"src={src!r}\n"
                f"url={urljoin(r.url, src)}",
                flush=True,
            )

    print("\n=== HTML keyword check ===")

    lower = r.text.lower()

    for key in [
        "mbrace",
        "od2",
        ".lzh",
        ".zip",
        "dindex",
        "download",
        "競走成績",
    ]:
        print(
            f"{key!r}: {'FOUND' if key.lower() in lower else 'NOT_FOUND'}",
            flush=True,
        )

    print("\n=== structure probe finished ===", flush=True)


if __name__ == "__main__":
    main()