# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, requests
from typing import Dict, Optional
from bs4 import BeautifulSoup

VERSION = "2026-08-19 deadline-table-diagnostic-v1"
TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-19")
VENUE_ID = os.getenv("DEADLINE_TEST_VENUE", "10").zfill(2)
RACE_NOS = [int(x) for x in os.getenv("DEADLINE_TEST_RACES", "1,2,12").split(",") if x.strip()]

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
})

def zen(s: str) -> str:
    return str(s or "").translate(str.maketrans({
        "０":"0","１":"1","２":"2","３":"3","４":"4","５":"5",
        "６":"6","７":"7","８":"8","９":"9","：":":","　":" ",
    }))

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", zen(s)).strip()

def hhmm(s: str) -> Optional[str]:
    m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", clean(s))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if 0 <= h <= 23 and 0 <= mi <= 59 else None

def url(rno: int) -> str:
    return f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={rno}&jcd={VENUE_ID}&hd={TARGET_DATE.replace('-', '')}"

def fetch(rno: int) -> str:
    r = S.get(url(rno), timeout=25)
    r.raise_for_status()
    enc = (r.encoding or "").strip() or "utf-8"
    try:
        return r.content.decode(enc)
    except Exception:
        return r.content.decode("utf-8", errors="replace")

def parse_deadline_table(html: str) -> Dict[int, str]:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for i, tr in enumerate(rows):
            texts = [clean(c.get_text(" ", strip=True)) for c in tr.find_all(["th","td"])]
            race_cols = {}
            for col, text in enumerate(texts):
                m = re.fullmatch(r"(?:第\s*)?([1-9]|1[0-2])\s*R", text, flags=re.I)
                if m:
                    race_cols[col] = int(m.group(1))
            if len(race_cols) < 3:
                continue
            for tr2 in rows[i+1:i+5]:
                texts2 = [clean(c.get_text(" ", strip=True)) for c in tr2.find_all(["th","td"])]
                if "締切" not in " ".join(texts2):
                    continue
                out = {}
                for col, race_no in race_cols.items():
                    if col < len(texts2):
                        t = hhmm(texts2[col])
                        if t:
                            out[race_no] = t
                if len(out) >= 3:
                    return out
    return {}

def main():
    print(f"✅ diagnose_deadline_table_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE} VENUE_ID={VENUE_ID} TEST_RACES={RACE_NOS}", flush=True)
    print("READ_ONLY=1 DB_UPDATE=0", flush=True)
    for rno in RACE_NOS:
        d = parse_deadline_table(fetch(rno))
        print(f"PAGE_RNO={rno} parsed_deadlines={len(d)}", flush=True)
        print("  " + " ".join(f"{k}R={d.get(k)}" for k in range(1,13)), flush=True)
        print(f"  TARGET {rno}R={d.get(rno)}", flush=True)
    print("RESULT=PASS", flush=True)

if __name__ == "__main__":
    main()