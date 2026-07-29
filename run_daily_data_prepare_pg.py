# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")
    try:
        import psycopg  # type: ignore
        return psycopg.connect(url)
    except Exception:
        import psycopg2  # type: ignore
        return psycopg2.connect(url)

def audit_target_date(target_date: str) -> None:
    sql = '''
        WITH race_counts AS (
            SELECT
                r.race_id,
                COUNT(DISTINCT o.ticket) FILTER (
                    WHERE o.ticket ~ '^[1-6]-[1-6]-[1-6]$'
                      AND split_part(o.ticket, '-', 1) <> split_part(o.ticket, '-', 2)
                      AND split_part(o.ticket, '-', 1) <> split_part(o.ticket, '-', 3)
                      AND split_part(o.ticket, '-', 2) <> split_part(o.ticket, '-', 3)
                )::int AS valid_tickets,
                COUNT(*) FILTER (
                    WHERE o.ticket ~ '^[1-6]-[1-6]-[1-6]$'
                      AND (
                           split_part(o.ticket, '-', 1) = split_part(o.ticket, '-', 2)
                        OR split_part(o.ticket, '-', 1) = split_part(o.ticket, '-', 3)
                        OR split_part(o.ticket, '-', 2) = split_part(o.ticket, '-', 3)
                      )
                )::int AS invalid_rows
            FROM v2_races r
            LEFT JOIN v2_odds_trifecta o ON o.race_id = r.race_id
            WHERE r.race_date = %s
            GROUP BY r.race_id
        )
        SELECT race_id, valid_tickets, invalid_rows
        FROM race_counts
        WHERE valid_tickets < 120 OR invalid_rows > 0
        ORDER BY race_id
    '''
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (target_date,))
            rows = cur.fetchall()
    finally:
        conn.close()

    print("=== daily odds quality audit ===", flush=True)
    print(f"problem_races={len(rows)}", flush=True)
    for race_id, valid_tickets, invalid_rows in rows[:100]:
        print(
            f"  {race_id} valid_tickets={valid_tickets} invalid_rows={invalid_rows}",
            flush=True,
        )

def main() -> None:
    print("✅ run_daily_data_prepare_pg.py VERSION 2026-07-29-quality-audit", flush=True)

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")
        os.environ["TARGET_DATE"] = target_date

    os.environ["REPAIR_START_DATE"] = target_date
    os.environ["REPAIR_END_DATE"] = target_date
    os.environ["REPAIR_DO_RACES"] = "1"
    os.environ["REPAIR_DO_RESULTS"] = "0"
    os.environ["REPAIR_DO_ODDS"] = "1"
    os.environ.setdefault("REPAIR_WORKERS", os.getenv("WORKERS", "4"))
    os.environ.setdefault("REPAIR_ODDS_WORKERS", os.getenv("ODDS_WORKERS", "2"))
    os.environ.setdefault("REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1"))

    print(f"TARGET_DATE={target_date}", flush=True)

    base_dir = Path(__file__).resolve().parent
    repair_path = base_dir / "repair_month_all_pg.py"
    if not repair_path.exists():
        raise FileNotFoundError(f"repair_month_all_pg.py が見つかりません: {repair_path}")

    runpy.run_path(str(repair_path), run_name="__main__")
    audit_target_date(target_date)

if __name__ == "__main__":
    main()