# -*- coding: utf-8 -*-
"""
probe_k_index_pg.py

mbrace公式の競走成績ダウンロード index から
TARGET_DATE のKファイル候補リンクを自動発見して取得確認する。

DB更新なし。
大量ログを避けるため、対象日とその近傍リンクだけを出力する。
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

VERSION = "2026-08-17 k-index-target-discovery-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
INDEX_URL = "https://www1.mbrace.or.jp/od2/K/dindex.html"
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

def fetch(url: str):
    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    return r

def main():
    print(f"✅ probe_k_index_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("DB書き込みなし。", flush=True)

    dt = datetime.strptime(TARGET_DATE, "%Y-%m-%d")
    ymd8 = dt.strftime("%Y%m%d")
    ymd6 = dt.strftime("%y%m%d")
    yyyy_mm = dt.strftime("%Y%m")
    mmdd = dt.strftime("%m%d")

    r = fetch(INDEX_URL)
    print(
        f"INDEX status={r.status_code} bytes={len(r.content)} final={r.url}",
        flush=True,
    )
    r.raise_for_status()

    # 日本語ページでもリンクURL自体はASCIIなので、文字化けしても探索できる。
    r.encoding = r.apparent_encoding or "shift_jis"
    soup = BeautifulSoup(r.text, "html.parser")

    print("\n=== TARGET-LIKE LINKS ===", flush=True)

    found = []
    all_links = []

    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        label = " ".join(a.get_text(" ", strip=True).split())
        absolute = urljoin(r.url, href)
        low = absolute.lower()

        all_links.append((label, href, absolute))

        # 日付、kYYMMDD、YYYYMM、MMDD のいずれかを含むものだけ
        if (
            ymd8 in low
            or ymd6 in low
            or f"k{ymd6}" in low
            or yyyy_mm in low
            or mmdd in low
        ):
            found.append((label, href, absolute))

    if found:
        for i, (label, href, absolute) in enumerate(found[:40], 1):
            print(
                f"{i:02d} TEXT={label!r} HREF={href!r} URL={absolute}",
                flush=True,
            )
    else:
        print("NONE", flush=True)

    print(f"target_like_count={len(found)}", flush=True)

    print("\n=== DIRECT LZH CANDIDATES FROM INDEX ===", flush=True)
    lzh_links = [
        (label, href, absolute)
        for label, href, absolute in all_links
        if ".lzh" in absolute.lower()
    ]

    target_lzh = [
        x for x in lzh_links
        if (
            ymd8 in x[2].lower()
            or ymd6 in x[2].lower()
            or f"k{ymd6}" in x[2].lower()
        )
    ]

    if target_lzh:
        for i, (label, href, absolute) in enumerate(target_lzh[:20], 1):
            print(
                f"{i:02d} TEXT={label!r} URL={absolute}",
                flush=True,
            )
    else:
        print("NONE", flush=True)

    print(f"index_lzh_count={len(lzh_links)}", flush=True)
    print(f"target_lzh_count={len(target_lzh)}", flush=True)

    # dindexが月別/年別ページへの導線だけを持つ場合、
    # TARGET_DATEに関連しそうなページを1階層だけ追う。
    follow_candidates = []
    for label, href, absolute in all_links:
        low = absolute.lower()
        if ".lzh" in low:
            continue
        if (
            yyyy_mm in low
            or dt.strftime("%Y") in low
            or dt.strftime("%m") in low
            or "index" in low
        ):
            follow_candidates.append((label, absolute))

    # 重複除去し、最大12ページまで。
    dedup = []
    seen = set()
    for x in follow_candidates:
        if x[1] in seen:
            continue
        seen.add(x[1])
        dedup.append(x)

    discovered = []
    for label, url in dedup[:12]:
        try:
            r2 = fetch(url)
            if r2.status_code != 200:
                continue

            r2.encoding = r2.apparent_encoding or "shift_jis"
            s2 = BeautifulSoup(r2.text, "html.parser")

            for a in s2.find_all("a", href=True):
                href = a.get("href") or ""
                absolute = urljoin(r2.url, href)
                low = absolute.lower()

                if ".lzh" not in low:
                    continue

                if (
                    ymd8 in low
                    or ymd6 in low
                    or f"k{ymd6}" in low
                ):
                    discovered.append(
                        (
                            " ".join(a.get_text(" ", strip=True).split()),
                            absolute,
                        )
                    )
        except Exception as exc:
            print(
                f"FOLLOW_ERROR url={url} "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )

    print("\n=== DISCOVERED TARGET LZH ===", flush=True)

    # 直接リンク + 1階層探索を統合
    urls = []
    seen = set()

    for label, href, absolute in target_lzh:
        if absolute not in seen:
            seen.add(absolute)
            urls.append((label, absolute))

    for label, absolute in discovered:
        if absolute not in seen:
            seen.add(absolute)
            urls.append((label, absolute))

    if not urls:
        print("NONE", flush=True)
        print("RESULT=TARGET_LZH_NOT_DISCOVERED", flush=True)
        return

    for i, (label, url) in enumerate(urls[:20], 1):
        print(f"{i:02d} TEXT={label!r} URL={url}", flush=True)

    print("\n=== DOWNLOAD TEST ===", flush=True)

    success = False

    for label, url in urls[:5]:
        try:
            rr = fetch(url)
            print(
                f"TRY url={url} status={rr.status_code} "
                f"bytes={len(rr.content)} "
                f"ctype={rr.headers.get('Content-Type')}",
                flush=True,
            )

            if rr.status_code == 200 and len(rr.content) > 100:
                print(
                    f"first32={rr.content[:32].hex()}",
                    flush=True,
                )

                # LHA/LZHでは先頭付近に "-lh" が現れることが多い
                if b"-lh" in rr.content[:64]:
                    print("archive_signature=LZH/LHA likely", flush=True)
                else:
                    print("archive_signature=UNKNOWN", flush=True)

                out = "/tmp/boatrace_k_target.lzh"
                with open(out, "wb") as f:
                    f.write(rr.content)

                print(f"saved={out}", flush=True)
                success = True
                break

        except Exception as exc:
            print(
                f"DOWNLOAD_ERROR={type(exc).__name__}: {exc}",
                flush=True,
            )

    print(
        f"RESULT={'SUCCESS' if success else 'DOWNLOAD_FAILED'}",
        flush=True,
    )

if __name__ == "__main__":
    main()