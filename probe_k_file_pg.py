# -*- coding: utf-8 -*-
"""
probe_k_file_pg.py

BOAT RACE公式ダウンロードページから
現在の「競走成績ダウンロード」リンクを追跡するプローブ。

DB更新なし。
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

VERSION = "2026-08-17 k-file-link-discovery-v2"

START_URL = "https://www.boatrace.jp/owpc/pc/extra/data/download.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

TIMEOUT = 30


def fetch(url: str):
    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    print("=" * 90, flush=True)
    print(f"GET={url}", flush=True)
    print(f"status={r.status_code}", flush=True)
    print(f"final_url={r.url}", flush=True)
    print(f"content_type={r.headers.get('Content-Type')}", flush=True)
    print(f"bytes={len(r.content)}", flush=True)
    return r


def main():
    print(
        f"✅ probe_k_file_pg.py VERSION {VERSION}",
        flush=True,
    )
    print("DB書き込みはありません。", flush=True)

    r = fetch(START_URL)
    if r.status_code != 200:
        raise RuntimeError("official download page fetch failed")

    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    print("\n=== links containing download / race result words ===")

    candidates = []

    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = a.get("href")
        absolute = urljoin(r.url, href)

        combined = (text + " " + absolute).lower()

        if (
            "競走成績" in text
            or "成績ダウンロード" in text
            or "race" in combined
            or "/k/" in combined
            or "od2" in combined
            or "mbrace" in combined
        ):
            print(
                f"TEXT={text!r}\nURL={absolute}",
                flush=True,
            )
            candidates.append((text, absolute))

    print(
        f"\ncandidate_count={len(candidates)}",
        flush=True,
    )

    # 有力リンクを1階層だけ追う
    seen = set()

    for text, url in candidates:
        if url in seen:
            continue
        seen.add(url)

        print("\n" + "#" * 90, flush=True)
        print(f"FOLLOW text={text!r}", flush=True)

        try:
            r2 = fetch(url)

            if r2.status_code != 200:
                continue

            ctype = (r2.headers.get("Content-Type") or "").lower()

            # HTMLならリンクを列挙
            if "html" in ctype or r2.content[:20].lower().startswith(b"<!doctype"):
                r2.encoding = r2.apparent_encoding or "utf-8"
                s2 = BeautifulSoup(r2.text, "html.parser")

                print("--- child links ---", flush=True)

                child_count = 0

                for a in s2.find_all("a", href=True):
                    t = " ".join(
                        a.get_text(" ", strip=True).split()
                    )
                    u = urljoin(r2.url, a["href"])

                    low = u.lower()

                    if (
                        ".lzh" in low
                        or ".zip" in low
                        or "/k/" in low
                        or "k26" in low
                        or "202608" in low
                        or "260816" in low
                    ):
                        print(
                            f"TEXT={t!r}\nURL={u}",
                            flush=True,
                        )
                        child_count += 1

                print(
                    f"child_candidate_count={child_count}",
                    flush=True,
                )

        except Exception as exc:
            print(
                f"FOLLOW_ERROR={type(exc).__name__}: {exc}",
                flush=True,
            )

    print("\n=== discovery finished ===", flush=True)


if __name__ == "__main__":
    main()