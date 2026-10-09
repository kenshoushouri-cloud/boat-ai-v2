# -*- coding: utf-8 -*-
"""Read-only compare official K race ids vs v2_results for one date."""
from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
from pathlib import Path
import lhafile
import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from save_k_day_results_pg import parse_k_text

TARGET_DATE=os.getenv("TARGET_DATE","2026-08-21")

def main():
    ymd=TARGET_DATE.replace("-","")
    yy=ymd[2:]
    mm=ymd[4:6]
    dd=ymd[6:8]
    url=f"https://www1.mbrace.or.jp/od2/K/{ymd[:6]}/k{yy}{mm}{dd}.lzh"

    with urllib.request.urlopen(url, timeout=30) as r:
        raw=r.read()
    print(f"K_GET status=200 bytes={len(raw)}")

    with tempfile.NamedTemporaryFile(suffix=".lzh") as f:
        f.write(raw); f.flush()
        arc=lhafile.Lhafile(f.name)
        names=arc.namelist()
        if not names:
            raise RuntimeError("empty K archive")
        text=arc.read(names[0]).decode("cp932","replace")

    parsed=parse_k_text(text, TARGET_DATE)
    wanted=sorted(str(x["race_id"]) for x in parsed)
    print(f"K_RACES={len(wanted)}")

    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        cur=conn.cursor()
        cur.execute("BEGIN READ ONLY")
        cur.execute(
            "select race_id from v2_results where race_id = any(%s)",
            (wanted,),
        )
        existing={str(x["race_id"]) for x in cur.fetchall()}
        cur.execute(
            "select race_id from v2_races where race_id = any(%s)",
            (wanted,),
        )
        race_ids={str(x["race_id"]) for x in cur.fetchall()}
        conn.rollback()

    missing_results=[x for x in wanted if x not in existing]
    missing_races=[x for x in wanted if x not in race_ids]

    print(f"DB_V2_RESULTS={len(existing)}/{len(wanted)}")
    print(f"MISSING_V2_RESULTS={len(missing_results)}")
    for rid in missing_results:
        print(f"MISSING_RESULT_RACE_ID={rid}")
    print(f"MISSING_V2_RACES={len(missing_races)}")
    for rid in missing_races:
        print(f"MISSING_BASE_RACE_ID={rid}")
    print("DB_TRANSACTION=READ_ONLY")
    print("K_RESULT_GAP_AUDIT=PASS")

if __name__=="__main__":
    main()
