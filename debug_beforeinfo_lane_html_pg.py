# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, unicodedata, requests
from typing import Any
from bs4 import BeautifulSoup

TARGET_DATE = os.getenv("TARGET_DATE", "").strip()
TARGET_RACE_ID = os.getenv("TARGET_RACE_ID", "").strip()
TARGET_LANE = int(os.getenv("TARGET_LANE", "1"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))

def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(v or ""))).strip()

def main() -> None:
    print("✅ debug_beforeinfo_lane_html_pg.py VERSION 2026-07-15 lane-outer-html-v2-regex-fix", flush=True)
    print("読み取り専用です。", flush=True)

    m = re.fullmatch(r"(\d{8})_(\d{2})_(\d{2})", TARGET_RACE_ID)
    if not m:
        raise RuntimeError("TARGET_RACE_ID形式が不正です")
    ymd, venue_id, race_no_s = m.groups()
    if TARGET_DATE and ymd != TARGET_DATE.replace("-", ""):
        raise RuntimeError("TARGET_DATEとTARGET_RACE_IDの日付が不一致です")
    if TARGET_LANE not in range(1, 7):
        raise RuntimeError("TARGET_LANEは1～6です")

    url = (
        "https://www.boatrace.jp/owpc/pc/race/beforeinfo"
        f"?rno={int(race_no_s)}&jcd={venue_id}&hd={ymd}"
    )
    print(f"TARGET_RACE_ID={TARGET_RACE_ID}", flush=True)
    print(f"TARGET_LANE={TARGET_LANE}", flush=True)
    print(f"URL={url}", flush=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; boat-ai-beforeinfo-lane-debug/1.0)",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    })
    res = session.get(url, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"

    soup = BeautifulSoup(res.text, "html.parser")
    for index, tbody in enumerate(soup.select("tbody.is-fs12")):
        rows = tbody.find_all("tr", recursive=False)
        if not rows:
            continue
        first = rows[0].find_all(["th", "td"], recursive=False)
        values = [_norm(c.get_text(" ", strip=True)) for c in first]
        lane = None
        for value in values[:2]:
            if re.fullmatch(r"[1-6]", value or ""):
                lane = int(value)
                break
        if lane != TARGET_LANE:
            continue

        print(f"=== MATCHED TBODY index={index} lane={lane} ===", flush=True)
        for row_index, row in enumerate(rows):
            print(f"--- ROW {row_index} TEXT ---", flush=True)
            print(_norm(row.get_text(" | ", strip=True)), flush=True)
            print(f"--- ROW {row_index} DIRECT CELLS ---", flush=True)
            for cell_index, cell in enumerate(row.find_all(["th", "td"], recursive=False)):
                print(
                    f"cell[{cell_index}] tag={cell.name} "
                    f"class={' '.join(cell.get('class') or []) or '-'} "
                    f"rowspan={cell.get('rowspan') or '-'} "
                    f"colspan={cell.get('colspan') or '-'} "
                    f"text={_norm(cell.get_text(' ', strip=True))!r}",
                    flush=True,
                )
                for child_index, child in enumerate(cell.find_all(["a","span","div","img","i","em","strong"])[:20]):
                    attrs = {k: v for k, v in child.attrs.items() if k in {"class","id","src","alt","title","data-course","data-rank","data-value"}}
                    print(
                        f"  child[{child_index}] <{child.name}> attrs={attrs} "
                        f"text={_norm(child.get_text(' ', strip=True))!r}",
                        flush=True,
                    )
            print(f"--- ROW {row_index} HTML ---", flush=True)
            print(str(row)[:6000], flush=True)
        print("=== lane html debug finished ===", flush=True)
        return

    print("対象艇のtbodyが見つかりませんでした。", flush=True)

if __name__ == "__main__":
    main()