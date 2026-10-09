# -*- coding: utf-8 -*-
"""Read-only compare official K race ids vs v2_results for one date."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_k_day_all_pg as ka

TARGET_DATE=os.getenv("TARGET_DATE","2026-08-21")

def main():
    text=ka.get_k_text(TARGET_DATE)
    sections=ka.split_venue_sections(text.splitlines())
    parsed=[]
    for section in sections:
        parsed.extend(ka.parse_section(section))
    wanted=sorted(str(x["race_id"]) for x in parsed)
    print(f"K_RACES={len(wanted)}")
    print(f"K_VENUE_SECTIONS={len(sections)}")

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
