# -*- coding: utf-8 -*-
"""
run_odds_window_pg.py

Railway Postgres版：締切時刻ウィンドウ内のレースだけ、3連単オッズを再取得します。

想定用途:
- 早朝枠: WINDOW_NAME=morning または WINDOW_START=08:30 WINDOW_END=10:15
- 昼間枠: WINDOW_NAME=day     または WINDOW_START=09:45 WINDOW_END=15:00
- 後半枠: WINDOW_NAME=night   または WINDOW_START=14:45 WINDOW_ENDなし

Start Command:
    python -u run_odds_window_pg.py

主な環境変数:
    TARGET_DATE=2026-07-09          # 未指定ならJST当日
    WINDOW_NAME=morning|day|night   # 任意。WINDOW_START/ENDが優先
    WINDOW_START=08:30
    WINDOW_END=10:15                # 後半枠は空でもOK
    WINDOW_WORKERS=2
    WINDOW_SKIP_FULL_ODDS=0         # 1なら既に120通り揃っているレースはスキップ
"""

from __future__ import annotations

import os
import runpy
import importlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

JST = timezone(timedelta(hours=9))


# ============================================================
# Window settings
# ============================================================

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
            # 安全側デフォルト: 早朝枠
            name = "morning"
            start, default_end = WINDOW_PRESETS[name]
            end = default_end or ""

    if not name:
        name = f"{start}-{end or 'end'}"

    return start, (end or None), name


def _normalize_date(v: Any) -> str:
    if v is None:
        return ""
    return str(v)[:10]


# ============================================================
# DB helpers
# ============================================================

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


def _fetch_dicts(sql: str, params: Tuple[Any, ...]) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = []
            for d in cur.description:
                cols.append(getattr(d, "name", None) or d[0])
            return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def select_window_races(target_date: str, start: str, end: Optional[str]) -> List[Dict[str, Any]]:
    """
    v2_races.deadline_time を使い、指定ウィンドウのレースだけ取得する。
    deadline_time は HH:MM 形式のため、文字列比較で時刻順に比較できる。
    """
    if end:
        if start <= end:
            sql = """
                select
                    race_id,
                    race_date::text as race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                from v2_races
                where race_date = %s
                  and deadline_time is not null
                  and deadline_time >= %s
                  and deadline_time < %s
                order by deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
        else:
            # 日跨ぎウィンドウ用。今回の運用では通常使わない。
            sql = """
                select
                    race_id,
                    race_date::text as race_date,
                    venue_code,
                    venue_name,
                    race_no,
                    deadline_time,
                    deadline_at
                from v2_races
                where race_date = %s
                  and deadline_time is not null
                  and (deadline_time >= %s or deadline_time < %s)
                order by deadline_time, venue_code, race_no
            """
            params = (target_date, start, end)
    else:
        sql = """
            select
                race_id,
                race_date::text as race_date,
                venue_code,
                venue_name,
                race_no,
                deadline_time,
                deadline_at
            from v2_races
            where race_date = %s
              and deadline_time is not null
              and deadline_time >= %s
            order by deadline_time, venue_code, race_no
        """
        params = (target_date, start)

    return _fetch_dicts(sql, params)


def select_odds_counts(race_ids: List[str]) -> Dict[str, int]:
    if not race_ids:
        return {}

    sql = """
        select race_id, count(*)::int as odds_rows
        from v2_odds_trifecta
        where race_id = any(%s)
        group by race_id
    """

    # psycopg2/psycopgともPostgres配列としてlistを渡せる想定。
    try:
        rows = _fetch_dicts(sql, (race_ids,))
        return {str(r["race_id"]): int(r["odds_rows"]) for r in rows}
    except Exception:
        # ドライバ差異の保険。IN句に展開する。
        placeholders = ",".join(["%s"] * len(race_ids))
        sql2 = f"""
            select race_id, count(*)::int as odds_rows
            from v2_odds_trifecta
            where race_id in ({placeholders})
            group by race_id
        """
        rows = _fetch_dicts(sql2, tuple(race_ids))
        return {str(r["race_id"]): int(r["odds_rows"]) for r in rows}


# ============================================================
# Main
# ============================================================

def main() -> None:
    print("✅ run_odds_window_pg.py", flush=True)

    target_date = os.getenv("TARGET_DATE") or _today_jst()
    window_start, window_end, window_name = _resolve_window()

    print(f"TARGET_DATE={target_date}", flush=True)
    print(f"WINDOW_NAME={window_name}", flush=True)
    print(f"WINDOW_START={window_start}", flush=True)
    print(f"WINDOW_END={window_end or ''}", flush=True)
    print(f"DATABASE_URL={'OK' if os.getenv('DATABASE_URL') else 'MISSING'}", flush=True)

    races = select_window_races(target_date, window_start, window_end)
    print(f"target_races={len(races)}", flush=True)

    if races:
        print("target sample:", flush=True)
        for r in races[:20]:
            print(
                f"  {r['race_id']} {r.get('venue_name') or ''} {r.get('race_no')}R deadline={r.get('deadline_time')}",
                flush=True,
            )

    if not races:
        print("対象レースなし。終了します。", flush=True)
        return

    skip_full = (os.getenv("WINDOW_SKIP_FULL_ODDS") or "0") == "1"
    race_ids = [str(r["race_id"]) for r in races]

    if skip_full:
        odds_counts = select_odds_counts(race_ids)
        before = len(races)
        races = [r for r in races if int(odds_counts.get(str(r["race_id"]), 0)) < 120]
        print(f"skip_full_odds=1 before={before} after={len(races)}", flush=True)
        if not races:
            print("全対象レースのオッズが120通り揃っています。終了します。", flush=True)
            return

    # repair_month_all_pg.py を odds-only で使う。
    # import時に環境変数を読むため、必ずimport前にセットする。
    os.environ["REPAIR_DO_RACES"] = "0"
    os.environ["REPAIR_DO_RESULTS"] = "0"
    os.environ["REPAIR_DO_ODDS"] = "1"
    os.environ.setdefault("REPAIR_SLEEP_SEC", os.getenv("SLEEP_SEC", "0.1"))
    os.environ.setdefault("REPAIR_ODDS_WORKERS", os.getenv("WINDOW_WORKERS", "2"))

    repair = importlib.import_module("repair_month_all_pg")

    workers = int(os.getenv("WINDOW_WORKERS") or os.getenv("ODDS_WORKERS") or "2")
    total_odds_saved = 0
    success = 0
    failed = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {}
        for r in races:
            date_str = _normalize_date(r["race_date"])
            venue_code = str(r["venue_code"]).zfill(2)
            race_no = int(r["race_no"])
            futures[ex.submit(repair.process_race, date_str, venue_code, race_no, True)] = r

        for idx, fut in enumerate(as_completed(futures), start=1):
            rr = fut.result()
            if rr.ok:
                success += 1
                total_odds_saved += int(rr.odds_saved or 0)
            else:
                failed.append(rr)

            if idx % 20 == 0 or idx == len(futures):
                print(
                    f"progress odds-window: {idx}/{len(futures)} success={success} failed={len(failed)} odds_rows={total_odds_saved}",
                    flush=True,
                )

    print("=== odds window finished ===", flush=True)
    print(f"target_races={len(races)}", flush=True)
    print(f"success={success}", flush=True)
    print(f"failed={len(failed)}", flush=True)
    print(f"saved_odds_rows={total_odds_saved}", flush=True)

    if failed:
        print("failed sample:", flush=True)
        for rr in failed[:50]:
            print(f"  {rr.race_id} {rr.error}", flush=True)


if __name__ == "__main__":
    main()