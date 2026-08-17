# -*- coding: utf-8 -*-
"""
probe_k_accident_line_pg.py

Kファイル内の指定レースについて、
事故艇/対象登録番号を含む原文行だけを表示する低ログ診断。
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
TARGET_RACER = os.getenv("TARGET_RACER", "5360")
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
    with tempfile.TemporaryDirectory(prefix="kacc_") as td:
        p = Path(td) / "k.lzh"
        p.write_bytes(r.content)
        lha = lhafile.Lhafile(str(p))
        data = lha.read(lha.namelist()[0])
    return data.decode("cp932")

def main():
    print("✅ probe_k_accident_line_pg.py VERSION 2026-08-17 accident-raw-v1", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} TARGET_RNO={TARGET_RNO} TARGET_RACER={TARGET_RACER}", flush=True)
    print("DB書き込みなし。", flush=True)

    lines = get_text().splitlines()

    # 12R見出し位置を探し、次R/場終了までを対象にする
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(f"{TARGET_RNO}R"):
            start = i
            break
    if start is None:
        raise RuntimeError("target race header not found")

    end = min(len(lines), start + 120)
    for i in range(start + 1, len(lines)):
        s = lines[i].lstrip()
        if i > start + 1 and s[:2].rstrip("R").isdigit() and "R" in s[:4]:
            end = i
            break
        if s.startswith("ENDK") or s.startswith("24KEND"):
            end = i
            break

    block = lines[start:end]

    print("=== TARGET RAW LINES ===", flush=True)
    hits = 0
    keywords = (TARGET_RACER, "転", "落", "沈", "妨", "失", "欠", "不", "F", "L")
    for offset, line in enumerate(block):
        if any(k in line for k in keywords):
            print(f"{start+offset+1:05d}: {line!r}", flush=True)
            print(f"HEX={line.encode('cp932', errors='replace').hex()}", flush=True)
            hits += 1

    print(f"hit_lines={hits}", flush=True)
    print("RESULT=SUCCESS", flush=True)

if __name__ == "__main__":
    main()