# -*- coding: utf-8 -*-
"""
probe_k_race_block_raw_pg.py

Kファイルの指定Rブロック原文をそのまま少量表示する診断用。
DB更新なし。
"""

from __future__ import annotations
import os
import tempfile
from datetime import datetime
from pathlib import Path
import requests
import lhafile  # type: ignore

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TARGET_RNO = int(os.getenv("TARGET_RNO", "12"))
TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
}

def k_url(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"https://www1.mbrace.or.jp/od2/K/{dt:%Y%m}/k{dt:%y%m%d}.lzh"

def get_text():
    r = requests.get(k_url(TARGET_DATE), headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    with tempfile.TemporaryDirectory(prefix="kraw_") as td:
        p = Path(td) / "k.lzh"
        p.write_bytes(r.content)
        lha = lhafile.Lhafile(str(p))
        data = lha.read(lha.namelist()[0])
    return data.decode("cp932")

def main():
    print("✅ probe_k_race_block_raw_pg.py VERSION 2026-08-17 raw-block-v1", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} TARGET_RNO={TARGET_RNO}", flush=True)
    print("DB書き込みなし。", flush=True)

    lines = get_text().splitlines()

    # この日最初に現れる対象Rを表示。
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(f"{TARGET_RNO}R"):
            start = i
            break

    if start is None:
        raise RuntimeError("target race header not found")

    print(f"start_line={start+1}", flush=True)
    print("=== RAW BLOCK ===", flush=True)

    # 次のR見出しまたは最大50行
    shown = 0
    for i in range(start, min(len(lines), start + 50)):
        line = lines[i]
        if i > start:
            s = line.lstrip()
            # 次のレース見出し
            for rno in range(1, 13):
                if rno != TARGET_RNO and s.startswith(f"{rno}R"):
                    print(f"STOP next_race={rno}R line={i+1}", flush=True)
                    print("RESULT=SUCCESS", flush=True)
                    return

        print(f"{i+1:05d}: {line!r}", flush=True)
        shown += 1

    print(f"shown_lines={shown}", flush=True)
    print("RESULT=SUCCESS", flush=True)

if __name__ == "__main__":
    main()