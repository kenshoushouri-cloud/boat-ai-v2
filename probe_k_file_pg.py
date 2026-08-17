# -*- coding: utf-8 -*-
"""
probe_k_file_pg.py

BOAT RACE公式ダウンロードページ構造調査・低ログ版。
必要なリンク / iframe / form / script だけ抽出する。
DB更新なし。
"""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

VERSION = "2026-08-17 k-file-page-structure-v4-lowlog"

URL = "https://www.boatrace.jp/owpc/pc/extra/data/download.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

TIMEOUT = 30

KEYWORDS = [
    "競走成績",
    "番組表",
    "ダウンロード",
    "成績",
    "download",
    "mbrace",
    "od2",
    ".lzh",
    ".zip",
    "dindex",
    "static_extra",
]


def interesting(*values) -> bool:
    s = " ".join(str(v or "") for v in values).lower()
    return any(k.lower() in s for k in KEYWORDS)


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
        f"status={r.status_code} "
        f"bytes={len(r.content)} "
        f"final_url={r.url}",
        flush=True,
    )

    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"

    soup = BeautifulSoup(r.text, "html.parser")

    # --------------------------------------------------------
    # 1. ページタイトル
    # --------------------------------------------------------
    print("\n=== PAGE ===", flush=True)

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else "NONE"
    )
    print(f"title={title}", flush=True)

    # --------------------------------------------------------
    # 2. キーワード周辺テキスト
    # --------------------------------------------------------
    print("\n=== RELEVANT TEXT ===", flush=True)

    text = soup.get_text("\n", strip=True)
    lines = [
        re.sub(r"\s+", " ", x).strip()
        for x in text.splitlines()
        if x.strip()
    ]

    found_text = []

    for i, line in enumerate(lines):
        if interesting(line):
            block = " | ".join(
                lines[max(0, i - 1):min(len(lines), i + 2)]
            )
            if block not in found_text:
                found_text.append(block)

    if found_text:
        for x in found_text[:30]:
            print(x, flush=True)
    else:
        print("NONE", flush=True)

    # --------------------------------------------------------
    # 3. 関係ありそうなリンクのみ
    # --------------------------------------------------------
    print("\n=== RELEVANT LINKS ===", flush=True)

    relevant_links = []

    for a in soup.find_all("a"):
        href = a.get("href") or ""
        label = " ".join(
            a.get_text(" ", strip=True).split()
        )

        if interesting(label, href):
            relevant_links.append(
                (
                    label,
                    href,
                    urljoin(r.url, href),
                )
            )

    if relevant_links:
        for i, (label, href, absolute) in enumerate(
            relevant_links[:50],
            start=1,
        ):
            print(
                f"{i:02d} TEXT={label!r} "
                f"HREF={href!r} "
                f"URL={absolute}",
                flush=True,
            )
    else:
        print("NONE", flush=True)

    print(
        f"relevant_link_count={len(relevant_links)}",
        flush=True,
    )

    # --------------------------------------------------------
    # 4. iframe / form
    # --------------------------------------------------------
    print("\n=== IFRAMES / FORMS ===", flush=True)

    special_count = 0

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or ""
        print(
            f"IFRAME src={src!r} "
            f"url={urljoin(r.url, src)}",
            flush=True,
        )
        special_count += 1

    for form in soup.find_all("form"):
        action = form.get("action") or ""
        method = form.get("method") or ""
        print(
            f"FORM method={method!r} "
            f"action={action!r} "
            f"url={urljoin(r.url, action)}",
            flush=True,
        )
        special_count += 1

    if special_count == 0:
        print("NONE", flush=True)

    # --------------------------------------------------------
    # 5. 関係ありそうなJSだけ
    # --------------------------------------------------------
    print("\n=== RELEVANT SCRIPT SRC ===", flush=True)

    script_hits = []

    for script in soup.find_all("script"):
        src = script.get("src") or ""

        if src and interesting(src):
            script_hits.append(urljoin(r.url, src))

    if script_hits:
        for x in script_hits[:30]:
            print(x, flush=True)
    else:
        print("NONE", flush=True)

    # --------------------------------------------------------
    # 6. HTMLそのものにキーワードが存在するか
    # --------------------------------------------------------
    print("\n=== HTML KEYWORD CHECK ===", flush=True)

    lower = r.text.lower()

    for key in [
        "mbrace",
        "od2",
        ".lzh",
        ".zip",
        "dindex",
        "download",
        "競走成績",
        "番組表",
        "static_extra",
    ]:
        print(
            f"{key}: "
            f"{'FOUND' if key.lower() in lower else 'NOT_FOUND'}",
            flush=True,
        )

    # --------------------------------------------------------
    # 7. HTML中のURL/パスらしい文字列を限定抽出
    # --------------------------------------------------------
    print("\n=== RAW DOWNLOAD-LIKE STRINGS ===", flush=True)

    candidates = set()

    patterns = [
        r'["\']([^"\']*\.lzh[^"\']*)["\']',
        r'["\']([^"\']*\.zip[^"\']*)["\']',
        r'["\']([^"\']*download[^"\']*)["\']',
        r'["\']([^"\']*mbrace[^"\']*)["\']',
        r'["\']([^"\']*od2[^"\']*)["\']',
        r'["\']([^"\']*dindex[^"\']*)["\']',
    ]

    for pattern in patterns:
        for m in re.finditer(
            pattern,
            r.text,
            flags=re.IGNORECASE,
        ):
            value = m.group(1).strip()
            if len(value) <= 500:
                candidates.add(value)

    if candidates:
        for x in sorted(candidates)[:50]:
            print(x, flush=True)
    else:
        print("NONE", flush=True)

    print(
        f"raw_candidate_count={len(candidates)}",
        flush=True,
    )

    print("\n=== probe finished ===", flush=True)


if __name__ == "__main__":
    main()