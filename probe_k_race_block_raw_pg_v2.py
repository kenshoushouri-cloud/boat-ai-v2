# -*- coding: utf-8 -*-
"""
probe_k_race_block_raw_pg_v2.py

Kファイル内の「払戻一覧の12R」ではなく、
詳細成績セクションの12Rを特定して原文表示する診断用。
DB更新なし。
"""

from __future__ import annotations
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
import requests
import lhafile  # type: ignore

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TARGET_RNO = int(os.getenv("TARGET_RNO", "12"))
TARGET_RACER = os.getenv("TARGET_RACER", "5360")
TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)"}

def k_url(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"https://www1.mbrace.or.jp/od2/K/{dt:%Y%m}/k{dt:%y%m%d}.lzh"

def get_lines():
    r = requests.get(k_url(TARGET_DATE), headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    with tempfile.TemporaryDirectory(prefix="kraw2_") as td:
        p = Path(td) / "k.lzh"
        p.write_bytes(r.content)
        arc = lhafile.Lhafile(str(p))
        data = arc.read(arc.namelist()[0])
    return data.decode("cp932").splitlines()

def is_detail_header(line):
    s = line.strip()
    # 詳細行は "12R ... H1800m ..." の形。払戻一覧は除外。
    return bool(re.match(rf"^{TARGET_RNO}R\b", s)) and "H1800m" in s

def main():
    print("✅ probe_k_race_block_raw_pg_v2.py VERSION 2026-08-17 detail-header-v2", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} TARGET_RNO={TARGET_RNO} TARGET_RACER={TARGET_RACER}", flush=True)
    print("DB書き込みなし。", flush=True)

    lines = get_lines()
    starts = [i for i, line in enumerate(lines) if is_detail_header(line)]
    print(f"detail_header_count={len(starts)}", flush=True)

    if not starts:
        # 診断用にTARGET_RACERの全出現位置だけ表示
        hits = [(i, x) for i, x in enumerate(lines) if TARGET_RACER in x]
        print(f"racer_global_hits={len(hits)}", flush=True)
        for i, x in hits[:20]:
            print(f"{i+1:05d}: {x!r}", flush=True)
        print("RESULT=DETAIL_HEADER_NOT_FOUND", flush=True)
        return

    # 1日には複数場の12Rがあるので、TARGET_RACERを含むブロックを優先
    chosen = None
    chosen_end = None
    for start in starts:
        end = min(len(lines), start + 80)
        for j in range(start + 1, min(len(lines), start + 80)):
            if re.match(r"^\s*\d{1,2}R\b", lines[j]) and "H1800m" in lines[j]:
                end = j
                break
            if re.match(r"^\d{2}KEND", lines[j].strip()) or lines[j].strip() == "ENDK":
                end = j
                break
        if any(TARGET_RACER in x for x in lines[start:end]):
            chosen, chosen_end = start, end
            break

    if chosen is None:
        chosen = starts[0]
        chosen_end = min(len(lines), chosen + 60)

    print(f"selected_start_line={chosen+1}", flush=True)
    print("=== DETAIL RAW BLOCK ===", flush=True)
    for i in range(chosen, chosen_end):
        print(f"{i+1:05d}: {lines[i]!r}", flush=True)

    print("=== TARGET RACER LINES ===", flush=True)
    hits = 0
    for i in range(chosen, chosen_end):
        if TARGET_RACER in lines[i]:
            print(f"{i+1:05d}: {lines[i]!r}", flush=True)
            print(f"HEX={lines[i].encode('cp932', errors='replace').hex()}", flush=True)
            hits += 1

    print(f"target_racer_hits={hits}", flush=True)
    print("RESULT=SUCCESS", flush=True)

if __name__ == "__main__":
    main()