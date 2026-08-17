# -*- coding: utf-8 -*-
"""
probe_k_file_pg.py

BOAT RACE公式 競走成績Kファイル取得プローブ。
DB書き込みなし。
"""

from __future__ import annotations

import os
from datetime import datetime
import requests

VERSION = "2026-08-17 k-file-download-probe-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}


def candidates(date_str: str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    yy = dt.strftime("%y")
    mm = dt.strftime("%m")
    dd = dt.strftime("%d")
    yyyymm = dt.strftime("%Y%m")

    filename = f"k{yy}{mm}{dd}.lzh"

    # 過去から使われている公式配信パターン。
    return [
        (
            "official-static",
            f"https://www.boatrace.jp/"
            f"static_extra/pc_static/download/data/"
            f"K/{yyyymm}/{filename}",
        ),
        (
            "official-static-lower",
            f"https://www.boatrace.jp/"
            f"static_extra/pc_static/download/data/"
            f"k/{yyyymm}/{filename}",
        ),
    ]


def main():
    print(
        f"✅ probe_k_file_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("DB書き込みはありません。", flush=True)

    found = False

    for name, url in candidates(TARGET_DATE):
        print("=" * 80, flush=True)
        print(f"TRY={name}", flush=True)
        print(f"URL={url}", flush=True)

        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            print(f"status_code={r.status_code}", flush=True)
            print(f"final_url={r.url}", flush=True)
            print(
                f"content_type={r.headers.get('Content-Type')}",
                flush=True,
            )
            print(
                f"content_length_header="
                f"{r.headers.get('Content-Length')}",
                flush=True,
            )
            print(f"received_bytes={len(r.content)}", flush=True)
            print(
                f"first_32_bytes={r.content[:32].hex()}",
                flush=True,
            )

            if r.status_code == 200 and len(r.content) > 100:
                found = True

                out = "/tmp/boatrace_result_test.lzh"
                with open(out, "wb") as f:
                    f.write(r.content)

                print("✅ DOWNLOAD SUCCESS", flush=True)
                print(f"saved={out}", flush=True)

                # LZHの典型的なヘッダー確認。
                head = r.content[:64]
                if b"-lh" in head:
                    print(
                        "archive_signature=LZH/LHA likely",
                        flush=True,
                    )
                else:
                    print(
                        "archive_signature=UNKNOWN",
                        flush=True,
                    )

                break

        except Exception as exc:
            print(
                f"ERROR={type(exc).__name__}: {exc}",
                flush=True,
            )

    print("=" * 80, flush=True)

    if found:
        print(
            "RESULT=SUCCESS: Kファイル候補を取得できました。",
            flush=True,
        )
    else:
        print(
            "RESULT=NOT_FOUND: URL規則または配信方式を再確認します。",
            flush=True,
        )


if __name__ == "__main__":
    main()