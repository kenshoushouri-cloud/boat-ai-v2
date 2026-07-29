# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import importlib
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

JST = timezone(timedelta(hours=9))
WINDOW_PRESETS = {
    "morning": ("08:30", "10:15"),
    "day": ("09:45", "15:00"),
    "night": ("14:45", None),
}

def _today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")

def _resolve_window() -> Tuple[str, Optional[str], str]:
    name = (os.getenv("WINDOW_NAME") or "").strip().lower()
    start = (os.getenv("WINDOW_START") or "").strip()
    end = (os.getenv("WINDOW_END") or "").strip()
    if not start:
        if name in WINDOW_PRESETS:
            start, default_end = WINDOW_PRESETS[name]
            if not end:
                end = default_end or ""
        else:
            name = "morning"
            start, default_end = WINDOW_PRESETS[name]
            end = default_end or ""
    if not name:
        name = f"{start}-{end or 'end'}"
    return start, (end or None), name

def _normalize_date(v: Any) -> str:
    return "" if v is None else str(v)[:10]

def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL ãæªè¨­å®ã§ã")
    try:
        import psycopg  # type: ignore
        return psycopg.connect(url)
    except Exception:
        import psycopg2  # type: ignore
        return psycopg2.connect(url)

def _fetch_dicts(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [getattr(d, "name", None) or d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()

def select_window_races(target_date: str, start: str, end: Optional[str]) -> List[Dict[str, Any]]:
    if end:
        if start <= end:
            sql = '''
                SELECT race_id, race_date::text AS race_date, venue_code,
                       venue_name, race_no, deadline_time, deadline_at
                FROM v2_races
                WHERE race_date = %s
                  AND deadline_time IS NOT NULL
                  AND deadline_time >= %s
                  AND deadline_time < %s
                ORDER BY deadline_time, venue_code, race_no
            '''
            params = (target_date, start, end)
        else:
            sql = '''
                SELECT race_id, race_date::text AS race_date, venue_code,
                       venue_name, race_no, deadline_time, deadline_at
                FROM v2_races
                WHERE race_date = %s
                  AND deadline_time IS NOT NULL
                  AND (deadline_time >= %s OR deadline_time < %s)
                ORDER BY deadline_time, venue_code, race_no
            '''
            params = (target_date, start, end)
    else:
        sql = '''
            SELECT race_id, race_date::text AS race_date, venue_code,
                   venue_name, race_no, deadline_time, deadline_at
            FROM v2_races
            WHERE race_date = %s
              AND deadline_time IS NOT NULL
              AND deadline_time >= %s
            ORDER BY deadline_time, venue_code, race_no
        '''
        params = (target_date, start)
    return _fetch_dicts(sql, params)

def select_valid_odds_counts(race_ids: List[str]) -> Dict[str, int]:
    if not race_ids:
        return {}
    valid_condition = '''
        ticket ~ '^[1-6]-[1-6]-[1-6]$'
        AND split_part(ticket, '-', 1) <> split_part(ticket, '-', 2)
        AND split_part(ticket, '-', 1) <> split_part(ticket, '-', 3)
        AND split_part(ticket, '-', 2) <> split_part(ticket, '-', 3)
    '''
    sql = f'''
        SELECT race_id, COUNT(DISTINCT ticket)::int AS valid_odds_rows
        FROM v2_odds_trifecta
        WHERE race_id = ANY(%s)
          AND {valid_condition}
        GROUP BY race_id
    '''
    try:
        rows = _fetch_dicts(sql, (race_ids,))
    except Exception:
        placeholders = ",".join(["%s"] * len(race_ids))
        sql = f'''
            SELECT race_id, COUNT(DISTINCT ticket)::int AS valid_odds_rows
            FROM v2_odds_trifecta
            WHERE race_id IN ({placeholders})
              AND {valid_condition}
            GROUP BY race_id
        '''
        rows = _fetch_dicts(sql, tuple(race_ids))
    return {str(r["race_id"]): int(r["valid_odds_rows"]) for r in rows}

def _run_fetch_batch(repair, races: List[Dict[str, Any]], workers: int, label: str):
    total_saved = 0
    success = 0
    failed = []
    if not races:
        return success, failed, total_saved
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {}
        for r in races:
            fut = ex.submit(
                repair.process_race,
                _normalize_date(r["race_date"]),
                str(r["venue_code"]).zfill(2),
                int(r["race_no"]),
                True,
            )
            futures[fut] = r
        for idx, fut in enumerate(as_completed(futures), start=1):
            r = futures[fut]
            try:
                rr = fut.result()
            except Exception as exc:
                failed.append((str(r["race_id"]), repr(exc)))
                continue
            if rr.ok:
                success += 1
                total_saved += int(rr.odds_saved or 0)
            else:
                failed.append((str(rr.race_id), str(rr.error)))
            if idx % 20 == 0 or idx == len(futures):
                print(
                    f"progress {label}: {idx}/{len(futures)} "
                    f"success={success} failed={len(failed)} saved_rows={total_saved}",
                    flush=True,
                )
    return success, failed, total_saved

def main() -> None:
    print("â run_odds_window_pg.py VERSION 2026-07-29-quality-guard", flush=True)
    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()
    workers = int(os.getenv("WINDOW_WORKERS") or os.getenv("ODDS_WORKERS") or "2")
    max_retries = max(0, int(os.getenv("WINDOW_ODDS_RETRIES", "2")))
    retry_wait = max(0.0, float(os.getenv("WINDOW_ODDS_RETRY_WAIT_SEC", "30")))

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(f"WINDOW_WORKERS={workers}", flush=True)
    print(f"WINDOW_ODDS_RETRIES={max_retries}", flush=True)
    print(f"WINDOW_ODDS_RETRY_WAIT_SEC={retry_wait}", flush=True)
    print(f"DATABASE_URL={'OK' if os.getenv('DATABASE_URL') else 'MISSING'}", flush=True)

    all_races = select_window_races(target_date, window_start, window_end)
    print(f"target_races={len(all_races)}", flush=True)
    if not all_races:
        print("å¯¾è±¡ã¬ã¼ã¹ãªããçµäºãã¾ãã", flush=True)
        return

    races = all_races
    if (os.getenv("WINDOW_SKIP_FULL_ODDS") or "0") == "1":
        counts = select_valid_odds_counts([str(r["race_id"]) for r in races])
        before = len(races)
        races = [r for r in races if counts.get(str(r["race_id"]), 0) < 120]
        print(f"skip_full_odds=1 before={before} after={len(races)}", flush=True)
        if not races:
            print("å¨å¯¾è±¡ã¬ã¼ã¹ã§æå¹ãª3é£å120éããæã£ã¦ãã¾ãã", flush=True)
            return

    os.environ["REPAIR_DO_RACES"] = "0"
    os.environ["REPAIR_DO_RESULTS"] = "0"
    os.environ["REPAIR_DO_ODDS"] = "1"
    os.environ.setdefault("REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1"))
    os.environ.setdefault("REPAIR_ODDS_WORKERS", str(workers))
    repair = importlib.import_module("repair_month_all_pg")

    total_success = 0
    total_saved = 0
    all_failed = []

    success, failed, saved = _run_fetch_batch(repair, races, workers, "initial")
    total_success += success
    total_saved += saved
    all_failed.extend(failed)

    pending = races
    for retry_no in range(1, max_retries + 1):
        counts = select_valid_odds_counts([str(r["race_id"]) for r in pending])
        pending = [r for r in pending if counts.get(str(r["race_id"]), 0) < 120]
        if not pending:
            print(f"retry_check={retry_no}: å¨ã¬ã¼ã¹120éãå®äº", flush=True)
            break
        print(f"retry_check={retry_no}: incomplete_races={len(pending)}", flush=True)
        for r in pending[:30]:
            rid = str(r["race_id"])
            print(f"  {rid} valid_tickets={counts.get(rid, 0)}", flush=True)
        if retry_wait > 0:
            print(f"retry_wait={retry_wait} sec", flush=True)
            time.sleep(retry_wait)
        success, failed, saved = _run_fetch_batch(repair, pending, workers, f"retry-{retry_no}")
        total_success += success
        total_saved += saved
        all_failed.extend(failed)

    final_counts = select_valid_odds_counts([str(r["race_id"]) for r in all_races])
    incomplete = [
        (str(r["race_id"]), final_counts.get(str(r["race_id"]), 0))
        for r in all_races
        if final_counts.get(str(r["race_id"]), 0) < 120
    ]

    print("=== odds window finished ===", flush=True)
    print(f"target_races={len(all_races)}", flush=True)
    print(f"fetch_success_total={total_success}", flush=True)
    print(f"fetch_failed_total={len(all_failed)}", flush=True)
    print(f"saved_odds_rows_total={total_saved}", flush=True)
    print(f"complete_120={len(all_races) - len(incomplete)}", flush=True)
    print(f"incomplete={len(incomplete)}", flush=True)

    if incomplete:
        print("incomplete sample:", flush=True)
        for race_id, count in incomplete[:50]:
            print(f"  {race_id} valid_tickets={count}", flush=True)
    if all_failed:
        print("failed sample:", flush=True)
        for race_id, error in all_failed[:50]:
            print(f"  {race_id} {error}", flush=True)

if __name__ == "__main__":
    main()