# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import requests
import repair_month_all_pg as rp

VERSION = "2026-08-18 historical-odds-encoding-v1"
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "20260731_13_10")
ENCODINGS = ["utf-8", "cp932", "shift_jis", "euc_jp", "iso2022_jp"]

def main():
    print(f"✅ probe_historical_odds_encoding_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print("DB書き込みなし。", flush=True)

    parsed = rp._parse_race_id(TARGET_RACE_ID)
    if not parsed:
        raise RuntimeError("TARGET_RACE_ID が不正です")

    date_str, venue_id, race_no = parsed
    url = rp._official_url("odds3t", date_str, venue_id, race_no)
    print(f"URL={url}", flush=True)

    res = requests.get(
        url,
        headers=rp.SESSION.headers,
        timeout=rp.HTTP_TIMEOUT,
        allow_redirects=True,
    )

    print(f"status={res.status_code}", flush=True)
    print(f"content_type={res.headers.get('content-type')}", flush=True)
    print(f"requests_encoding={res.encoding}", flush=True)
    print(f"apparent_encoding={res.apparent_encoding}", flush=True)
    print(f"bytes={len(res.content)}", flush=True)
    print(f"first64={res.content[:64].hex()}", flush=True)

    head_ascii = res.content[:5000].decode("ascii", errors="ignore")
    metas = re.findall(r"charset\\s*=\\s*[\\\"']?\\s*([A-Za-z0-9._-]+)", head_ascii, flags=re.I)
    print(f"meta_charset_candidates={metas}", flush=True)

    print("\n=== DECODE / PARSE COMPARISON ===", flush=True)

    tested = []
    for enc in ENCODINGS:
        try:
            text = res.content.decode(enc)
        except Exception as exc:
            print(f"{enc}: DECODE_FAIL {type(exc).__name__}: {exc}", flush=True)
            continue

        rows = rp.parse_odds3t(text, TARGET_RACE_ID)
        jp_count = sum(text.count(x) for x in ("3連単", "オッズ", "締切", "発売"))
        replacement_count = text.count("\ufffd")
        sample = re.sub(r"\\s+", " ", text[:500])

        print(
            f"{enc}: chars={len(text)} parsed_rows={len(rows)} "
            f"jp_keyword_hits={jp_count} replacement={replacement_count}",
            flush=True,
        )
        print(f"{enc}: sample={sample[:260]}", flush=True)

        if rows:
            print(
                f"{enc}: first_rows=" +
                ", ".join(f"{x.get('ticket')}={x.get('odds')}" for x in rows[:12]),
                flush=True,
            )

        tested.append((enc, len(rows), jp_count, replacement_count))

    print("\n=== BEST ===", flush=True)
    if tested:
        best = sorted(tested, key=lambda x: (x[1], x[2], -x[3]), reverse=True)[0]
        print(
            f"encoding={best[0]} parsed_rows={best[1]} "
            f"jp_keyword_hits={best[2]} replacement={best[3]}",
            flush=True,
        )

    print("RESULT=SUCCESS", flush=True)

if __name__ == "__main__":
    main()